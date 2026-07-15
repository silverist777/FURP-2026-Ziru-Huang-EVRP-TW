"""Build a PyVRP VRPTW table and shared Solomon comparison cases.

The retained POMO comparison path uses the upstream yd-kwon/POMO CVRP
checkpoint in `cvrp_method_comparison.py` or `ydkwon_pomo_method_comparison.py`.
This module no longer contains the old random-initialized RL4CO POMO baseline.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import time
from dataclasses import dataclass, replace
from pathlib import Path

from pyvrp import Model
from pyvrp.stop import MaxRuntime

from core.experiment_record import (
    CORE_RECORD_FIELDS,
    build_experiment_record,
    format_constraint_violations,
)
from core.vrptw_support import SolomonCustomer, SolomonInstance, parse_solomon_instance


REPO_ROOT = Path(__file__).resolve().parents[4]
SCALE = 10
DEFAULT_OUTPUT_DIR = REPO_ROOT / "src" / "log" / "week2" / "method-comparison"
DEFAULT_SOLOMON = REPO_ROOT / "src" / "data" / "Solomon" / "C101.txt"
DEFAULT_HOLMBERGER = REPO_ROOT / "src" / "data" / "Holmberger" / "C1_2_1.txt"


@dataclass(frozen=True)
class ExperimentCase:
    label: str
    source: str
    client_count: int
    instance: SolomonInstance
    selected_cust_no: list[int]


def scaled(value: float) -> int:
    return int(round(value * SCALE))


def euclidean(a: SolomonCustomer, b: SolomonCustomer) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def sample_instance(
    base: SolomonInstance,
    client_count: int,
    seed: int,
    source_label: str,
) -> ExperimentCase:
    rng = random.Random(seed + client_count)
    if client_count < base.num_clients:
        selected = sorted(rng.sample([c.cust_no for c in base.customers], client_count))
        customers = [customer for customer in base.customers if customer.cust_no in selected]
    else:
        selected = [customer.cust_no for customer in base.customers]
        customers = list(base.customers)

    instance = replace(
        base,
        name=f"{base.name}_{client_count}",
        customers=customers,
        known_cost=None,
        solution_path=None,
    )
    return ExperimentCase(
        label=instance.name,
        source=source_label,
        client_count=client_count,
        instance=instance,
        selected_cust_no=selected,
    )


def build_cases(solomon_path: Path, holmberger_path: Path, seed: int) -> list[ExperimentCase]:
    solomon = parse_solomon_instance(solomon_path)
    holmberger = parse_solomon_instance(holmberger_path)
    cases = [
        sample_instance(solomon, 20, seed, f"Solomon {solomon_path.name}"),
        sample_instance(solomon, 50, seed, f"Solomon {solomon_path.name}"),
        sample_instance(solomon, 100, seed, f"Solomon {solomon_path.name}"),
    ]
    cases.append(
        ExperimentCase(
            label=holmberger.name,
            source=f"Holmberger {holmberger_path.name}",
            client_count=holmberger.num_clients,
            instance=holmberger,
            selected_cust_no=[customer.cust_no for customer in holmberger.customers],
        )
    )
    return cases


def write_case_instance(case: ExperimentCase, output_dir: Path) -> Path:
    path = output_dir / f"{case.label}.txt"
    instance = case.instance
    rows = [instance.depot, *instance.customers]
    with path.open("w", encoding="utf-8") as file:
        file.write(f"{case.label}\n\n")
        file.write("VEHICLE\n")
        file.write("NUMBER     CAPACITY\n")
        file.write(f"{instance.vehicles:4d}{int(instance.capacity):12d}\n\n")
        file.write("CUSTOMER\n")
        file.write(
            "CUST NO.  XCOORD.    YCOORD.    DEMAND   READY TIME  "
            "DUE DATE   SERVICE TIME\n"
        )
        file.write(" \n")
        for row in rows:
            file.write(
                f"{row.cust_no:5d}"
                f"{row.x:10.0f}"
                f"{row.y:11.0f}"
                f"{row.demand:11.0f}"
                f"{row.ready_time:11.0f}"
                f"{row.due_time:11.0f}"
                f"{row.service_time:11.0f}\n"
            )
    return path


def build_pyvrp_model(instance: SolomonInstance) -> Model:
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
            delivery=int(customer.demand),
            service_duration=scaled(customer.service_time),
            tw_early=scaled(customer.ready_time),
            tw_late=scaled(customer.due_time),
            name=str(customer.cust_no),
        )
        for customer in instance.customers
    ]
    model.add_vehicle_type(
        num_available=instance.vehicles,
        capacity=int(instance.capacity),
        start_depot=depot,
        end_depot=depot,
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
    )

    original_locations = [instance.depot, *instance.customers]
    pyvrp_locations = [depot, *clients]
    for frm_idx, frm in enumerate(pyvrp_locations):
        for to_idx, to in enumerate(pyvrp_locations):
            if frm is to:
                continue
            distance = scaled(euclidean(original_locations[frm_idx], original_locations[to_idx]))
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


def make_row(
    method: str,
    case: ExperimentCase,
    objective: float,
    feasible: bool,
    runtime: float,
    details: str,
    seed: int,
    model_status: str,
    vehicles_used: int | None,
    constraint_violations: str,
    best_solution_found: object,
    convergence_curve: object = None,
    improvement_over_time: object = None,
    iterations: int | None = None,
    generations: int | None = None,
    search_steps: int | None = None,
) -> dict[str, object]:
    selected = (
        ",".join(str(num) for num in case.selected_cust_no)
        if case.client_count < 100
        else f"all customers 1-{case.client_count}"
    )
    feasibility_status = (
        "feasible; E disabled; TW and capacity enforced"
        if feasible
        else "infeasible; E disabled; TW and capacity enforced"
    )
    row = build_experiment_record(
        instance_name=case.label,
        instance_size=case.client_count,
        method_name=method,
        objective_value=objective,
        runtime_seconds=runtime,
        feasibility_status=feasibility_status,
        vehicles_used=vehicles_used,
        constraint_violations=constraint_violations,
        random_seed=seed,
        best_solution_found=best_solution_found,
        reference_value=case.instance.known_cost,
        convergence_curve=convergence_curve,
        improvement_over_time=improvement_over_time,
        iterations=iterations,
        generations=generations,
        search_steps=search_steps,
    )
    row.update({
        "method": method,
        "clients": case.client_count,
        "instance": case.label,
        "source": case.source,
        "selected_cust_no": selected,
        "objective_value": round(objective, 3),
        "feasibility_status_under_added_constraints": feasibility_status,
        "runtime_seconds": round(runtime, 3),
        "convergence_details": details,
        "seed": seed,
        "model_status": model_status,
    })
    return row


def evaluate_pyvrp(case: ExperimentCase, runtime_seconds: int, seed: int) -> dict[str, object]:
    started = time.perf_counter()
    model = build_pyvrp_model(case.instance)
    result = model.solve(MaxRuntime(runtime_seconds), seed=seed, display=False)
    elapsed = time.perf_counter() - started
    solution = result.best
    objective = solution.distance() / SCALE
    feasible = solution.is_feasible()
    routes = pyvrp_routes(solution, case.instance)
    excess_load = list(solution.excess_load())
    constraint_violations = format_constraint_violations(
        {
            "time_warp": round(solution.time_warp() / SCALE, 3),
            "excess_load": excess_load,
        }
    )
    details = (
        f"MaxRuntime={runtime_seconds}s; routes={solution.num_routes()}; "
        f"time_warp={solution.time_warp() / SCALE:.1f}; "
        f"excess_load={excess_load}"
    )
    return make_row(
        method="PYVRP",
        case=case,
        objective=objective,
        feasible=feasible,
        runtime=elapsed,
        details=details,
        seed=seed,
        model_status="exact checkpoint not applicable",
        vehicles_used=solution.num_routes(),
        constraint_violations=constraint_violations,
        best_solution_found=routes,
        convergence_curve="not captured by PyVRP API",
        improvement_over_time="not captured by PyVRP API",
        search_steps=None,
    )


def write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    headers = [
        *CORE_RECORD_FIELDS,
        "source",
        "selected_cust_no",
        "model_status",
        "convergence_details",
    ]
    with path.open("w", encoding="utf-8") as file:
        file.write("# PyVRP Method Comparison and Record\n\n")
        file.write(
            "Electric-vehicle constraints are disabled. Time windows and capacity "
            "are enforced by PyVRP.\n\n"
        )
        file.write("| " + " | ".join(headers) + " |\n")
        file.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for row in rows:
            values = [str(row[header]).replace("|", "\\|") for header in headers]
            file.write("| " + " | ".join(values) + " |\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a PYVRP comparison table.")
    parser.add_argument("--solomon", type=Path, default=DEFAULT_SOLOMON)
    parser.add_argument("--holmberger", type=Path, default=DEFAULT_HOLMBERGER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--pyvrp-runtime-seconds", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = build_cases(args.solomon, args.holmberger, args.seed)

    rows = [
        evaluate_pyvrp(case, args.pyvrp_runtime_seconds, args.seed)
        for case in cases
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    instance_dir = args.output_dir / "instances"
    instance_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        write_case_instance(case, instance_dir)
    csv_path = args.output_dir / "method_comparison_table.csv"
    md_path = args.output_dir / "method_comparison_table.md"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(rows, md_path)

    print("method_comparison_ok: True")
    print(f"csv: {csv_path}")
    print(f"markdown: {md_path}")
    for row in rows:
        print(
            f"{row['method']} clients={row['clients']} "
            f"objective={row['objective_value']} runtime={row['runtime_seconds']} "
            f"{row['feasibility_status_under_added_constraints']}"
        )


if __name__ == "__main__":
    main()
