"""Convert Solomon/Holmberger VRPTW text data to the project instance schema.

The Week 4 comparison uses C101 and R1_10_9.txt, which are Solomon-style
VRPTW files. They do not contain EV charging stations or battery parameters, so
the converted instance keeps energy disabled while still using the shared
EVRP-TW repair/checker interface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vrptw_support import SolomonCustomer, parse_solomon_instance


def convert_solomon_instance(
    input_path: Path,
    num_vehicles: int | None = None,
    solver_runtime_seconds: int = 10,
    solver_seed: int = 1,
    solver_display: bool = False,
) -> dict:
    instance = parse_solomon_instance(Path(input_path))
    depot = instance.depot
    vehicles = instance.vehicles if num_vehicles is None else num_vehicles

    return {
        "name": instance.name,
        "problem_type": "VRPTW",
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
            "scale": 1,
        },
        "solver": {
            "runtime_seconds": solver_runtime_seconds,
            "seed": solver_seed,
            "display": solver_display,
        },
        "vehicles": {
            "num_available": vehicles,
            "capacity": instance.capacity,
            "start_depot": "D0",
            "end_depot": "D0",
            "tw_early": depot.ready_time,
            "tw_late": depot.due_time,
            "battery_capacity": None,
            "initial_battery": None,
        },
        "depot": {
            "name": "D0",
            "x": depot.x,
            "y": depot.y,
            "tw_early": depot.ready_time,
            "tw_late": depot.due_time,
        },
        "energy": {
            "consumption_per_distance": None,
            "minimum_battery": None,
        },
        "charging": {
            "policy": "none",
            "allow_partial_recharge": False,
            "charging_rate": None,
            "fixed_service_duration": 0,
        },
        "charging_stations": [],
        "clients": [convert_customer(customer) for customer in instance.customers],
        "source": {
            "format": "Solomon/Holmberger VRPTW",
            "path": str(Path(input_path)),
            "known_cost": instance.known_cost,
        },
    }


def convert_customer(customer: SolomonCustomer) -> dict:
    return {
        "name": f"C{customer.cust_no}",
        "x": customer.x,
        "y": customer.y,
        "demand": customer.demand,
        "service_duration": customer.service_time,
        "tw_early": customer.ready_time,
        "tw_late": customer.due_time,
        "source_customer_id": customer.cust_no,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Solomon/Holmberger VRPTW text into project JSON."
    )
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--runtime-seconds", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--display", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = convert_solomon_instance(
        input_path=args.input_path,
        num_vehicles=args.vehicles,
        solver_runtime_seconds=args.runtime_seconds,
        solver_seed=args.seed,
        solver_display=args.display,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")
    print(f"converted_instance: {args.output}")
    print(f"clients: {len(data['clients'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
