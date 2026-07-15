"""CLI for the Schneider et al. (2014) Part 4 VNS/TS baseline."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
DEFAULT_RESULTS_DIR = SRC_ROOT / "log" / "week4" / "vns-ts-comparison"

sys.path.insert(0, str(EXPERIMENTS_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from core.experiment_record import build_experiment_record, format_constraint_violations  # noqa: E402
from checkers.feasibility_checker import check_explicit_routes, print_benchmark_report  # noqa: E402
from core.instance_loader import load_instance_data  # noqa: E402
from methods.pyvrp.parse_schneider_instance import convert_schneider_instance  # noqa: E402
from methods.vns_ts.schneider_vns_ts import SchneiderVNSTS, SearchConfig  # noqa: E402
from tools.solomon_to_project_instance import convert_solomon_instance  # noqa: E402


METHOD_NAME = "Schneider-2014 hybrid VNS/TS E-VRPTW"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Schneider, Stenger, and Goeke (2014) Part 4 hybrid "
            "VNS/TS baseline. Charging stations are searched directly; no "
            "external route repair is used."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--instance", type=Path, help="Project JSON instance.")
    source.add_argument("--schneider", type=Path, help="Schneider E-VRPTW text instance.")
    source.add_argument("--solomon", type=Path, help="Solomon/Holmberger VRPTW text instance.")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--vehicles", type=int, default=None, help="Maximum vehicle count.")
    parser.add_argument("--initial-vehicles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--initial-order", choices=("tw_sweep", "sweep"), default=None, help=argparse.SUPPRESS)

    # Backward-compatible names from the former repair baseline. They now map
    # to the paper's outer VNS and inner TS iteration counts.
    parser.add_argument("--iterations", type=int, default=80, help="Default VNS phase budget.")
    parser.add_argument(
        "--neighbors-per-iteration",
        type=int,
        default=20,
        help="Deprecated alias for --tabu-iterations.",
    )
    parser.add_argument("--tabu-size", type=int, default=None, help=argparse.SUPPRESS)

    parser.add_argument("--feasibility-iterations", type=int, default=None)
    parser.add_argument("--distance-iterations", type=int, default=None)
    parser.add_argument("--tabu-iterations", type=int, default=None)
    parser.add_argument("--max-candidate-moves", type=int, default=250)
    parser.add_argument("--candidate-list-size", type=int, default=12)
    parser.add_argument("--station-candidates-per-arc", type=int, default=3)
    parser.add_argument("--tabu-tenure-min", type=int, default=5)
    parser.add_argument("--tabu-tenure-max", type=int, default=15)
    parser.add_argument("--penalty-initial", type=float, default=1.0)
    parser.add_argument("--penalty-min", type=float, default=0.01)
    parser.add_argument("--penalty-max", type=float, default=10_000.0)
    parser.add_argument("--penalty-factor", type=float, default=1.2)
    parser.add_argument("--penalty-update-interval", type=int, default=5)
    parser.add_argument("--diversification-lambda", type=float, default=0.01)
    parser.add_argument("--sa-worsening-fraction", type=float, default=0.04)
    parser.add_argument("--time-limit-seconds", type=float, default=None)
    parser.add_argument("--progress-interval", type=int, default=1)
    parser.add_argument("--fail-on-unsolved", action="store_true")
    return parser.parse_args(argv)


def load_full_instance(args: argparse.Namespace):
    if args.solomon is not None:
        source_path = args.solomon
        data = convert_solomon_instance(
            input_path=args.solomon,
            num_vehicles=args.vehicles or 100,
            solver_runtime_seconds=0,
            solver_seed=args.seed,
            solver_display=False,
        )
    elif args.schneider is not None:
        source_path = args.schneider
        data = convert_schneider_instance(
            input_path=args.schneider,
            num_vehicles=args.vehicles or 100,
            solver_runtime_seconds=0,
            solver_seed=args.seed,
            solver_display=False,
        )
    else:
        source_path = args.instance
        with args.instance.open(encoding="utf-8") as file:
            data = json.load(file)
        data.setdefault("solver", {})["seed"] = args.seed
        data.setdefault("solver", {})["display"] = False
        if args.vehicles is not None:
            data.setdefault("vehicles", {})["num_available"] = args.vehicles

    # Part 4 assumes complete recharge. This is an algorithm setting, even if
    # a generic project JSON advertises partial-recharge support.
    data.setdefault("charging", {})["policy"] = "full_recharge"
    data["charging"]["allow_partial_recharge"] = False
    return load_instance_data(data, default_name=source_path.stem), source_path, data


def make_config(args: argparse.Namespace, instance) -> SearchConfig:
    tabu_max = args.tabu_tenure_max
    if args.tabu_size is not None:
        tabu_max = max(args.tabu_tenure_min, args.tabu_size)
    return SearchConfig(
        seed=args.seed,
        max_vehicles=instance.num_vehicles,
        initial_vehicles=args.initial_vehicles,
        feasibility_iterations=(
            args.feasibility_iterations
            if args.feasibility_iterations is not None
            else args.iterations
        ),
        distance_iterations=(
            args.distance_iterations
            if args.distance_iterations is not None
            else args.iterations
        ),
        tabu_iterations=(
            args.tabu_iterations
            if args.tabu_iterations is not None
            else args.neighbors_per_iteration
        ),
        max_candidate_moves=args.max_candidate_moves,
        candidate_list_size=args.candidate_list_size,
        station_candidates_per_arc=args.station_candidates_per_arc,
        tabu_tenure_min=args.tabu_tenure_min,
        tabu_tenure_max=tabu_max,
        penalty_initial=args.penalty_initial,
        penalty_min=args.penalty_min,
        penalty_max=args.penalty_max,
        penalty_factor=args.penalty_factor,
        penalty_update_interval=args.penalty_update_interval,
        diversification_lambda=args.diversification_lambda,
        sa_worsening_fraction=args.sa_worsening_fraction,
        time_limit_seconds=args.time_limit_seconds,
        progress_interval=args.progress_interval,
    )


def solve(args: argparse.Namespace):
    started = time.perf_counter()
    instance, source_path, instance_data = load_full_instance(args)
    config = make_config(args, instance)
    result = SchneiderVNSTS(instance, config).run()
    elapsed = time.perf_counter() - started
    routes = [list(route) for route in result.best.routes if route]
    report = check_explicit_routes(
        routes=routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=None,
    )
    status = "solved" if report.feasible else "unsolved"
    payload = build_payload(
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        args=args,
        config=config,
        result=result,
        report=report,
        elapsed_runtime_seconds=elapsed,
    )
    output_path = resolve_output_path(args.output, instance.name)
    write_solution(payload, output_path)
    return status, output_path, payload, report


def resolve_output_path(output: Path | None, instance_name: str) -> Path:
    if output is not None:
        return output
    return DEFAULT_RESULTS_DIR / f"{instance_name}_vns_ts_solution.json"


def build_payload(
    *,
    status: str,
    source_path: Path,
    instance,
    instance_data: dict,
    args: argparse.Namespace,
    config: SearchConfig,
    result,
    report,
    elapsed_runtime_seconds: float,
) -> dict:
    routes = [list(route) for route in result.best.routes if route]
    constraint_violations = format_constraint_violations(
        {
            "missing_customers": len(report.missing_customers),
            "duplicate_customers": len(report.duplicate_customers),
            "time_window_violations": report.time_window_violations,
            "capacity_violations": report.capacity_violations,
            "energy_violations": report.energy_violations,
            "vehicle_limit_violations": report.vehicle_limit_violations,
        }
    )
    return {
        "status": status,
        "source": {
            "path": str(source_path),
            "instance": instance.name,
            "problem_type": instance.problem_type,
            "paper": "Schneider, Stenger, and Goeke (2014), Part 4",
        },
        "experiment_record": build_experiment_record(
            instance_name=instance.name,
            instance_size=len(instance.clients),
            method_name=METHOD_NAME,
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(routes),
            constraint_violations=constraint_violations,
            random_seed=args.seed,
            best_solution_found=routes,
            reference_value=instance_data.get("source", {}).get("known_cost"),
            convergence_curve=result.history,
            improvement_over_time=result.history,
            iterations=result.outer_iterations,
            search_steps=result.evaluated_moves,
        ),
        "solver": {
            "method_name": METHOD_NAME,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "seed": args.seed,
            "outer_iterations": result.outer_iterations,
            "tabu_steps": result.tabu_steps,
            "evaluated_moves": result.evaluated_moves,
            "stopped_by_time_limit": result.stopped_by_time_limit,
            "preprocessed_infeasible_arcs": result.removed_arc_count,
            "repair_used": False,
            "recharge_policy": "full_recharge",
        },
        "algorithm": {
            "vns": "15 cyclic-exchange neighborhoods (#routes=2..4, max chain=1..5)",
            "tabu_neighborhood": ["2-opt*", "relocate", "exchange", "stationInRe"],
            "acceptance": "simulated_annealing_linear_cooling",
            "tabu_attribute": "deleted_arc_with_route_and_station_boundaries",
            "generalized_cost": "distance + alpha*capacity + beta*time_window + gamma*battery + diversification",
            "configuration": asdict(config),
            "final_penalty_weights": asdict(result.final_weights),
            "preprocessed_infeasible_arcs": result.removed_arc_count,
        },
        "routes": [
            {"route_index": index, "visits": route, "charging_policy": "full_recharge"}
            for index, route in enumerate(routes, start=1)
        ],
        "metrics": {
            "feasible": report.feasible,
            "vehicle_count": len(routes),
            "total_distance": report.total_distance,
            "total_duration": report.total_duration,
            "makespan": report.makespan,
            "served_customers": report.served_customers,
            "missing_customers": len(report.missing_customers),
            "duplicate_customers": len(report.duplicate_customers),
            "time_window_violations": report.time_window_violations,
            "capacity_violations": report.capacity_violations,
            "energy_violations": report.energy_violations,
            "vehicle_limit_violations": report.vehicle_limit_violations,
            "charging_count": report.charging_count,
            "charging_time": report.charging_time,
        },
        "generalized_evaluation": {
            "feasible": result.best.feasible,
            "distance": result.best.distance,
            "capacity_violation": result.best.capacity_violation,
            "time_window_violation": result.best.time_window_violation,
            "battery_violation": result.best.battery_violation,
        },
        "repair": {
            "used": False,
            "reason": "Part 4 searches station visits directly with stationInRe.",
        },
        "search_history": result.history,
        "violations": [asdict(violation) for violation in report.violations],
        "report": asdict(report),
        "instance": instance_data,
    }


def write_solution(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def print_summary(status: str, output_path: Path, payload: dict, report) -> None:
    print(METHOD_NAME)
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  output={output_path}")
    print(f"  vehicles={payload['metrics']['vehicle_count']}")
    print(f"  distance={payload['metrics']['total_distance']}")
    print(f"  evaluated_moves={payload['solver']['evaluated_moves']}")
    print_benchmark_report(
        report,
        runtime_seconds=payload["solver"]["elapsed_runtime_seconds"],
        seed=payload["solver"]["seed"],
        solver=METHOD_NAME,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status, output_path, payload, report = solve(args)
    print_summary(status, output_path, payload, report)
    if args.fail_on_unsolved and status != "solved":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
