import argparse
import json
import sys
import time
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(EXPERIMENTS_ROOT))

from pyvrp import Model
from pyvrp.stop import MaxRuntime

from methods.pyvrp.evrptw_v3_repair import repair_routes_with_splitting
from checkers.feasibility_checker import check_explicit_routes, print_benchmark_report
from core.instance_loader import load_instance_data
from core.experiment_record import build_experiment_record, format_constraint_violations
from methods.pyvrp.parse_schneider_instance import convert_schneider_instance
from tools.solomon_to_project_instance import convert_solomon_instance


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = ROOT / "log" / "week2" / "evrptw-pipeline"


def build_pyvrp_model(instance):
    """Builds a PyVRP VRPTW customer-routing baseline model."""

    model = Model()
    depot = model.add_depot(
        x=instance.depot.x,
        y=instance.depot.y,
        tw_early=int(round(instance.depot.tw_early)),
        tw_late=int(round(instance.depot.tw_late)),
        name=instance.depot.name,
    )
    clients = [
        model.add_client(
            x=client.x,
            y=client.y,
            delivery=int(round(client.demand)),
            service_duration=int(round(client.service_duration)),
            tw_early=int(round(client.tw_early)),
            tw_late=int(round(client.tw_late)),
            name=client.name,
        )
        for client in instance.clients
    ]

    model.add_vehicle_type(
        num_available=instance.num_vehicles,
        capacity=int(round(instance.vehicle_capacity)),
        start_depot=depot,
        end_depot=depot,
        tw_early=int(round(instance.vehicle.tw_early)),
        tw_late=int(round(instance.vehicle.tw_late)),
    )

    locations = [depot, *clients]
    for frm in locations:
        for to in locations:
            if frm is not to:
                model.add_edge(
                    frm,
                    to,
                    distance=instance.distance(frm, to),
                    duration=instance.travel_duration(frm, to),
                )

    return model


def baseline_routes_from_solution(solution, instance):
    customer_by_index = {
        idx: customer.name for idx, customer in enumerate(instance.clients, start=1)
    }
    return [
        [customer_by_index[customer_idx] for customer_idx in route.visits()]
        for route in solution.routes()
    ]


def load_pipeline_instance(args):
    if args.solomon is not None:
        data = convert_solomon_instance(
            input_path=args.solomon,
            num_vehicles=args.vehicles,
            solver_runtime_seconds=args.runtime_seconds,
            solver_seed=args.seed,
            solver_display=args.display,
        )
        source_path = Path(args.solomon)
    elif args.schneider is not None:
        data = convert_schneider_instance(
            input_path=args.schneider,
            num_vehicles=1 if args.vehicles is None else args.vehicles,
            solver_runtime_seconds=args.runtime_seconds,
            solver_seed=args.seed,
            solver_display=args.display,
        )
        source_path = Path(args.schneider)
    else:
        source_path = Path(args.instance)
        with source_path.open(encoding="utf-8") as file:
            data = json.load(file)
        apply_overrides(
            data=data,
            vehicles=args.vehicles,
            runtime_seconds=args.runtime_seconds,
            seed=args.seed,
            display=args.display,
        )

    return load_instance_data(data, default_name=source_path.stem), source_path, data


def apply_overrides(data, vehicles, runtime_seconds, seed, display):
    solver = data.setdefault("solver", {})
    solver["runtime_seconds"] = runtime_seconds
    solver["seed"] = seed
    solver["display"] = display
    if vehicles is not None:
        data.setdefault("vehicles", {})["num_available"] = vehicles


def solve_pipeline(args):
    started = time.perf_counter()
    instance, source_path, instance_data = load_pipeline_instance(args)
    output_path = resolve_output_path(args.output, instance.name)

    model = build_pyvrp_model(instance)
    result = model.solve(
        MaxRuntime(instance.solver.runtime_seconds),
        seed=instance.solver.seed,
        display=instance.solver.display,
    )
    solution = result.best
    baseline_routes = baseline_routes_from_solution(solution, instance)
    repair_plan = repair_routes_with_splitting(baseline_routes, instance)
    report = check_explicit_routes(
        routes=repair_plan.routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=repair_plan.charging_plans,
    )
    status = "solved" if repair_plan.feasible and report.feasible else "unsolved"
    elapsed_runtime_seconds = time.perf_counter() - started

    payload = build_solution_payload(
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        solution=solution,
        baseline_routes=baseline_routes,
        repair_plan=repair_plan,
        report=report,
        elapsed_runtime_seconds=elapsed_runtime_seconds,
    )
    write_solution(payload, output_path)
    return status, output_path, payload, report


def resolve_output_path(output, instance_name):
    if output is not None:
        return Path(output)
    return DEFAULT_RESULTS_DIR / f"{instance_name}_solution.json"


def build_solution_payload(
    status,
    source_path,
    instance,
    instance_data,
    solution,
    baseline_routes,
    repair_plan,
    report,
    elapsed_runtime_seconds,
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
        },
        "experiment_record": build_experiment_record(
            instance_name=instance.name,
            instance_size=len(instance.clients),
            method_name="PyVRP VRPTW + EVRP-TW station repair",
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(repair_plan.routes),
            constraint_violations=constraint_violations,
            random_seed=instance.solver.seed,
            best_solution_found=repair_plan.routes,
            reference_value=None,
            convergence_curve="not captured; repair attempts are recorded in repair.attempts",
            improvement_over_time="not captured",
            search_steps=len(repair_plan.attempts),
        ),
        "solver": {
            "baseline": "PyVRP VRPTW",
            "repair": "v3_partial_recharge_label_setting",
            "pyvrp_version": version("pyvrp"),
            "runtime_seconds": instance.solver.runtime_seconds,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "seed": instance.solver.seed,
        },
        "routes": [
            {
                "route_index": idx,
                "visits": route,
                "charging_plan": (
                    repair_plan.charging_plans[idx - 1]
                    if idx - 1 < len(repair_plan.charging_plans)
                    else []
                ),
            }
            for idx, route in enumerate(repair_plan.routes, start=1)
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
        "baseline": {
            "pyvrp_solution_feasible": solution.is_feasible(),
            "pyvrp_time_warp": solution.time_warp(),
            "customer_routes": baseline_routes,
        },
        "repair": {
            "feasible": repair_plan.feasible,
            "split_count": repair_plan.split_count,
            "station_insertions": repair_plan.station_insertions,
            "charging_plans": repair_plan.charging_plans,
            "policy": "partial_recharge",
            "attempts": repair_plan.attempts,
            "unsolved": repair_plan.unsolved,
        },
        "violations": [asdict(violation) for violation in report.violations],
        "report": asdict(report),
        "instance": instance_data,
    }


def write_solution(payload, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def print_summary(status, output_path, payload, report):
    print("EVRP-TW solving pipeline")
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  source={payload['source']['path']}")
    print(f"  vehicles={payload['metrics']['vehicle_count']}")
    print(f"  runtime={payload['solver']['elapsed_runtime_seconds']}s")
    print(f"  station_insertions={payload['repair']['station_insertions']}")
    print(f"  split_count={payload['repair']['split_count']}")
    print_benchmark_report(report, solver="EVRPTWRepairPipeline")
    print(f"Solution JSON: {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Solve EVRP-TW with a PyVRP baseline plus station repair."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schneider", type=Path, help="External Schneider .txt file.")
    source.add_argument("--solomon", type=Path, help="Solomon/Holmberger VRPTW .txt file.")
    source.add_argument("--instance", type=Path, help="Project JSON instance file.")
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--runtime-seconds", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--fail-on-unsolved", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    status, output_path, payload, report = solve_pipeline(args)
    print_summary(status, output_path, payload, report)
    if args.fail_on_unsolved and status != "solved":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
