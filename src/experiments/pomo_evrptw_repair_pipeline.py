"""Build EVRP-TW routes from a pretrained CVRP-POMO candidate sequence.

The POMO checkpoint is still a CVRP model: it only sees depot/customer
coordinates, demand, and vehicle capacity. This pipeline keeps that boundary
explicit, then lets the project EVRP-TW repair layer add time-window and energy
feasibility through route splitting, charging-station insertion, and checker
validation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
POMO_ROOT = REPO_ROOT / "external" / "POMO" / "NEW_py_ver"
POMO_CVRP_ROOT = POMO_ROOT / "CVRP"
POMO_CVRP_CODE = POMO_CVRP_ROOT / "POMO"
DEFAULT_CHECKPOINT = (
    POMO_CVRP_CODE / "result" / "saved_CVRP100_model" / "checkpoint-30500.pt"
)
DEFAULT_RESULTS_DIR = SRC_ROOT / "results"

sys.path.insert(0, str(POMO_CVRP_CODE))
sys.path.insert(0, str(POMO_CVRP_ROOT))
sys.path.insert(0, str(POMO_ROOT))
sys.path.insert(0, str(EXPERIMENTS_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from CVRPEnv import CVRPEnv  # noqa: E402
from CVRPModel import CVRPModel  # noqa: E402
from CVRProblemDef import augment_xy_data_by_8_fold  # noqa: E402
from experiment_record import (  # noqa: E402
    build_experiment_record,
    format_constraint_violations,
)
from feasibility_checker import check_explicit_routes, print_benchmark_report  # noqa: E402
from instance_loader import load_instance_data  # noqa: E402
from PyVRP.evrptw_v3_repair import (  # noqa: E402
    repair_customer_sequence,
    repair_routes_with_splitting,
)
from PyVRP.parse_schneider_instance import convert_schneider_instance  # noqa: E402


MODEL_PARAMS = {
    "embedding_dim": 128,
    "sqrt_embedding_dim": 128**0.5,
    "encoder_layer_num": 6,
    "qkv_dim": 16,
    "head_num": 8,
    "logit_clipping": 10,
    "ff_hidden_dim": 512,
    "eval_type": "argmax",
}


@dataclass(frozen=True)
class POMOCandidate:
    rank: int
    pomo_rank: int
    variant: str
    actions: list[int]
    customer_routes: list[list[str]]
    aug_index: int
    pomo_index: int
    normalized_cvrp_distance: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Use the pretrained yd-kwon CVRP-POMO checkpoint as a customer-order "
            "generator, then repair the result into checked EVRP-TW routes."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--instance", type=Path, help="Project JSON EVRP-TW instance.")
    source.add_argument("--schneider", type=Path, help="External Schneider .txt file.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--augmentation",
        action="store_true",
        help="Use the same 8-fold coordinate augmentation as POMO testing.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=4,
        help=(
            "Number of distinct POMO rollouts to try through EVRP-TW repair, "
            "ranked by CVRP reward. Time-window repair variants may add more "
            "evaluations."
        ),
    )
    parser.add_argument("--fail-on-unsolved", action="store_true")
    return parser.parse_args()


def load_pipeline_instance(args: argparse.Namespace):
    if args.schneider is not None:
        data = convert_schneider_instance(
            input_path=args.schneider,
            num_vehicles=1 if args.vehicles is None else args.vehicles,
            solver_runtime_seconds=0,
            solver_seed=args.seed,
            solver_display=False,
        )
        source_path = Path(args.schneider)
    else:
        source_path = Path(args.instance)
        with source_path.open(encoding="utf-8") as file:
            data = json.load(file)
        apply_overrides(data=data, vehicles=args.vehicles, seed=args.seed)

    return load_instance_data(data, default_name=source_path.stem), source_path, data


def apply_overrides(data: dict, vehicles: int | None, seed: int) -> None:
    solver = data.setdefault("solver", {})
    solver["seed"] = seed
    solver["display"] = False
    if vehicles is not None:
        data.setdefault("vehicles", {})["num_available"] = vehicles


def resolve_output_path(output: Path | None, instance_name: str) -> Path:
    if output is not None:
        return output
    return DEFAULT_RESULTS_DIR / f"{instance_name}_pomo_repair_solution.json"


def load_model(checkpoint_path: Path, device: torch.device) -> CVRPModel:
    if not checkpoint_path.exists():
        raise FileNotFoundError(checkpoint_path)

    model = CVRPModel(**MODEL_PARAMS).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def normalize_instance_for_pomo(instance) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if not instance.clients:
        raise ValueError("POMO requires at least one customer.")
    if instance.vehicle_capacity <= 0:
        raise ValueError("Vehicle capacity must be positive for CVRP-POMO demand scaling.")

    rows = [instance.depot, *instance.clients]
    xs = [row.x for row in rows]
    ys = [row.y for row in rows]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1.0)

    depot_xy = torch.tensor(
        [[[(instance.depot.x - min_x) / span, (instance.depot.y - min_y) / span]]],
        dtype=torch.float32,
    )
    node_xy = torch.tensor(
        [
            [
                [(client.x - min_x) / span, (client.y - min_y) / span]
                for client in instance.clients
            ]
        ],
        dtype=torch.float32,
    )
    node_demand = torch.tensor(
        [[client.demand / instance.vehicle_capacity for client in instance.clients]],
        dtype=torch.float32,
    )
    return depot_xy, node_xy, node_demand


def rollout_pomo_candidates(
    instance,
    model: CVRPModel,
    device: torch.device,
    use_augmentation: bool,
    max_candidates: int,
) -> list[POMOCandidate]:
    if max_candidates <= 0:
        raise ValueError("--max-candidates must be positive.")

    depot_xy, node_xy, node_demand = normalize_instance_for_pomo(instance)
    if use_augmentation:
        aug_factor = 8
        depot_xy = augment_xy_data_by_8_fold(depot_xy)
        node_xy = augment_xy_data_by_8_fold(node_xy)
        node_demand = node_demand.repeat(8, 1)
    else:
        aug_factor = 1

    depot_xy = depot_xy.to(device)
    node_xy = node_xy.to(device)
    node_demand = node_demand.to(device)

    env = CVRPEnv(problem_size=len(instance.clients), pomo_size=len(instance.clients))
    env.FLAG__use_saved_problems = True
    env.saved_depot_xy = depot_xy
    env.saved_node_xy = node_xy
    env.saved_node_demand = node_demand
    env.saved_index = 0

    with torch.inference_mode():
        env.load_problems(batch_size=aug_factor, aug_factor=1)
        reset_state, _, _ = env.reset()
        model.pre_forward(reset_state)
        state, reward, done = env.pre_step()
        while not done:
            selected, _ = model(state)
            state, reward, done = env.step(selected)

    rewards = reward.reshape(aug_factor, 1, env.pomo_size)
    flat_rewards = rewards.reshape(-1)
    ranked_indices = flat_rewards.argsort(descending=True).detach().cpu().tolist()
    candidates: list[POMOCandidate] = []
    seen_actions: set[tuple[int, ...]] = set()

    for flat_index in ranked_indices:
        aug_index = int(flat_index // env.pomo_size)
        pomo_index = int(flat_index % env.pomo_size)
        actions = tuple(
            int(action)
            for action in env.selected_node_list[aug_index, pomo_index]
            .detach()
            .cpu()
            .tolist()
        )
        if actions in seen_actions:
            continue
        seen_actions.add(actions)
        normalized_cvrp_distance = float(
            -rewards[aug_index, 0, pomo_index].detach().cpu()
        )
        candidates.append(
            POMOCandidate(
                rank=len(candidates) + 1,
                pomo_rank=len(candidates) + 1,
                variant="pomo_routes",
                actions=list(actions),
                customer_routes=actions_to_customer_routes(list(actions), instance),
                aug_index=aug_index,
                pomo_index=pomo_index,
                normalized_cvrp_distance=normalized_cvrp_distance,
            )
        )
        if len(candidates) >= max_candidates:
            break

    return candidates


def expand_candidate_variants(
    pomo_candidates: list[POMOCandidate],
    instance,
) -> list[POMOCandidate]:
    variants: list[POMOCandidate] = []
    seen_routes: set[tuple[tuple[str, ...], ...]] = set()

    def add_variant(candidate: POMOCandidate, routes: list[list[str]], variant: str) -> None:
        signature = routes_signature(routes)
        if signature in seen_routes:
            return
        seen_routes.add(signature)
        variants.append(
            POMOCandidate(
                rank=len(variants) + 1,
                pomo_rank=candidate.pomo_rank,
                variant=variant,
                actions=candidate.actions,
                customer_routes=routes,
                aug_index=candidate.aug_index,
                pomo_index=candidate.pomo_index,
                normalized_cvrp_distance=candidate.normalized_cvrp_distance,
            )
        )

    for candidate in pomo_candidates:
        add_variant(candidate, candidate.customer_routes, candidate.variant)
        time_window_routes = build_time_window_greedy_routes(candidate, instance)
        add_variant(candidate, time_window_routes, "time_window_greedy_pack")

    return variants


def routes_signature(routes: list[list[str]]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(route) for route in routes)


def build_time_window_greedy_routes(candidate: POMOCandidate, instance) -> list[list[str]]:
    customers_by_name = {customer.name: customer for customer in instance.clients}
    position_by_name = {
        customer_name: position
        for position, customer_name in enumerate(flatten_routes(candidate.customer_routes))
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
        if route_sequence_feasible(proposed, instance):
            current = proposed
            continue
        if current:
            routes.append(current)
        current = [customer_name]

    if current:
        routes.append(current)
    return routes


def flatten_routes(routes: list[list[str]]) -> list[str]:
    flattened: list[str] = []
    seen: set[str] = set()
    for route in routes:
        for customer_name in route:
            if customer_name not in seen:
                flattened.append(customer_name)
                seen.add(customer_name)
    return flattened


def route_sequence_feasible(customer_names: list[str], instance) -> bool:
    return repair_customer_sequence(customer_names, instance).feasible


def actions_to_customer_routes(actions: list[int], instance) -> list[list[str]]:
    customer_by_index = {
        index: customer.name for index, customer in enumerate(instance.clients, start=1)
    }
    routes: list[list[str]] = []
    current: list[str] = []
    seen: set[str] = set()

    for raw_action in actions:
        action = int(raw_action)
        if action == 0:
            if current:
                routes.append(current)
                current = []
            continue

        customer_name = customer_by_index.get(action)
        if customer_name is None or customer_name in seen:
            continue
        current.append(customer_name)
        seen.add(customer_name)

    if current:
        routes.append(current)

    missing = [
        customer.name for customer in instance.clients if customer.name not in seen
    ]
    routes.extend([[customer_name] for customer_name in missing])
    return routes


def solve_pipeline(args: argparse.Namespace):
    started = time.perf_counter()
    torch.manual_seed(args.seed)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")

    device = torch.device(args.device)
    if hasattr(torch, "set_default_device"):
        torch.set_default_device(device)

    instance, source_path, instance_data = load_pipeline_instance(args)
    output_path = resolve_output_path(args.output, instance.name)
    model = load_model(args.checkpoint, device)
    pomo_candidates = rollout_pomo_candidates(
        instance=instance,
        model=model,
        device=device,
        use_augmentation=args.augmentation,
        max_candidates=args.max_candidates,
    )
    candidates = expand_candidate_variants(pomo_candidates, instance)
    evaluations = [evaluate_candidate(candidate, instance) for candidate in candidates]
    selected = min(evaluations, key=evaluation_sort_key)
    candidate = selected["candidate"]
    repair_plan = selected["repair_plan"]
    report = selected["report"]
    status = "solved" if repair_plan.feasible and report.feasible else "unsolved"
    elapsed_runtime_seconds = time.perf_counter() - started
    payload = build_solution_payload(
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        candidate=candidate,
        candidate_evaluations=evaluations,
        checkpoint=args.checkpoint,
        use_augmentation=args.augmentation,
        device=args.device,
        repair_plan=repair_plan,
        report=report,
        elapsed_runtime_seconds=elapsed_runtime_seconds,
    )
    write_solution(payload, output_path)
    return status, output_path, payload, report


def evaluate_candidate(candidate: POMOCandidate, instance) -> dict:
    repair_plan = repair_routes_with_splitting(candidate.customer_routes, instance)
    report = check_explicit_routes(
        routes=repair_plan.routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=repair_plan.charging_plans,
    )
    return {
        "candidate": candidate,
        "repair_plan": repair_plan,
        "report": report,
    }


def evaluation_sort_key(evaluation: dict) -> tuple:
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    feasible = repair_plan.feasible and report.feasible
    if feasible:
        return (
            0,
            report.total_distance,
            len(repair_plan.routes),
            repair_plan.station_insertions,
            evaluation["candidate"].normalized_cvrp_distance,
        )
    return (
        1,
        -report.served_customers,
        len(report.violations),
        len(repair_plan.unsolved),
        repair_plan.split_count,
        evaluation["candidate"].normalized_cvrp_distance,
    )


def build_solution_payload(
    status,
    source_path,
    instance,
    instance_data,
    candidate,
    candidate_evaluations,
    checkpoint,
    use_augmentation,
    device,
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
            method_name="yd-kwon/POMO CVRP + EVRP-TW repair",
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(repair_plan.routes),
            constraint_violations=constraint_violations,
            random_seed=instance.solver.seed,
            best_solution_found=repair_plan.routes,
            reference_value=None,
            convergence_curve="single pretrained CVRP-POMO rollout",
            improvement_over_time="repair attempts are recorded in repair.attempts",
            search_steps=len(candidate.actions) + len(repair_plan.attempts),
        ),
        "solver": {
            "candidate_generator": "yd-kwon/POMO CVRP100 pretrained checkpoint",
            "repair": "v3_partial_recharge_label_setting",
            "checkpoint": str(checkpoint),
            "device": device,
            "augmentation": use_augmentation,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "seed": instance.solver.seed,
            "model_status": (
                "CVRP-only checkpoint; time windows, battery, and charging stations "
                "are handled by the external repair/checker layer."
            ),
        },
        "candidate": {
            "rank": candidate.rank,
            "pomo_rank": candidate.pomo_rank,
            "variant": candidate.variant,
            "actions": candidate.actions,
            "customer_routes": candidate.customer_routes,
            "selected_augmentation_index": candidate.aug_index,
            "selected_pomo_index": candidate.pomo_index,
            "normalized_cvrp_distance": round(candidate.normalized_cvrp_distance, 6),
        },
        "candidate_selection": {
            "evaluated_candidates": len(candidate_evaluations),
            "selected_rank": candidate.rank,
            "selected_variant": candidate.variant,
            "policy": (
                "try distinct POMO rollouts ranked by CVRP reward; choose feasible "
                "EVRP-TW repair with lowest checked distance"
            ),
            "evaluations": [
                candidate_evaluation_payload(evaluation)
                for evaluation in candidate_evaluations
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


def candidate_evaluation_payload(evaluation: dict) -> dict:
    candidate = evaluation["candidate"]
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    return {
        "rank": candidate.rank,
        "pomo_rank": candidate.pomo_rank,
        "variant": candidate.variant,
        "customer_routes": candidate.customer_routes,
        "normalized_cvrp_distance": round(candidate.normalized_cvrp_distance, 6),
        "repair_feasible": repair_plan.feasible,
        "checked_feasible": report.feasible,
        "served_customers": report.served_customers,
        "total_distance": report.total_distance,
        "vehicle_count": len(repair_plan.routes),
        "split_count": repair_plan.split_count,
        "station_insertions": repair_plan.station_insertions,
        "violation_count": len(report.violations),
        "unsolved": repair_plan.unsolved,
    }


def write_solution(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def print_summary(status, output_path, payload, report) -> None:
    print("POMO + EVRP-TW repair pipeline")
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  source={payload['source']['path']}")
    print(f"  vehicles={payload['metrics']['vehicle_count']}")
    print(f"  runtime={payload['solver']['elapsed_runtime_seconds']}s")
    print(
        "  selected_candidate="
        f"{payload['candidate']['rank']}/{payload['candidate_selection']['evaluated_candidates']}"
    )
    print(f"  selected_variant={payload['candidate']['variant']}")
    print(f"  candidate_routes={payload['candidate']['customer_routes']}")
    print(f"  station_insertions={payload['repair']['station_insertions']}")
    print(f"  split_count={payload['repair']['split_count']}")
    print_benchmark_report(report, solver="POMO+EVRPTWRepair")
    print(f"Solution JSON: {output_path}")


def main() -> int:
    args = parse_args()
    status, output_path, payload, report = solve_pipeline(args)
    print_summary(status, output_path, payload, report)
    if args.fail_on_unsolved and status != "solved":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
