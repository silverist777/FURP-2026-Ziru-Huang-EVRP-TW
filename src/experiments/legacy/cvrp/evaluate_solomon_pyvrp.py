"""Evaluate PyVRP on Solomon-style VRPTW test sets.

This benchmark intentionally ignores electric-vehicle constraints: there is no
battery, charging station, charging time, or energy feasibility check. The model
is plain VRPTW with capacity and time-window constraints.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from pyvrp import Model
from pyvrp.stop import MaxRuntime


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = REPO_ROOT / "src" / "data" / "Solomon"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "src"
    / "log"
    / "week1"
    / "pyvrp-solomon-eval"
    / "pyvrp_solomon_eval_results.csv"
)
SCALE = 10

sys.path.insert(0, str(REPO_ROOT / "src" / "experiments"))

from core.experiment_record import (  # noqa: E402
    build_experiment_record,
    format_constraint_violations,
)


@dataclass(frozen=True)
class SolomonCustomer:
    cust_no: int
    x: float
    y: float
    demand: int
    ready_time: float
    due_time: float
    service_time: float


@dataclass(frozen=True)
class SolomonInstance:
    name: str
    path: Path
    vehicles: int
    capacity: int
    depot: SolomonCustomer
    customers: list[SolomonCustomer]
    known_cost: float | None


def scaled(value: float) -> int:
    return int(round(value * SCALE))


def parse_known_cost(path: Path) -> float | None:
    solution_path = path.with_suffix(".sol")
    if not solution_path.exists():
        return None

    for raw_line in solution_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("Cost"):
            return float(line.split()[-1])
    return None


def parse_solomon_instance(path: Path) -> SolomonInstance:
    vehicles = None
    capacity = None
    rows: list[SolomonCustomer] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    for idx, raw_line in enumerate(lines):
        parts = raw_line.split()
        if len(parts) == 2 and all(part.replace(".", "", 1).isdigit() for part in parts):
            prev = lines[idx - 1].upper() if idx > 0 else ""
            if "CAPACITY" in prev:
                vehicles = int(float(parts[0]))
                capacity = int(float(parts[1]))
                continue

        if len(parts) == 7 and parts[0].lstrip("-").isdigit():
            rows.append(
                SolomonCustomer(
                    cust_no=int(parts[0]),
                    x=float(parts[1]),
                    y=float(parts[2]),
                    demand=int(float(parts[3])),
                    ready_time=float(parts[4]),
                    due_time=float(parts[5]),
                    service_time=float(parts[6]),
                )
            )

    if vehicles is None or capacity is None:
        raise ValueError(f"Could not parse VEHICLE block from {path}")
    if not rows or rows[0].cust_no != 0:
        raise ValueError(f"Could not parse depot row cust_no=0 from {path}")

    return SolomonInstance(
        name=path.stem,
        path=path,
        vehicles=vehicles,
        capacity=capacity,
        depot=rows[0],
        customers=rows[1:],
        known_cost=parse_known_cost(path),
    )


def load_instances(
    data_dir: Path,
    instance_name: str | None,
    limit: int | None,
) -> list[SolomonInstance]:
    paths = sorted(data_dir.glob("*.txt"))
    if instance_name is not None:
        paths = [path for path in paths if path.stem == instance_name]
    if limit is not None:
        paths = paths[:limit]
    return [parse_solomon_instance(path) for path in paths]


def euclidean(a: SolomonCustomer, b: SolomonCustomer) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def build_model(instance: SolomonInstance) -> Model:
    model = Model()
    depot = model.add_depot(
        x=scaled(instance.depot.x),
        y=scaled(instance.depot.y),
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
        name=str(instance.depot.cust_no),
    )
    clients = [
        model.add_client(
            x=scaled(customer.x),
            y=scaled(customer.y),
            delivery=customer.demand,
            service_duration=scaled(customer.service_time),
            tw_early=scaled(customer.ready_time),
            tw_late=scaled(customer.due_time),
            name=str(customer.cust_no),
        )
        for customer in instance.customers
    ]

    model.add_vehicle_type(
        num_available=instance.vehicles,
        capacity=instance.capacity,
        start_depot=depot,
        end_depot=depot,
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
    )

    locations = [instance.depot, *instance.customers]
    pyvrp_locations = [depot, *clients]
    for frm_idx, frm in enumerate(pyvrp_locations):
        for to_idx, to in enumerate(pyvrp_locations):
            if frm is to:
                continue
            distance = scaled(euclidean(locations[frm_idx], locations[to_idx]))
            model.add_edge(frm, to, distance=distance, duration=distance)

    return model


def pyvrp_routes(solution, instance: SolomonInstance) -> list[list[int]]:
    customer_by_index = {
        idx: customer.cust_no for idx, customer in enumerate(instance.customers, start=1)
    }
    return [
        [customer_by_index.get(customer_idx, customer_idx) for customer_idx in route.visits()]
        for route in solution.routes()
    ]


def evaluate_instance(instance: SolomonInstance, runtime_seconds: int, seed: int) -> dict:
    started = time.perf_counter()
    model = build_model(instance)
    result = model.solve(MaxRuntime(runtime_seconds), seed=seed, display=False)
    elapsed = time.perf_counter() - started
    solution = result.best
    distance = solution.distance() / SCALE
    routes = pyvrp_routes(solution, instance)
    excess_load = list(solution.excess_load())
    constraint_violations = format_constraint_violations(
        {
            "time_warp": round(solution.time_warp() / SCALE, 3),
            "excess_load": excess_load,
        }
    )
    gap_pct = (
        None
        if instance.known_cost in (None, 0)
        else (distance - instance.known_cost) / instance.known_cost * 100.0
    )

    row = build_experiment_record(
        instance_name=instance.name,
        instance_size=len(instance.customers),
        method_name="PyVRP VRPTW",
        objective_value=distance,
        runtime_seconds=elapsed,
        feasibility_status="feasible" if solution.is_feasible() else "infeasible",
        vehicles_used=solution.num_routes(),
        constraint_violations=constraint_violations,
        random_seed=seed,
        best_solution_found=routes,
        reference_value=instance.known_cost,
        convergence_curve="not captured by PyVRP API",
        improvement_over_time="not captured by PyVRP API",
        search_steps=None,
    )
    row.update({
        "instance": instance.name,
        "clients": len(instance.customers),
        "vehicles_available": instance.vehicles,
        "vehicles_used": solution.num_routes(),
        "known_cost": instance.known_cost,
        "pyvrp_distance": distance,
        "gap_pct": gap_pct,
        "is_feasible": solution.is_feasible(),
        "time_warp": solution.time_warp() / SCALE,
        "excess_load": excess_load,
        "runtime_seconds": round(elapsed, 3),
        "runtime_limit_seconds": runtime_seconds,
        "seed": seed,
        "electric_constraints": "disabled",
    })
    return row


def summarize(rows: list[dict]) -> dict[str, float | int | None]:
    gaps = [row["gap_pct"] for row in rows if row["gap_pct"] is not None]
    return {
        "evaluated_instances": len(rows),
        "feasible_instances": sum(1 for row in rows if row["is_feasible"]),
        "mean_gap_pct": sum(gaps) / len(gaps) if gaps else None,
        "min_gap_pct": min(gaps) if gaps else None,
        "max_gap_pct": max(gaps) if gaps else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PyVRP on Solomon VRPTW.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--instance", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--runtime-seconds", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def format_optional_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def main() -> None:
    args = parse_args()
    instances = load_instances(args.data_dir, args.instance, args.limit)
    if not instances:
        raise RuntimeError(f"No Solomon .txt instances found in {args.data_dir}")

    print("PyVRP Solomon VRPTW evaluation")
    print("=============================")
    print(f"data_dir: {args.data_dir}")
    print(f"instances: {len(instances)}")
    print("electric_constraints: disabled")

    rows = []
    for instance in instances:
        row = evaluate_instance(instance, args.runtime_seconds, args.seed)
        rows.append(row)
        gap = "n/a" if row["gap_pct"] is None else f"{row['gap_pct']:.2f}%"
        print(
            f"{row['instance']}: known={row['known_cost']} "
            f"pyvrp={row['pyvrp_distance']:.1f} gap={gap} "
            f"vehicles={row['vehicles_used']} feasible={row['is_feasible']} "
            f"time_warp={row['time_warp']:.1f} excess_load={row['excess_load']}"
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows)
    print("summary")
    print("-------")
    print(f"results_csv: {args.output_csv}")
    print(f"evaluated_instances: {summary['evaluated_instances']}")
    print(f"feasible_instances: {summary['feasible_instances']}")
    print(f"mean_gap_pct: {format_optional_pct(summary['mean_gap_pct'])}")
    print(f"min_gap_pct: {format_optional_pct(summary['min_gap_pct'])}")
    print(f"max_gap_pct: {format_optional_pct(summary['max_gap_pct'])}")
    print("evaluation_ok: True")


if __name__ == "__main__":
    main()
