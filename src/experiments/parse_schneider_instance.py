import argparse
import json
import re
from pathlib import Path


NODE_TYPES = {
    "d": "depot",
    "depot": "depot",
    "c": "client",
    "customer": "client",
    "f": "station",
    "station": "station",
}

PARAMETER_KEYS = {
    "q": "battery_capacity",
    "c": "vehicle_capacity",
    "r": "consumption_per_distance",
    "g": "inverse_refueling_rate",
    "v": "average_velocity",
}

NUMBER_PATTERN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")


def parse_schneider_file(path):
    """Parses a Schneider-style EVRP-TW text file into nodes and parameters."""

    nodes = []
    parameters = {}
    source_path = Path(path)

    with source_path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            clean_line = raw_line.strip()
            if not clean_line or clean_line.startswith("#"):
                continue

            node = parse_node_line(clean_line)
            if node is not None:
                nodes.append(node)
                continue

            parameter = parse_parameter_line(clean_line)
            if parameter is not None:
                key, value = parameter
                parameters[key] = value
                continue

            if looks_like_malformed_node(clean_line):
                raise ValueError(f"Could not parse line {line_number}: {clean_line}")

    if not nodes:
        raise ValueError(f"No Schneider-style nodes found in {source_path}")

    return nodes, parameters


def parse_node_line(line):
    """Parses rows like 'C1 c 10 20 5 0 100 10'."""

    tokens = strip_inline_comment(line).split()
    if len(tokens) < 8:
        return None

    node_type = NODE_TYPES.get(tokens[1].lower())
    if node_type is None:
        return None

    return {
        "name": tokens[0],
        "type": node_type,
        "x": parse_number(tokens[2]),
        "y": parse_number(tokens[3]),
        "demand": parse_number(tokens[4]),
        "tw_early": parse_number(tokens[5]),
        "tw_late": parse_number(tokens[6]),
        "service_duration": parse_number(tokens[7]),
    }


def parse_parameter_line(line):
    """Parses parameter rows such as 'Q 77.75 / battery capacity'."""

    tokens = line.strip().split(maxsplit=1)
    if not tokens:
        return None

    key = PARAMETER_KEYS.get(tokens[0].lower())
    if key is None:
        return None

    numbers = NUMBER_PATTERN.findall(line)
    if numbers:
        return key, parse_number(numbers[-1])
    return None


def strip_inline_comment(line):
    return re.split(r"\s[/#]\s|#", line, maxsplit=1)[0].strip()


def looks_like_malformed_node(line):
    tokens = strip_inline_comment(line).split()
    if len(tokens) < 2:
        return False
    return tokens[1].lower() in NODE_TYPES and len(tokens) < 8


def is_number(value):
    try:
        float(value)
    except ValueError:
        return False
    return True


def parse_number(value):
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def convert_schneider_instance(
    input_path,
    num_vehicles=1,
    solver_runtime_seconds=10,
    solver_seed=1,
    solver_display=False,
):
    """Converts Schneider-style text data into the project's JSON schema."""

    source_path = Path(input_path)
    nodes, parameters = parse_schneider_file(source_path)
    depot_nodes = [node for node in nodes if node["type"] == "depot"]
    client_nodes = [node for node in nodes if node["type"] == "client"]
    station_nodes = [node for node in nodes if node["type"] == "station"]
    if len(depot_nodes) != 1:
        raise ValueError(
            f"Expected exactly one depot, found {len(depot_nodes)} in {source_path}"
        )

    depot = depot_nodes[0]
    battery_capacity = parameters.get("battery_capacity")
    vehicle_capacity = parameters.get("vehicle_capacity", 1_000_000)
    energy_rate = parameters.get("consumption_per_distance")
    inverse_refueling_rate = parameters.get("inverse_refueling_rate")
    average_velocity = parameters.get("average_velocity", 1)
    duration_scale = 1 / average_velocity if average_velocity else 1
    charging_rate = None
    if inverse_refueling_rate:
        charging_rate = 1 / inverse_refueling_rate

    return {
        "name": source_path.stem,
        "problem_type": "EVRPTW",
        "objective": {
            "primary": "minimize_vehicle_count",
            "secondary": "minimize_total_distance",
        },
        "distance": {
            "metric": "euclidean",
            "scale": 1,
        },
        "duration": {
            "metric": "euclidean",
            "scale": duration_scale,
        },
        "solver": {
            "name": "PyVRP",
            "runtime_seconds": solver_runtime_seconds,
            "seed": solver_seed,
            "display": solver_display,
        },
        "vehicles": {
            "num_available": num_vehicles,
            "capacity": vehicle_capacity,
            "start_depot": depot["name"],
            "end_depot": depot["name"],
            "tw_early": depot["tw_early"],
            "tw_late": depot["tw_late"],
            "battery_capacity": battery_capacity,
            "initial_battery": battery_capacity,
        },
        "depot": {
            "name": depot["name"],
            "x": depot["x"],
            "y": depot["y"],
            "tw_early": depot["tw_early"],
            "tw_late": depot["tw_late"],
        },
        "energy": {
            "consumption_per_distance": energy_rate,
            "minimum_battery": 0,
        },
        "charging": {
            "policy": "full_recharge",
            "allow_partial_recharge": True,
            "charging_rate": charging_rate,
            "fixed_service_duration": 0,
        },
        "charging_stations": [
            {
                "name": station["name"],
                "x": station["x"],
                "y": station["y"],
                "service_duration": station["service_duration"],
                "tw_early": station["tw_early"],
                "tw_late": station["tw_late"],
                "charging_rate": charging_rate,
            }
            for station in station_nodes
        ],
        "clients": [
            {
                "name": client["name"],
                "x": client["x"],
                "y": client["y"],
                "demand": client["demand"],
                "service_duration": client["service_duration"],
                "tw_early": client["tw_early"],
                "tw_late": client["tw_late"],
            }
            for client in client_nodes
        ],
    }


def write_instance_json(instance, output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        json.dump(instance, file, indent=2, ensure_ascii=False)
        file.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Schneider-style EVRP-TW text files to project JSON."
    )
    parser.add_argument("input_path")
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--vehicles", type=int, default=1)
    parser.add_argument("--runtime-seconds", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--display", action="store_true")
    args = parser.parse_args()

    instance = convert_schneider_instance(
        input_path=args.input_path,
        num_vehicles=args.vehicles,
        solver_runtime_seconds=args.runtime_seconds,
        solver_seed=args.seed,
        solver_display=args.display,
    )
    write_instance_json(instance, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
