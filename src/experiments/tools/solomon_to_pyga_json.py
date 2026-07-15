"""Convert Solomon/Holmberger text instances for py-ga-VRPTW custom input."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PY_GA_ROOT = REPO_ROOT / "py-ga-VRPTW"
DEFAULT_OUTPUT_DIR = PY_GA_ROOT / "data" / "json_customize"


def parse_solomon_rows(path: Path) -> tuple[str, int, float, list[dict]]:
    name = path.stem
    vehicles = None
    capacity = None
    rows: list[dict] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    for idx, raw_line in enumerate(lines):
        parts = raw_line.split()
        if len(parts) == 2 and all(is_number(part) for part in parts):
            prev = lines[idx - 1].upper() if idx > 0 else ""
            if "CAPACITY" in prev:
                vehicles = int(float(parts[0]))
                capacity = float(parts[1])
                continue

        if len(parts) == 7 and parts[0].lstrip("-").isdigit():
            rows.append(
                {
                    "id": int(parts[0]),
                    "coordinates": {
                        "x": float(parts[1]),
                        "y": float(parts[2]),
                    },
                    "demand": float(parts[3]),
                    "ready_time": float(parts[4]),
                    "due_time": float(parts[5]),
                    "service_time": float(parts[6]),
                }
            )

    if vehicles is None or capacity is None:
        raise ValueError(f"Could not parse VEHICLE block from {path}")
    if not rows or rows[0]["id"] != 0:
        raise ValueError(f"Could not parse depot row cust_no=0 from {path}")
    return name, vehicles, capacity, rows


def is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def distance(left: dict, right: dict) -> float:
    return math.dist(
        (left["coordinates"]["x"], left["coordinates"]["y"]),
        (right["coordinates"]["x"], right["coordinates"]["y"]),
    )


def convert(path: Path) -> dict:
    name, vehicles, capacity, rows = parse_solomon_rows(path)
    depot = rows[0]
    customers = rows[1:]
    expected_ids = list(range(1, len(customers) + 1))
    actual_ids = [customer["id"] for customer in customers]
    if actual_ids != expected_ids:
        raise ValueError(
            "py-ga-VRPTW expects contiguous customer ids 1..N; "
            f"got first ids {actual_ids[:10]} from {path}"
        )

    data = {
        "instance_name": name,
        "max_vehicle_number": vehicles,
        "vehicle_capacity": capacity,
        "depart": strip_id(depot),
    }
    for customer in customers:
        data[f"customer_{customer['id']}"] = strip_id(customer)

    ordered = [data["depart"], *[data[f"customer_{idx}"] for idx in expected_ids]]
    data["distance_matrix"] = [
        [distance(from_node, to_node) for to_node in ordered]
        for from_node in ordered
    ]
    return data


def strip_id(row: dict) -> dict:
    return {
        "coordinates": row["coordinates"],
        "demand": row["demand"],
        "ready_time": row["ready_time"],
        "due_time": row["due_time"],
        "service_time": row["service_time"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Solomon/Holmberger text into py-ga-VRPTW custom JSON."
    )
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--output", "-o", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = convert(args.input_path)
    output = args.output or (DEFAULT_OUTPUT_DIR / f"{data['instance_name']}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")
    print(f"pyga_json: {output}")
    print(f"customers: {len(data) - 5}")
    print(f"distance_matrix_size: {len(data['distance_matrix'])}x{len(data['distance_matrix'][0])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
