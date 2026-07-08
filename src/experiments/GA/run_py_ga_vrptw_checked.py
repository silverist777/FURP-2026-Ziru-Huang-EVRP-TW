"""Run py-ga-VRPTW and validate its final route with the shared checker."""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import io
import json
import random
import re
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
PY_GA_ROOT = REPO_ROOT / "py-ga-VRPTW"
DEFAULT_RESULTS_DIR = SRC_ROOT / "results" / "week4_vns_ts_comparison"

sys.path.insert(0, str(EXPERIMENTS_ROOT))
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(PY_GA_ROOT))

from experiment_record import build_experiment_record, format_constraint_violations  # noqa: E402
from feasibility_checker import check_explicit_routes, print_benchmark_report  # noqa: E402
from instance_loader import load_instance_data  # noqa: E402
from solomon_to_project_instance import convert_solomon_instance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run external py-ga-VRPTW and emit a checked Week 4 JSON."
    )
    parser.add_argument("--solomon", type=Path, required=True)
    parser.add_argument("--instance", default=None)
    parser.add_argument("--ind-size", type=int, required=True)
    parser.add_argument("--pop-size", type=int, default=80)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--unit-cost", type=float, default=8.0)
    parser.add_argument("--init-cost", type=float, default=100.0)
    parser.add_argument("--wait-cost", type=float, default=1.0)
    parser.add_argument("--delay-cost", type=float, default=1.5)
    parser.add_argument("--crossover-prob", type=float, default=0.85)
    parser.add_argument("--mutation-prob", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-log", type=Path, default=None)
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--customize-data", action="store_true")
    parser.add_argument("--fail-on-unsolved", action="store_true")
    return parser.parse_args()


def expected_py_ga_csv(args: argparse.Namespace, instance_name: str) -> Path:
    name = (
        f"{instance_name}_uC{args.unit_cost}_iC{args.init_cost}"
        f"_wC{args.wait_cost}_dC{args.delay_cost}_iS{args.ind_size}"
        f"_pS{args.pop_size}_cP{args.crossover_prob}"
        f"_mP{args.mutation_prob}_nG{args.generations}.csv"
    )
    return PY_GA_ROOT / "results" / name


def run_pyga(args: argparse.Namespace, instance_name: str) -> tuple[str, float]:
    from gavrptw.core import run_gavrptw  # noqa: PLC0415

    if args.seed is not None:
        random.seed(args.seed)

    buffer = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(buffer):
        run_gavrptw(
            instance_name=instance_name,
            unit_cost=args.unit_cost,
            init_cost=args.init_cost,
            wait_cost=args.wait_cost,
            delay_cost=args.delay_cost,
            ind_size=args.ind_size,
            pop_size=args.pop_size,
            cx_pb=args.crossover_prob,
            mut_pb=args.mutation_prob,
            n_gen=args.generations,
            export_csv=True,
            customize_data=args.customize_data,
        )
    elapsed = time.perf_counter() - started
    return buffer.getvalue(), elapsed


def parse_best_individual(stdout: str) -> list[int]:
    match = re.search(r"^Best individual:\s*(\[.*\])$", stdout, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError("Could not parse py-ga best individual from stdout.")
    value = ast.literal_eval(match.group(1))
    return [int(item) for item in value]


def parse_total_cost(stdout: str) -> float | None:
    match = re.search(r"^Total cost:\s*([0-9.eE+-]+)$", stdout, flags=re.MULTILINE)
    return None if match is None else float(match.group(1))


def load_pyga_instance(instance_name: str, customize_data: bool) -> dict:
    from gavrptw.utils import load_instance  # noqa: PLC0415

    data_dir = "json_customize" if customize_data else "json"
    path = PY_GA_ROOT / "data" / data_dir / f"{instance_name}.json"
    data = load_instance(str(path))
    if data is None:
        raise RuntimeError(f"Could not load py-ga instance JSON: {path}")
    return data


def copy_generated_csv(args: argparse.Namespace, instance_name: str) -> list[dict]:
    generated = expected_py_ga_csv(args, instance_name)
    output_csv = args.output_csv or (DEFAULT_RESULTS_DIR / f"{instance_name}_pyga.csv")
    if not generated.exists():
        raise RuntimeError(f"Expected py-ga CSV was not created: {generated}")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated, output_csv)
    generated.unlink()
    with output_csv.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def build_payload(
    *,
    args: argparse.Namespace,
    instance_name: str,
    source_path: Path,
    instance,
    instance_data: dict,
    customer_routes: list[list[str]],
    report,
    stdout: str,
    elapsed_runtime_seconds: float,
    total_cost: float | None,
    csv_rows: list[dict],
) -> dict:
    constraint_violations = format_constraint_violations(
        {
            "missing_customers": len(report.missing_customers),
            "duplicate_customers": len(report.duplicate_customers),
            "time_window_violations": report.time_window_violations,
            "capacity_violations": report.capacity_violations,
            "energy_violations": report.energy_violations,
        }
    )
    status = "solved" if report.feasible else "unsolved"
    return {
        "status": status,
        "source": {
            "path": str(source_path),
            "instance": instance.name,
            "problem_type": instance.problem_type,
        },
        "experiment_record": build_experiment_record(
            instance_name=instance.name,
            instance_size=len(instance.clients),
            method_name="py-ga-VRPTW custom + shared checker",
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(customer_routes),
            constraint_violations=constraint_violations,
            random_seed=args.seed,
            best_solution_found=customer_routes,
            reference_value=None,
            convergence_curve=csv_rows,
            improvement_over_time=csv_rows,
            generations=args.generations,
            search_steps=args.generations * args.pop_size,
        ),
        "solver": {
            "method_name": "py-ga-VRPTW custom + shared checker",
            "baseline": "py-ga-VRPTW",
            "customize_data": args.customize_data,
            "ind_size": args.ind_size,
            "pop_size": args.pop_size,
            "generations": args.generations,
            "unit_cost": args.unit_cost,
            "init_cost": args.init_cost,
            "wait_cost": args.wait_cost,
            "delay_cost": args.delay_cost,
            "crossover_prob": args.crossover_prob,
            "mutation_prob": args.mutation_prob,
            "seed": args.seed,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "pyga_total_cost": round(total_cost, 3) if total_cost is not None else None,
            "unsupported_reason": "",
        },
        "routes": [
            {
                "route_index": idx,
                "visits": route,
                "charging_plan": [],
            }
            for idx, route in enumerate(customer_routes, start=1)
        ],
        "metrics": {
            "feasible": report.feasible,
            "vehicle_count": len(customer_routes),
            "total_distance": report.total_distance,
            "total_duration": report.total_duration,
            "makespan": report.makespan,
            "served_customers": report.served_customers,
            "missing_customers": len(report.missing_customers),
            "duplicate_customers": len(report.duplicate_customers),
            "time_window_violations": report.time_window_violations,
            "capacity_violations": report.capacity_violations,
            "energy_violations": report.energy_violations,
            "charging_count": report.charging_count,
            "charging_time": report.charging_time,
        },
        "pyga": {
            "stdout": stdout,
            "csv_rows": csv_rows,
        },
        "violations": [asdict(violation) for violation in report.violations],
        "report": asdict(report),
        "instance": instance_data,
    }


def main() -> int:
    args = parse_args()
    instance_name = args.instance or args.solomon.stem
    output_json = args.output or (DEFAULT_RESULTS_DIR / f"{instance_name}_pyga_checked.json")
    output_log = args.output_log or (DEFAULT_RESULTS_DIR / f"{instance_name}_pyga.log")

    instance_data = convert_solomon_instance(
        input_path=args.solomon,
        num_vehicles=args.vehicles,
        solver_runtime_seconds=0,
        solver_seed=args.seed,
        solver_display=False,
    )
    instance = load_instance_data(instance_data, default_name=args.solomon.stem)

    stdout, elapsed = run_pyga(args, instance_name)
    best_individual = parse_best_individual(stdout)
    total_cost = parse_total_cost(stdout)
    pyga_instance = load_pyga_instance(instance_name, args.customize_data)

    from gavrptw.core import ind2route  # noqa: PLC0415

    raw_routes = ind2route(best_individual, pyga_instance)
    customer_routes = [[f"C{customer_id}" for customer_id in route] for route in raw_routes]
    report = check_explicit_routes(
        routes=customer_routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=[[] for _ in customer_routes],
    )
    csv_rows = copy_generated_csv(args, instance_name)
    payload = build_payload(
        args=args,
        instance_name=instance_name,
        source_path=args.solomon,
        instance=instance,
        instance_data=instance_data,
        customer_routes=customer_routes,
        report=report,
        stdout=stdout,
        elapsed_runtime_seconds=elapsed,
        total_cost=total_cost,
        csv_rows=csv_rows,
    )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")
    output_log.parent.mkdir(parents=True, exist_ok=True)
    output_log.write_text(stdout, encoding="utf-8")

    print("py-ga-VRPTW custom + shared checker")
    print(f"  status={payload['status']}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  output={output_json}")
    print(f"  vehicles={payload['metrics']['vehicle_count']}")
    print(f"  distance={payload['metrics']['total_distance']}")
    print(f"  served_customers={payload['metrics']['served_customers']}")
    print_benchmark_report(
        report,
        runtime_seconds=payload["solver"]["elapsed_runtime_seconds"],
        seed=args.seed,
        solver="py-ga-VRPTW custom + shared checker",
    )
    if args.fail_on_unsolved and payload["status"] != "solved":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
