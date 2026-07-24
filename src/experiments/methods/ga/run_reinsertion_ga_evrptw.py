"""Run the paper-inspired RI-GA on the project's EVRP-TW benchmark."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time


SRC_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(EXPERIMENTS_ROOT))

from checkers.feasibility_checker import (  # noqa: E402
    check_explicit_routes,
    print_benchmark_report,
)
from core.evrptw_fleet_policy import apply_evrptw_vehicle_limit  # noqa: E402
from core.experiment_record import (  # noqa: E402
    build_experiment_record,
    format_constraint_violations,
)
from core.instance_loader import load_instance_data  # noqa: E402
from methods.ga.reinsertion_ga import ReinsertionGA  # noqa: E402
from methods.pyvrp.evrptw_v3_repair import (  # noqa: E402
    RepairPlan,
    repair_routes_with_splitting,
)
from methods.pyvrp.parse_schneider_instance import (  # noqa: E402
    convert_schneider_instance,
)


METHOD_NAME = "Li-Zhu-Lee RI-GA + EVRP-TW partial-recharge repair"
DEFAULT_OUTPUT_DIR = SRC_ROOT / "log" / "week5" / "reinsertion-ga"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a benchmark-adapted reproduction of the remove-reinsert GA "
            "from Li, Zhu, and Lee (2023)."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schneider", type=Path)
    source.add_argument("--instance", type=Path, help="Project-schema JSON instance.")
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--population-size", type=int, default=80)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--crossover-prob", type=float, default=0.85)
    parser.add_argument("--mutation-prob", type=float, default=0.8)
    parser.add_argument("--neighbour-count", type=int, default=3)
    parser.add_argument("--max-removal-fraction", type=float, default=0.3)
    parser.add_argument("--elite-count", type=int, default=2)
    parser.add_argument(
        "--repair-candidates",
        type=int,
        default=1,
        help="Top RI-GA candidates sent to the expensive charging repair (default: 1).",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on-unsolved", action="store_true")
    return parser.parse_args()


def load_benchmark_instance(args: argparse.Namespace):
    if args.schneider is not None:
        source_path = args.schneider
        data = convert_schneider_instance(
            input_path=source_path,
            num_vehicles=args.vehicles or 1,
            solver_runtime_seconds=0,
            solver_seed=args.seed,
            solver_display=False,
        )
    else:
        source_path = args.instance
        data = json.loads(source_path.read_text(encoding="utf-8"))
        data.setdefault("solver", {})["seed"] = args.seed

    if args.vehicles is None:
        apply_evrptw_vehicle_limit(data)
    else:
        data.setdefault("vehicles", {})["num_available"] = args.vehicles
    instance = load_instance_data(data, default_name=source_path.stem)
    return instance, source_path, data


def empty_repair(reason: str) -> RepairPlan:
    return RepairPlan(
        feasible=False,
        routes=[],
        split_count=0,
        station_insertions=0,
        charging_plans=[],
        attempts=[],
        unsolved=[{"reason": reason}],
    )


def check_plan(plan: RepairPlan, instance):
    return check_explicit_routes(
        routes=plan.routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=plan.charging_plans,
    )


def solve(args: argparse.Namespace):
    if args.repair_candidates < 1:
        raise ValueError("repair_candidates must be at least 1")
    started = time.perf_counter()
    instance, source_path, instance_data = load_benchmark_instance(args)
    solver = ReinsertionGA(
        instance,
        population_size=args.population_size,
        generations=args.generations,
        crossover_probability=args.crossover_prob,
        mutation_probability=args.mutation_prob,
        neighbour_count=args.neighbour_count,
        max_removal_fraction=args.max_removal_fraction,
        elite_count=args.elite_count,
        seed=args.seed,
    )
    search = solver.solve()

    repair_attempts = []
    repaired_candidates = []
    seen_routes = set()
    for rank, candidate in enumerate(search.candidates, start=1):
        if len(repair_attempts) >= args.repair_candidates:
            break
        route_key = candidate.routes
        if not candidate.feasible or route_key in seen_routes:
            continue
        seen_routes.add(route_key)
        plan = repair_routes_with_splitting(
            [list(route) for route in candidate.routes],
            instance,
            feasibility_first=True,
        )
        report = check_plan(plan, instance)
        repair_attempts.append(
            {
                "candidate_rank": rank,
                "customer_only_distance": candidate.distance,
                "customer_route_count": len(candidate.routes),
                "repair_feasible": plan.feasible,
                "checker_feasible": report.feasible,
                "repaired_distance": report.total_distance,
                "repaired_route_count": len(plan.routes),
                "split_count": plan.split_count,
                "station_insertions": plan.station_insertions,
                "unsolved": plan.unsolved,
            }
        )
        repaired_candidates.append((plan, report, candidate))

    feasible_candidates = [
        item for item in repaired_candidates if item[0].feasible and item[1].feasible
    ]
    if feasible_candidates:
        repair_plan, report, selected = min(
            feasible_candidates, key=lambda item: item[1].total_distance
        )
    elif repaired_candidates:
        repair_plan, report, selected = repaired_candidates[0]
    else:
        repair_plan = empty_repair("no_hard_feasible_ri_ga_candidate")
        report = check_plan(repair_plan, instance)
        selected = search.best

    elapsed = time.perf_counter() - started
    status = "solved" if repair_plan.feasible and report.feasible else "unsolved"
    payload = build_payload(
        args=args,
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        search=search,
        selected=selected,
        repair_plan=repair_plan,
        report=report,
        repair_attempts=repair_attempts,
        elapsed=elapsed,
    )
    output = args.output or (DEFAULT_OUTPUT_DIR / f"{instance.name}_reinsertion_ga.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return status, output, payload, report


def build_payload(
    *,
    args,
    status,
    source_path,
    instance,
    instance_data,
    search,
    selected,
    repair_plan,
    report,
    repair_attempts,
    elapsed,
):
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
            "paper": "Li, Zhu, and Lee (2023), DOI 10.1109/TTE.2023.3237964",
        },
        "experiment_record": build_experiment_record(
            instance_name=instance.name,
            instance_size=len(instance.clients),
            method_name=METHOD_NAME,
            objective_value=report.total_distance,
            runtime_seconds=elapsed,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(repair_plan.routes),
            constraint_violations=constraint_violations,
            random_seed=args.seed,
            best_solution_found=repair_plan.routes,
            convergence_curve=list(search.convergence),
            improvement_over_time=list(search.convergence),
            generations=args.generations,
            search_steps=args.generations * args.population_size,
        ),
        "solver": {
            "method_name": METHOD_NAME,
            "baseline": "Li-Zhu-Lee-2023 RI-GA",
            "benchmark_adaptation": (
                "hard TW/capacity/fleet split decoder; Schneider linear energy; "
                "project partial-recharge repair and independent checker"
            ),
            "population_size": args.population_size,
            "generations": args.generations,
            "crossover_probability": args.crossover_prob,
            "mutation_probability": args.mutation_prob,
            "neighbour_count": args.neighbour_count,
            "max_removal_fraction": args.max_removal_fraction,
            "elite_count": args.elite_count,
            "repair_candidates": args.repair_candidates,
            "seed": args.seed,
            "elapsed_runtime_seconds": round(elapsed, 3),
        },
        "routes": [
            {
                "route_index": index,
                "visits": route,
                "charging_plan": (
                    repair_plan.charging_plans[index - 1]
                    if index - 1 < len(repair_plan.charging_plans)
                    else []
                ),
            }
            for index, route in enumerate(repair_plan.routes, start=1)
        ],
        "metrics": {
            "feasible": report.feasible,
            "vehicle_count": len(repair_plan.routes),
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
        "ri_ga": {
            "selected_customer_routes": [list(route) for route in selected.routes],
            "selected_customer_only_distance": selected.distance,
            "selected_customer_only_feasible": selected.feasible,
            "convergence": list(search.convergence),
            "paper_operator_mapping": {
                "initialization": "randomized k-nearest-neighbour traversal",
                "selection": "roulette-wheel selection",
                "crossover": "complete route fragment grafted to second parent",
                "removal": "adaptive related removal",
                "reinsertion": "minimum linear-energy increment under hard constraints",
            },
        },
        "repair": {
            "feasible": repair_plan.feasible,
            "policy": "v3_partial_recharge_label_setting_feasibility_first",
            "split_count": repair_plan.split_count,
            "station_insertions": repair_plan.station_insertions,
            "attempts": repair_plan.attempts,
            "candidate_attempts": repair_attempts,
            "unsolved": repair_plan.unsolved,
        },
        "violations": [asdict(violation) for violation in report.violations],
        "report": asdict(report),
        "instance": instance_data,
    }


def main() -> int:
    args = parse_args()
    status, output, payload, report = solve(args)
    print("Benchmark-adapted Li-Zhu-Lee RI-GA")
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  output={output}")
    print(f"  customer_only_distance={payload['ri_ga']['selected_customer_only_distance']}")
    print(f"  station_insertions={payload['repair']['station_insertions']}")
    print_benchmark_report(
        report,
        runtime_seconds=payload["solver"]["elapsed_runtime_seconds"],
        seed=args.seed,
        solver=METHOD_NAME,
    )
    return 1 if args.fail_on_unsolved and status != "solved" else 0


if __name__ == "__main__":
    raise SystemExit(main())
