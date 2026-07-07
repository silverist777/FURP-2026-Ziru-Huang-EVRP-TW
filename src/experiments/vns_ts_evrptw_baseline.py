"""Tabu-assisted VNS baseline for EVRP-TW/VRPTW repair experiments.

This is a Week 4 comparison method with explicit inputs, outputs, and checker
validation. It searches over customer-route groupings; the shared repair layer
handles route splitting, charging insertion, and final feasibility checks.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
DEFAULT_RESULTS_DIR = SRC_ROOT / "results" / "week4_vns_ts_comparison"

sys.path.insert(0, str(EXPERIMENTS_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from experiment_record import build_experiment_record, format_constraint_violations  # noqa: E402
from feasibility_checker import check_explicit_routes, print_benchmark_report  # noqa: E402
from instance_loader import load_instance_data  # noqa: E402
from PyVRP.evrptw_v3_repair import (  # noqa: E402
    repair_customer_sequence,
    repair_routes_with_splitting,
)
from PyVRP.parse_schneider_instance import convert_schneider_instance  # noqa: E402
from solomon_to_project_instance import convert_solomon_instance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a tabu-assisted VNS EVRP-TW baseline."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--instance", type=Path, help="Project JSON EVRP-TW/VRPTW instance.")
    source.add_argument("--schneider", type=Path, help="External Schneider EVRP-TW .txt file.")
    source.add_argument("--solomon", type=Path, help="Solomon/Holmberger VRPTW .txt file.")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--neighbors-per-iteration", type=int, default=20)
    parser.add_argument("--tabu-size", type=int, default=80)
    parser.add_argument("--initial-order", choices=("tw_sweep", "sweep"), default="tw_sweep")
    parser.add_argument("--fail-on-unsolved", action="store_true")
    return parser.parse_args()


def load_full_instance(args: argparse.Namespace):
    if args.solomon is not None:
        source_path = args.solomon
        data = convert_solomon_instance(
            input_path=args.solomon,
            num_vehicles=args.vehicles,
            solver_runtime_seconds=0,
            solver_seed=args.seed,
            solver_display=False,
        )
    elif args.schneider is not None:
        source_path = args.schneider
        data = convert_schneider_instance(
            input_path=args.schneider,
            num_vehicles=1 if args.vehicles is None else args.vehicles,
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

    return load_instance_data(data, default_name=source_path.stem), source_path, data


def initial_customer_routes(instance, order_policy: str) -> list[list[str]]:
    customers = list(instance.clients)
    depot = instance.depot
    if order_policy == "sweep":
        customers.sort(key=lambda client: polar_key(client, depot))
    else:
        customers.sort(
            key=lambda client: (
                client.tw_early,
                client.tw_late,
                *polar_key(client, depot),
            )
        )

    routes: list[list[str]] = []
    load_by_route: list[float] = []
    customer_by_name = {customer.name: customer for customer in instance.clients}
    for customer in customers:
        best = None
        for route_idx, route in enumerate(routes):
            if load_by_route[route_idx] + customer.demand > instance.vehicle_capacity:
                continue
            for position in range(len(route) + 1):
                proposed = [*route[:position], customer.name, *route[position:]]
                repaired = repair_customer_sequence(proposed, instance)
                if not repaired.feasible:
                    continue
                delta = insertion_delta(
                    route=route,
                    customer_name=customer.name,
                    position=position,
                    instance=instance,
                    customer_by_name=customer_by_name,
                )
                candidate = (delta, len(proposed), route_idx, position)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            routes.append([customer.name])
            load_by_route.append(customer.demand)
            continue

        _delta, _length, route_idx, position = best
        routes[route_idx].insert(position, customer.name)
        load_by_route[route_idx] += customer.demand
    return routes


def insertion_delta(
    route: list[str],
    customer_name: str,
    position: int,
    instance,
    customer_by_name: dict,
) -> int:
    previous_location = (
        instance.depot if position == 0 else customer_by_name[route[position - 1]]
    )
    next_location = (
        instance.depot if position == len(route) else customer_by_name[route[position]]
    )
    customer = customer_by_name[customer_name]
    return (
        instance.distance(previous_location, customer)
        + instance.distance(customer, next_location)
        - instance.distance(previous_location, next_location)
    )


def polar_key(client, depot) -> tuple[float, float, str]:
    return (
        math.atan2(client.y - depot.y, client.x - depot.x),
        math.hypot(client.x - depot.x, client.y - depot.y),
        client.name,
    )


def evaluate(customer_routes: list[list[str]], instance) -> dict:
    repair_plan = repair_routes_with_splitting(customer_routes, instance)
    report = check_explicit_routes(
        routes=repair_plan.routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=repair_plan.charging_plans,
    )
    return {
        "customer_routes": [list(route) for route in customer_routes if route],
        "repair_plan": repair_plan,
        "report": report,
    }


def score(evaluation: dict) -> tuple:
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    feasible = repair_plan.feasible and report.feasible
    if feasible:
        return (
            0,
            len(repair_plan.routes),
            report.total_distance,
            report.charging_count,
            report.charging_time,
        )
    return (
        1,
        -report.served_customers,
        len(report.missing_customers),
        len(report.duplicate_customers),
        len(report.violations),
        len(repair_plan.unsolved),
        len(repair_plan.routes),
    )


def route_signature(routes: list[list[str]]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(route) for route in routes if route)


def clean_routes(routes: list[list[str]]) -> list[list[str]]:
    return [route for route in routes if route]


def generate_neighbor(routes: list[list[str]], rng: random.Random) -> list[list[str]]:
    candidate = [list(route) for route in routes if route]
    if not candidate:
        return candidate
    move = rng.choice(("relocate", "swap", "two_opt"))
    if move == "relocate" and sum(len(route) for route in candidate) >= 2:
        return relocate(candidate, rng)
    if move == "swap" and sum(len(route) for route in candidate) >= 2:
        return swap(candidate, rng)
    return two_opt(candidate, rng)


def choose_position(routes: list[list[str]], rng: random.Random) -> tuple[int, int]:
    non_empty_indices = [idx for idx, route in enumerate(routes) if route]
    route_idx = rng.choice(non_empty_indices)
    pos = rng.randrange(len(routes[route_idx]))
    return route_idx, pos


def relocate(routes: list[list[str]], rng: random.Random) -> list[list[str]]:
    src_idx, src_pos = choose_position(routes, rng)
    customer = routes[src_idx].pop(src_pos)
    if not routes[src_idx]:
        routes.pop(src_idx)
    dst_idx = rng.randrange(len(routes) + 1)
    if dst_idx == len(routes):
        routes.append([customer])
    else:
        dst_pos = rng.randrange(len(routes[dst_idx]) + 1)
        routes[dst_idx].insert(dst_pos, customer)
    return clean_routes(routes)


def swap(routes: list[list[str]], rng: random.Random) -> list[list[str]]:
    left_route, left_pos = choose_position(routes, rng)
    right_route, right_pos = choose_position(routes, rng)
    attempts = 0
    while (left_route, left_pos) == (right_route, right_pos) and attempts < 5:
        right_route, right_pos = choose_position(routes, rng)
        attempts += 1
    routes[left_route][left_pos], routes[right_route][right_pos] = (
        routes[right_route][right_pos],
        routes[left_route][left_pos],
    )
    return clean_routes(routes)


def two_opt(routes: list[list[str]], rng: random.Random) -> list[list[str]]:
    eligible = [idx for idx, route in enumerate(routes) if len(route) >= 4]
    if not eligible:
        return routes
    route_idx = rng.choice(eligible)
    route = routes[route_idx]
    left, right = sorted(rng.sample(range(len(route)), 2))
    if left != right:
        route[left : right + 1] = reversed(route[left : right + 1])
    return clean_routes(routes)


def search(instance, args: argparse.Namespace) -> tuple[dict, list[dict]]:
    rng = random.Random(args.seed)
    current_routes = initial_customer_routes(instance, args.initial_order)
    current_eval = evaluate(current_routes, instance)
    best_eval = current_eval
    history = [history_row(0, "initial", best_eval)]
    tabu = deque([route_signature(current_routes)], maxlen=args.tabu_size)
    tabu_set = {route_signature(current_routes)}

    for iteration in range(1, args.iterations + 1):
        best_neighbor_eval = None
        best_neighbor_signature = None
        for _ in range(args.neighbors_per_iteration):
            neighbor_routes = generate_neighbor(current_eval["customer_routes"], rng)
            signature = route_signature(neighbor_routes)
            if signature in tabu_set:
                continue
            neighbor_eval = evaluate(neighbor_routes, instance)
            if best_neighbor_eval is None or score(neighbor_eval) < score(best_neighbor_eval):
                best_neighbor_eval = neighbor_eval
                best_neighbor_signature = signature

        if best_neighbor_eval is None:
            history.append(history_row(iteration, "tabu_exhausted", best_eval))
            continue

        current_eval = best_neighbor_eval
        if best_neighbor_signature is not None:
            tabu.append(best_neighbor_signature)
            tabu_set = set(tabu)

        improved = score(current_eval) < score(best_eval)
        if improved:
            best_eval = current_eval
        history.append(history_row(iteration, "improved" if improved else "accepted", best_eval))

    return best_eval, history


def history_row(iteration: int, event: str, evaluation: dict) -> dict:
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    return {
        "iteration": iteration,
        "event": event,
        "feasible": repair_plan.feasible and report.feasible,
        "vehicle_count": len(repair_plan.routes),
        "total_distance": report.total_distance,
        "served_customers": report.served_customers,
        "missing_customers": len(report.missing_customers),
        "duplicate_customers": len(report.duplicate_customers),
        "violation_count": len(report.violations),
    }


def solve(args: argparse.Namespace):
    started = time.perf_counter()
    instance, source_path, instance_data = load_full_instance(args)
    best_eval, history = search(instance, args)
    elapsed = time.perf_counter() - started
    repair_plan = best_eval["repair_plan"]
    report = best_eval["report"]
    status = "solved" if repair_plan.feasible and report.feasible else "unsolved"
    payload = build_payload(
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        args=args,
        evaluation=best_eval,
        history=history,
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
    evaluation: dict,
    history: list[dict],
    elapsed_runtime_seconds: float,
) -> dict:
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    constraint_violations = format_constraint_violations(
        {
            "missing_customers": len(report.missing_customers),
            "duplicate_customers": len(report.duplicate_customers),
            "time_window_violations": report.time_window_violations,
            "capacity_violations": report.capacity_violations,
            "energy_violations": report.energy_violations,
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
            method_name="Tabu-assisted VNS EVRP-TW",
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(repair_plan.routes),
            constraint_violations=constraint_violations,
            random_seed=args.seed,
            best_solution_found=repair_plan.routes,
            reference_value=instance_data.get("source", {}).get("known_cost"),
            convergence_curve=history,
            improvement_over_time=history,
            iterations=args.iterations,
            search_steps=args.iterations * args.neighbors_per_iteration,
        ),
        "solver": {
            "method_name": "Tabu-assisted VNS EVRP-TW",
            "initial_order": args.initial_order,
            "iterations": args.iterations,
            "neighbors_per_iteration": args.neighbors_per_iteration,
            "tabu_size": args.tabu_size,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "seed": args.seed,
            "repair": "v3_partial_recharge_label_setting",
        },
        "candidate": {
            "customer_routes": evaluation["customer_routes"],
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
            "charging_count": report.charging_count,
            "charging_time": report.charging_time,
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
        "search_history": history,
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
    print("Tabu-assisted VNS EVRP-TW")
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  output={output_path}")
    print(f"  vehicles={payload['metrics']['vehicle_count']}")
    print(f"  distance={payload['metrics']['total_distance']}")
    print(f"  served_customers={payload['metrics']['served_customers']}")
    print_benchmark_report(
        report,
        runtime_seconds=payload["solver"]["elapsed_runtime_seconds"],
        seed=payload["solver"]["seed"],
        solver="Tabu-assisted VNS EVRP-TW",
    )


def main() -> int:
    args = parse_args()
    status, output_path, payload, report = solve(args)
    print_summary(status, output_path, payload, report)
    if args.fail_on_unsolved and status != "solved":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
