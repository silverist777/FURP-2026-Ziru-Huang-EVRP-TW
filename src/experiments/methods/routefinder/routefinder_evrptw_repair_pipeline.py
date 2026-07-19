"""Run RouteFinder VRPTW inference followed by the shared EVRP-TW repair.

RouteFinder does not model battery or charging-station state. This adapter
therefore supplies only depot/client VRPTW data to RouteFinder, decodes its
depot-separated actions, and sends the customer routes through the existing
partial-recharge label-setting repair and independent feasibility checker.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import warnings


SRC_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
REPO_ROOT = SRC_ROOT.parent
ROUTEFINDER_ROOT = SRC_ROOT / "routefinder"

sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(EXPERIMENTS_ROOT))

# Official checkpoints predate PyTorch's weights_only=True default. The model
# is downloaded from the pinned official ai4co/routefinder repository.
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(REPO_ROOT / ".cache" / "matplotlib-routefinder"),
)

warnings.filterwarnings(
    "ignore",
    message=r"Failed to import torchrl C\+\+ binaries.*",
)
warnings.filterwarnings(
    "ignore",
    message=r"Environment variable TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD.*",
)
warnings.filterwarnings(
    "ignore",
    message=r"Attribute '.*' is an instance of `nn\.Module`.*",
)

import torch  # noqa: E402
from tensordict import TensorDict  # noqa: E402

from checkers.feasibility_checker import (  # noqa: E402
    check_explicit_routes,
    print_benchmark_report,
)
from core.experiment_record import (  # noqa: E402
    build_experiment_record,
    format_constraint_violations,
)
from core.instance_loader import load_instance_data  # noqa: E402
from methods.pyvrp.evrptw_v3_repair import (  # noqa: E402
    repair_customer_sequence,
    repair_routes_with_splitting,
)
from methods.pyvrp.parse_schneider_instance import (  # noqa: E402
    convert_schneider_instance,
)
from routefinder.envs import MTVRPEnv  # noqa: E402
from routefinder.models import RouteFinderBase  # noqa: E402


DEFAULT_RESULTS_DIR = SRC_ROOT / "log" / "week5" / "routefinder-vehicle-limit"


@dataclass(frozen=True)
class RouteFinderCandidate:
    rank: int
    routefinder_rank: int
    variant: str
    normalized_cost: float
    actions: list[int]
    customer_routes: list[list[str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run RouteFinder on a project benchmark instance, then apply the "
            "shared EVRP-TW station repair and feasibility checker."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schneider", type=Path, help="Schneider EVRP-TW file.")
    source.add_argument("--instance", type=Path, help="Project JSON instance.")
    parser.add_argument("--vehicles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Checkpoint path. Defaults to RF-Transformer 50 or 100 by size.",
    )
    parser.add_argument(
        "--num-augment",
        type=int,
        choices=(1, 8),
        default=8,
        help="Number of geometric augmentations used by official inference.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=4,
        help="Best distinct RouteFinder candidates sent through EVRP-TW repair.",
    )
    parser.add_argument(
        "--greedy-pack-max-clients",
        type=int,
        default=50,
        help=(
            "Generate the repair-aware TW greedy packing variant only up to "
            "this instance size; set 0 to disable."
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
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
        source_path = args.schneider
    else:
        source_path = args.instance
        with source_path.open(encoding="utf-8") as file:
            data = json.load(file)
        data.setdefault("solver", {})
        data["solver"]["seed"] = args.seed
        if args.vehicles is not None:
            data.setdefault("vehicles", {})
            data["vehicles"]["num_available"] = args.vehicles

    data.setdefault("solver", {})
    data["solver"]["name"] = "RouteFinder"
    instance = load_instance_data(data, default_name=source_path.stem)
    return instance, source_path, data


def default_checkpoint(instance_size: int) -> Path:
    size = 50 if instance_size <= 50 else 100
    return ROUTEFINDER_ROOT / "checkpoints" / str(size) / "rf-transformer.ckpt"


def instance_to_tensordict(instance) -> tuple[TensorDict, dict]:
    """Converts one project instance to RouteFinder's normalized VRPTW schema."""

    if not instance.clients:
        raise ValueError("RouteFinder requires at least one client.")
    if instance.vehicle_capacity <= 0:
        raise ValueError("Vehicle capacity must be positive.")

    locations = [instance.depot, *instance.clients]
    min_x = min(location.x for location in locations)
    min_y = min(location.y for location in locations)
    x_span = max(location.x for location in locations) - min_x
    y_span = max(location.y for location in locations) - min_y
    coordinate_scale = max(float(x_span), float(y_span), 1.0)
    time_scale = max(
        coordinate_scale * float(instance.duration_scale),
        1.0,
    )

    locs = [
        [
            (float(location.x) - float(min_x)) / coordinate_scale,
            (float(location.y) - float(min_y)) / coordinate_scale,
        ]
        for location in locations
    ]
    time_windows = [
        [
            float(location.tw_early) / time_scale,
            float(location.tw_late) / time_scale,
        ]
        for location in locations
    ]
    service_time = [
        0.0,
        *[
            float(customer.service_duration) / time_scale
            for customer in instance.clients
        ],
    ]
    demand_linehaul = [
        float(customer.demand) / float(instance.vehicle_capacity)
        for customer in instance.clients
    ]

    td = TensorDict(
        {
            "locs": torch.tensor([locs], dtype=torch.float32),
            "demand_linehaul": torch.tensor(
                [demand_linehaul],
                dtype=torch.float32,
            ),
            "vehicle_capacity": torch.ones((1, 1), dtype=torch.float32),
            "speed": torch.ones((1, 1), dtype=torch.float32),
            "num_depots": torch.ones((1, 1), dtype=torch.int32),
            "time_windows": torch.tensor(
                [time_windows],
                dtype=torch.float32,
            ),
            "service_time": torch.tensor(
                [service_time],
                dtype=torch.float32,
            ),
        },
        batch_size=[1],
    )
    normalization = {
        "coordinate_origin": [float(min_x), float(min_y)],
        "coordinate_scale": coordinate_scale,
        "time_scale": time_scale,
        "demand_scale": float(instance.vehicle_capacity),
        "routefinder_vehicle_capacity": 1.0,
    }
    return td, normalization


def load_official_test_function():
    """Loads the pinned upstream inference helper without copying its logic."""

    test_path = ROUTEFINDER_ROOT / "test.py"
    spec = importlib.util.spec_from_file_location(
        "routefinder_official_test",
        test_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load RouteFinder test helper: {test_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.test


def load_model(checkpoint: Path):
    warnings.filterwarnings("ignore", message=".*weights_only.*", category=FutureWarning)
    previous_directory = Path.cwd()
    try:
        # Checkpoint hyperparameters contain official relative dataset paths.
        # Loading from the upstream root keeps those paths valid on Windows.
        os.chdir(ROUTEFINDER_ROOT)
        return RouteFinderBase.load_from_checkpoint(
            str(checkpoint),
            map_location="cpu",
            strict=False,
        )
    finally:
        os.chdir(previous_directory)


def decode_actions(actions: list[int], instance) -> list[list[str]]:
    """Decodes node 0 as depot separator and 1..N as client indices."""

    routes: list[list[str]] = []
    current: list[str] = []
    for action in actions:
        node = int(action)
        if node == 0:
            if current:
                routes.append(current)
                current = []
            continue
        if node < 1 or node > len(instance.clients):
            raise ValueError(f"RouteFinder emitted invalid node index {node}.")
        current.append(instance.clients[node - 1].name)
    if current:
        routes.append(current)

    emitted = [
        int(action)
        for action in actions
        if int(action) != 0
    ]
    expected = list(range(1, len(instance.clients) + 1))
    if sorted(emitted) != expected:
        raise ValueError(
            "RouteFinder actions must visit every client exactly once: "
            f"expected={expected}, emitted={emitted}"
        )
    return routes


def extract_candidates(
    output: dict,
    instance,
    max_candidates: int,
) -> list[RouteFinderCandidate]:
    actions = output.get("best_multistart_actions")
    rewards = output.get("max_reward")
    if actions is None or rewards is None:
        actions = output["best_aug_actions"].unsqueeze(1)
        rewards = output["max_aug_reward"].unsqueeze(1)

    actions = actions[0]
    rewards = rewards[0]
    if actions.dim() == 1:
        actions = actions.unsqueeze(0)
    if rewards.dim() == 0:
        rewards = rewards.unsqueeze(0)

    ranked = sorted(
        zip(rewards.detach().cpu().tolist(), actions.detach().cpu().tolist()),
        key=lambda item: item[0],
        reverse=True,
    )
    candidates: list[RouteFinderCandidate] = []
    seen: set[tuple[tuple[str, ...], ...]] = set()
    for reward, candidate_actions in ranked:
        routes = decode_actions(candidate_actions, instance)
        signature = tuple(tuple(route) for route in routes)
        if signature in seen:
            continue
        seen.add(signature)
        candidates.append(
            RouteFinderCandidate(
                rank=len(candidates) + 1,
                routefinder_rank=len(candidates) + 1,
                variant="routefinder_routes",
                normalized_cost=-float(reward),
                actions=[int(action) for action in candidate_actions],
                customer_routes=routes,
            )
        )
        if len(candidates) >= max(1, max_candidates):
            break
    if not candidates:
        raise RuntimeError("RouteFinder produced no decodable candidate.")
    return candidates


def expand_candidate_variants(
    routefinder_candidates: list[RouteFinderCandidate],
    instance,
    greedy_pack_max_clients: int,
) -> list[RouteFinderCandidate]:
    """Adds the same TW-greedy packing variant used by the POMO benchmark."""

    variants: list[RouteFinderCandidate] = []
    seen: set[tuple[tuple[str, ...], ...]] = set()

    def add_variant(
        candidate: RouteFinderCandidate,
        routes: list[list[str]],
        variant: str,
    ) -> None:
        signature = tuple(tuple(route) for route in routes)
        if signature in seen:
            return
        seen.add(signature)
        variants.append(
            RouteFinderCandidate(
                rank=len(variants) + 1,
                routefinder_rank=candidate.routefinder_rank,
                variant=variant,
                normalized_cost=candidate.normalized_cost,
                actions=candidate.actions,
                customer_routes=routes,
            )
        )

    for candidate in routefinder_candidates:
        add_variant(
            candidate,
            candidate.customer_routes,
            candidate.variant,
        )
        if (
            greedy_pack_max_clients > 0
            and len(instance.clients) <= greedy_pack_max_clients
        ):
            add_variant(
                candidate,
                build_time_window_greedy_routes(
                    candidate.customer_routes,
                    instance,
                ),
                "time_window_greedy_pack",
            )
    return variants


def build_time_window_greedy_routes(
    customer_routes: list[list[str]],
    instance,
) -> list[list[str]]:
    customers_by_name = {customer.name: customer for customer in instance.clients}
    position_by_name: dict[str, int] = {}
    for route in customer_routes:
        for name in route:
            if name not in position_by_name:
                position_by_name[name] = len(position_by_name)

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


def evaluate_candidate(candidate: RouteFinderCandidate, instance) -> dict:
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
    candidate = evaluation["candidate"]
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    feasible = repair_plan.feasible and report.feasible
    if feasible:
        return (
            0,
            report.total_distance,
            len(repair_plan.routes),
            repair_plan.station_insertions,
            candidate.normalized_cost,
        )
    return (
        1,
        -report.served_customers,
        len(report.violations),
        len(repair_plan.unsolved),
        repair_plan.split_count,
        candidate.normalized_cost,
    )


def resolve_output_path(output: Path | None, instance_name: str) -> Path:
    if output is not None:
        return output
    return DEFAULT_RESULTS_DIR / f"{instance_name}_routefinder_repair.json"


def repair_failure_reasons(repair_plan) -> list[str]:
    return sorted(
        {
            str(item.get("reason"))
            for item in repair_plan.unsolved
            if item.get("reason")
        }
    )


def constraint_violations_from_report(report, repair_plan) -> str:
    reasons = repair_failure_reasons(repair_plan)
    return format_constraint_violations(
        {
            "missing_customers": len(report.missing_customers),
            "duplicate_customers": len(report.duplicate_customers),
            "time_window_violations": report.time_window_violations,
            "capacity_violations": report.capacity_violations,
            "energy_violations": report.energy_violations,
            "vehicle_limit_violations": report.vehicle_limit_violations,
            "repair_vehicle_limit_exceeded": int(
                "vehicle_limit_exceeded" in reasons
            ),
        }
    )


def candidate_payload(evaluation: dict) -> dict:
    candidate = evaluation["candidate"]
    repair_plan = evaluation["repair_plan"]
    report = evaluation["report"]
    return {
        "rank": candidate.rank,
        "routefinder_rank": candidate.routefinder_rank,
        "variant": candidate.variant,
        "normalized_vrptw_cost": round(candidate.normalized_cost, 6),
        "customer_routes": candidate.customer_routes,
        "repair_feasible": repair_plan.feasible,
        "checked_feasible": report.feasible,
        "checked_distance": report.total_distance,
        "vehicle_count": len(repair_plan.routes),
        "station_insertions": repair_plan.station_insertions,
        "split_count": repair_plan.split_count,
        "served_customers": report.served_customers,
        "unsolved": repair_plan.unsolved,
    }


def build_solution_payload(
    *,
    status,
    source_path,
    instance,
    instance_data,
    checkpoint,
    device,
    num_augment,
    normalization,
    selected,
    evaluations,
    elapsed_runtime_seconds,
    inference_seconds,
):
    candidate = selected["candidate"]
    repair_plan = selected["repair_plan"]
    report = selected["report"]
    failure_reasons = repair_failure_reasons(repair_plan)
    unsupported_reason = (
        "; ".join(failure_reasons) if status != "solved" else ""
    )
    return {
        "status": status,
        "unsupported_reason": unsupported_reason,
        "source": {
            "path": str(source_path),
            "instance": instance.name,
            "problem_type": instance.problem_type,
        },
        "experiment_record": build_experiment_record(
            instance_name=instance.name,
            instance_size=len(instance.clients),
            method_name="RouteFinder RF-Transformer + EVRP-TW station repair",
            objective_value=report.total_distance,
            runtime_seconds=elapsed_runtime_seconds,
            feasibility_status="feasible" if report.feasible else "infeasible",
            vehicles_used=len(repair_plan.routes),
            constraint_violations=constraint_violations_from_report(
                report,
                repair_plan,
            ),
            random_seed=instance.solver.seed,
            best_solution_found=repair_plan.routes,
            reference_value=None,
            convergence_curve="not captured",
            improvement_over_time=(
                "best distinct augmented RouteFinder candidates are ranked "
                "after shared EVRP-TW repair"
            ),
            search_steps=sum(
                len(item["repair_plan"].attempts) for item in evaluations
            ),
        ),
        "solver": {
            "baseline": "RouteFinder RF-Transformer VRPTW",
            "method_name": "RouteFinder RF-Transformer + EVRP-TW repair",
            "repair": "v3_partial_recharge_label_setting",
            "checkpoint": str(checkpoint),
            "routefinder_commit": "fe0e45b6df118af03c5f42db8b93a351f7629131",
            "torch_version": torch.__version__,
            "device": str(device),
            "num_augment": num_augment,
            "elapsed_runtime_seconds": round(elapsed_runtime_seconds, 3),
            "inference_seconds": round(inference_seconds, 3),
            "seed": instance.solver.seed,
            "unsupported_reason": unsupported_reason,
        },
        "normalization": normalization,
        "candidate": {
            "rank": candidate.rank,
            "routefinder_rank": candidate.routefinder_rank,
            "variant": candidate.variant,
            "normalized_vrptw_cost": round(candidate.normalized_cost, 6),
            "estimated_unrounded_original_distance": round(
                candidate.normalized_cost * normalization["coordinate_scale"],
                3,
            ),
            "actions": candidate.actions,
            "customer_routes": candidate.customer_routes,
        },
        "candidate_evaluations": [
            candidate_payload(evaluation) for evaluation in evaluations
        ],
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
            "vehicle_limit_violations": max(
                report.vehicle_limit_violations,
                int("vehicle_limit_exceeded" in failure_reasons),
            ),
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


def write_solution(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def solve_pipeline(args: argparse.Namespace):
    started = time.perf_counter()
    torch.manual_seed(args.seed)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")
    if args.device == "cuda":
        torch.cuda.manual_seed_all(args.seed)
    torch.set_float32_matmul_precision("medium")

    instance, source_path, instance_data = load_pipeline_instance(args)
    checkpoint = args.checkpoint or default_checkpoint(len(instance.clients))
    if not checkpoint.is_absolute():
        checkpoint = (REPO_ROOT / checkpoint).resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(f"RouteFinder checkpoint not found: {checkpoint}")
    output_path = resolve_output_path(args.output, instance.name)
    device = torch.device(args.device)

    td, normalization = instance_to_tensordict(instance)
    model = load_model(checkpoint)
    env = MTVRPEnv(check_solution=False, load_solutions=False)
    policy = model.policy.to(device).eval()
    official_test = load_official_test_function()

    inference_started = time.perf_counter()
    output = official_test(
        policy,
        env.reset(td).to(device),
        env,
        num_augment=args.num_augment,
        device=device,
    )
    if device.type == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - inference_started

    routefinder_candidates = extract_candidates(
        output,
        instance,
        args.max_candidates,
    )
    candidates = expand_candidate_variants(
        routefinder_candidates,
        instance,
        args.greedy_pack_max_clients,
    )
    evaluations = [
        evaluate_candidate(candidate, instance) for candidate in candidates
    ]
    selected = min(evaluations, key=evaluation_sort_key)
    repair_plan = selected["repair_plan"]
    report = selected["report"]
    status = "solved" if repair_plan.feasible and report.feasible else "unsolved"
    elapsed_runtime_seconds = time.perf_counter() - started
    payload = build_solution_payload(
        status=status,
        source_path=source_path,
        instance=instance,
        instance_data=instance_data,
        checkpoint=checkpoint,
        device=device,
        num_augment=args.num_augment,
        normalization=normalization,
        selected=selected,
        evaluations=evaluations,
        elapsed_runtime_seconds=elapsed_runtime_seconds,
        inference_seconds=inference_seconds,
    )
    write_solution(payload, output_path)
    return status, output_path, payload, report


def print_summary(status, output_path, payload, report) -> None:
    print("RouteFinder + EVRP-TW repair pipeline")
    print(f"  status={status}")
    print(f"  instance={payload['source']['instance']}")
    print(f"  checkpoint={payload['solver']['checkpoint']}")
    print(f"  candidates={len(payload['candidate_evaluations'])}")
    print(f"  inference={payload['solver']['inference_seconds']}s")
    print(f"  total_runtime={payload['solver']['elapsed_runtime_seconds']}s")
    print(
        "  baseline_route_count="
        f"{len(payload['candidate']['customer_routes'])}"
    )
    if payload["experiment_record"]["instance_size"] <= 20:
        print(f"  baseline_routes={payload['candidate']['customer_routes']}")
    print(f"  station_insertions={payload['repair']['station_insertions']}")
    print(f"  split_count={payload['repair']['split_count']}")
    print_benchmark_report(report, solver="RouteFinderEVRPTWRepair")
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
