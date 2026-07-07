"""Scale the CVRP100 POMO repair baseline to large VRPTW/EVRP-TW instances.

The upstream checkpoint is still a 100-customer CVRP policy. This script keeps
that boundary explicit by decomposing a large instance into 100-customer
subproblems, using POMO only as a local customer-order generator, then repairing
and validating the merged full-instance routes with the project EVRP-TW layer.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
DEFAULT_RESULTS_DIR = SRC_ROOT / "results" / "week4_vns_ts_comparison"

sys.path.insert(0, str(EXPERIMENTS_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from experiment_record import build_experiment_record, format_constraint_violations  # noqa: E402
from feasibility_checker import check_explicit_routes, print_benchmark_report  # noqa: E402
from instance_loader import load_instance_data  # noqa: E402
from pomo_evrptw_repair_pipeline import (  # noqa: E402
    DEFAULT_CHECKPOINT,
    evaluate_candidate,
    evaluation_sort_key,
    expand_candidate_variants,
    load_model,
    rollout_pomo_candidates,
)
from PyVRP.evrptw_v3_repair import (  # noqa: E402
    repair_customer_sequence,
    repair_routes_with_splitting,
)
from PyVRP.parse_schneider_instance import convert_schneider_instance  # noqa: E402
from solomon_to_project_instance import convert_solomon_instance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run POMO100 cluster decomposition plus EVRP-TW repair."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--instance", type=Path, help="Project JSON EVRP-TW/VRPTW instance.")
    source.add_argument("--schneider", type=Path, help="External Schneider EVRP-TW .txt file.")
    source.add_argument("--solomon", type=Path, help="Solomon/Holmberger VRPTW .txt file.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--augmentation", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=4)
    parser.add_argument("--cluster-size", type=int, default=100)
    parser.add_argument("--cluster-method", choices=("sweep",), default="sweep")
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


def sweep_clusters(instance, cluster_size: int) -> list[list]:
    if cluster_size <= 0:
        raise ValueError("--cluster-size must be positive.")

    depot = instance.depot
    ordered = sorted(
        instance.clients,
        key=lambda client: (
            math.atan2(client.y - depot.y, client.x - depot.x),
            math.hypot(client.x - depot.x, client.y - depot.y),
            client.name,
        ),
    )
    return [
        ordered[start : start + cluster_size]
        for start in range(0, len(ordered), cluster_size)
    ]


def subproblem_data(full_data: dict, cluster_clients: list, cluster_index: int) -> dict:
    names = {client.name for client in cluster_clients}
    selected = [
        copy.deepcopy(client)
        for client in full_data.get("clients", [])
        if client.get("name") in names
    ]
    by_name = {client["name"]: client for client in selected}
    ordered_selected = [
        copy.deepcopy(by_name[client.name])
        if client.name in by_name
        else client_payload(client)
        for client in cluster_clients
    ]

    data = copy.deepcopy(full_data)
    data["name"] = f"{full_data.get('name', 'instance')}_cluster_{cluster_index:02d}"
    data["clients"] = ordered_selected
    data.setdefault("solver", {})["display"] = False
    return data


def client_payload(client) -> dict:
    return {
        "name": client.name,
        "x": client.x,
        "y": client.y,
        "demand": client.demand,
        "service_duration": client.service_duration,
        "tw_early": client.tw_early,
        "tw_late": client.tw_late,
    }


def repair_and_check(customer_routes: list[list[str]], instance):
    repair_plan = repair_routes_with_splitting(customer_routes, instance)
    report = check_explicit_routes(
        routes=repair_plan.routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=repair_plan.charging_plans,
    )
    return repair_plan, report


def evaluate_full_variants(customer_routes: list[list[str]], instance) -> list[dict]:
    variants = [
        ("cluster_routes", customer_routes),
        ("flattened_single_sequence", [flatten_customer_routes(customer_routes)]),
        ("time_window_greedy_pack", time_window_greedy_pack(customer_routes, instance)),
        ("insertion_greedy_pack", insertion_greedy_pack(customer_routes, instance)),
    ]
    evaluations = []
    seen: set[tuple[tuple[str, ...], ...]] = set()
    for variant, routes in variants:
        signature = tuple(tuple(route) for route in routes if route)
        if signature in seen:
            continue
        seen.add(signature)
        repair_plan, report = repair_and_check(routes, instance)
        evaluations.append(
            {
                "variant": variant,
                "customer_routes": routes,
                "repair_plan": repair_plan,
                "report": report,
            }
        )
    return evaluations


def full_evaluation_sort_key(evaluation: dict) -> tuple:
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    feasible = repair_plan.feasible and report.feasible
    if feasible:
        return (
            0,
            report.total_distance,
            len(repair_plan.routes),
            repair_plan.station_insertions,
        )
    return (
        1,
        -report.served_customers,
        len(report.missing_customers),
        len(report.duplicate_customers),
        len(report.violations),
        len(repair_plan.unsolved),
    )


def flatten_customer_routes(customer_routes: list[list[str]]) -> list[str]:
    flattened: list[str] = []
    seen: set[str] = set()
    for route in customer_routes:
        for customer_name in route:
            if customer_name in seen:
                continue
            flattened.append(customer_name)
            seen.add(customer_name)
    return flattened


def time_window_greedy_pack(customer_routes: list[list[str]], instance) -> list[list[str]]:
    customers_by_name = {customer.name: customer for customer in instance.clients}
    position_by_name = {
        name: position for position, name in enumerate(flatten_customer_routes(customer_routes))
    }
    ordered_names = sorted(
        position_by_name,
        key=lambda name: (
            customers_by_name[name].tw_early,
            customers_by_name[name].tw_late,
            position_by_name[name],
        ),
    )

    routes: list[list[str]] = []
    current: list[str] = []
    for customer_name in ordered_names:
        proposed = [*current, customer_name]
        if repair_customer_sequence(proposed, instance).feasible:
            current = proposed
            continue
        if current:
            routes.append(current)
        current = [customer_name]

    if current:
        routes.append(current)
    return routes


def insertion_greedy_pack(customer_routes: list[list[str]], instance) -> list[list[str]]:
    ordered_names = flatten_customer_routes(customer_routes)
    customer_by_name = {customer.name: customer for customer in instance.clients}
    routes: list[list[str]] = []
    load_by_route: list[float] = []

    for customer_name in ordered_names:
        customer = customer_by_name[customer_name]
        best = None
        for route_idx, route in enumerate(routes):
            if load_by_route[route_idx] + customer.demand > instance.vehicle_capacity:
                continue
            for position in range(len(route) + 1):
                proposed = [*route[:position], customer_name, *route[position:]]
                if not repair_customer_sequence(proposed, instance).feasible:
                    continue
                delta = insertion_delta(
                    route=route,
                    customer_name=customer_name,
                    position=position,
                    instance=instance,
                    customer_by_name=customer_by_name,
                )
                candidate = (delta, len(proposed), route_idx, position)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            routes.append([customer_name])
            load_by_route.append(customer.demand)
            continue

        _delta, _length, route_idx, position = best
        routes[route_idx].insert(position, customer_name)
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


def coverage_summary(customer_routes: list[list[str]], instance) -> dict:
    expected = {client.name for client in instance.clients}
    visits = [
        customer
        for route in customer_routes
        for customer in route
        if customer in expected
    ]
    counts = Counter(visits)
    return {
        "expected_customers": len(expected),
        "served_in_candidate_routes": sum(1 for name in expected if counts[name] == 1),
        "missing_customers": sorted(name for name in expected if counts[name] == 0),
        "duplicate_customers": sorted(name for name, count in counts.items() if count > 1),
    }


def solve(args: argparse.Namespace):
    started = time.perf_counter()
    torch.manual_seed(args.seed)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")
    device = torch.device(args.device)
    if hasattr(torch, "set_default_device"):
        torch.set_default_device(device)

    instance, source_path, instance_data = load_full_instance(args)
    clusters = sweep_clusters(instance, args.cluster_size)
    model = load_model(args.checkpoint, device)

    merged_customer_routes: list[list[str]] = []
    cluster_records = []
    for index, cluster_clients in enumerate(clusters, start=1):
        data = subproblem_data(instance_data, cluster_clients, index)
        sub_instance = load_instance_data(data, default_name=data["name"])
        pomo_candidates = rollout_pomo_candidates(
            instance=sub_instance,
            model=model,
            device=device,
            use_augmentation=args.augmentation,
            max_candidates=args.max_candidates,
        )
        candidates = expand_candidate_variants(pomo_candidates, sub_instance)
        evaluations = [evaluate_candidate(candidate, sub_instance) for candidate in candidates]
        selected = min(evaluations, key=evaluation_sort_key)
        selected_candidate = selected["candidate"]
        local_repair = selected["repair_plan"]
        local_report = selected["report"]
        merged_customer_routes.extend(selected_candidate.customer_routes)
        cluster_records.append(
            {
                "cluster_index": index,
                "customer_count": len(cluster_clients),
                "customers": [client.name for client in cluster_clients],
                "candidate_variant": selected_candidate.variant,
                "candidate_rank": selected_candidate.rank,
                "local_feasible": local_repair.feasible and local_report.feasible,
                "local_distance": local_report.total_distance,
                "local_vehicle_count": len(local_repair.routes),
                "local_missing_customers": len(local_report.missing_customers),
                "local_duplicate_customers": len(local_report.duplicate_customers),
                "evaluated_candidates": len(evaluations),
            }
        )

    full_evaluations = evaluate_full_variants(merged_customer_routes, instance)
    selected_full = min(full_evaluations, key=full_evaluation_sort_key)
    repair_plan = selected_full["repair_plan"]
    report = selected_full["report"]
    elapsed = time.perf_counter() - started
    status = "solved" if repair_plan.feasible and report.feasible else "unsolved"
    payload = build_payload(
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        args=args,
        clusters=clusters,
        cluster_records=cluster_records,
        merged_customer_routes=merged_customer_routes,
        full_evaluations=full_evaluations,
        selected_full_variant=selected_full["variant"],
        repair_plan=repair_plan,
        report=report,
        elapsed_runtime_seconds=elapsed,
    )
    output_path = resolve_output_path(args.output, instance.name)
    write_solution(payload, output_path)
    return status, output_path, payload, report


def resolve_output_path(output: Path | None, instance_name: str) -> Path:
    if output is not None:
        return output
    return DEFAULT_RESULTS_DIR / f"{instance_name}_pomo100_cluster_repair.json"


def build_payload(
    *,
    status: str,
    source_path: Path,
    instance,
    instance_data: dict,
    args: argparse.Namespace,
    clusters: list[list],
    cluster_records: list[dict],
    merged_customer_routes: list[list[str]],
    full_evaluations: list[dict],
    selected_full_variant: str,
    repair_plan,
    report,
    elapsed_runtime_seconds: float,
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
    coverage = coverage_summary(merged_customer_routes, instance)
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
            method_name="POMO100 cluster + EVRP-TW repair",
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(repair_plan.routes),
            constraint_violations=constraint_violations,
            random_seed=args.seed,
            best_solution_found=repair_plan.routes,
            reference_value=instance_data.get("source", {}).get("known_cost"),
            convergence_curve=cluster_records,
            improvement_over_time="cluster-local POMO candidates then full-instance repair",
            search_steps=sum(record["evaluated_candidates"] for record in cluster_records),
        ),
        "solver": {
            "candidate_generator": "yd-kwon/POMO CVRP100 pretrained checkpoint",
            "method_name": "POMO100 cluster + EVRP-TW repair",
            "checkpoint": str(args.checkpoint),
            "device": args.device,
            "augmentation": args.augmentation,
            "max_candidates_per_cluster": args.max_candidates,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "seed": args.seed,
            "model_status": (
                "CVRP100 checkpoint used only inside cluster-sized subproblems; "
                "full-instance feasibility is handled by repair/checker."
            ),
        },
        "decomposition": {
            "cluster_method": args.cluster_method,
            "cluster_size": args.cluster_size,
            "cluster_count": len(clusters),
            "coverage": coverage,
            "clusters": cluster_records,
        },
        "candidate": {
            "selected_full_variant": selected_full_variant,
            "customer_routes": merged_customer_routes,
            "full_variant_evaluations": [
                full_evaluation_payload(evaluation) for evaluation in full_evaluations
            ],
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
        "violations": [asdict(violation) for violation in report.violations],
        "report": asdict(report),
        "instance": instance_data,
    }


def full_evaluation_payload(evaluation: dict) -> dict:
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    return {
        "variant": evaluation["variant"],
        "candidate_route_count": len(evaluation["customer_routes"]),
        "repair_feasible": repair_plan.feasible,
        "checked_feasible": report.feasible,
        "served_customers": report.served_customers,
        "missing_customers": len(report.missing_customers),
        "duplicate_customers": len(report.duplicate_customers),
        "vehicle_count": len(repair_plan.routes),
        "total_distance": report.total_distance,
        "violation_count": len(report.violations),
        "unsolved": repair_plan.unsolved,
    }


def write_solution(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def print_summary(status: str, output_path: Path, payload: dict, report) -> None:
    print("POMO100 cluster + EVRP-TW repair")
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  output={output_path}")
    print(f"  clusters={payload['decomposition']['cluster_count']}")
    print(f"  selected_full_variant={payload['candidate']['selected_full_variant']}")
    print(f"  vehicles={payload['metrics']['vehicle_count']}")
    print(f"  distance={payload['metrics']['total_distance']}")
    print(f"  served_customers={payload['metrics']['served_customers']}")
    print(f"  missing_customers={payload['metrics']['missing_customers']}")
    print(f"  duplicate_customers={payload['metrics']['duplicate_customers']}")
    print_benchmark_report(
        report,
        runtime_seconds=payload["solver"]["elapsed_runtime_seconds"],
        seed=payload["solver"]["seed"],
        solver="POMO100 cluster + EVRP-TW repair",
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
