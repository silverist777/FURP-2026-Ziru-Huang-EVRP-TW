"""Run yd-kwon/POMO CVRP checkpoint on the method-comparison instances.

The upstream POMO repository provides a CVRP100 checkpoint, not a VRPTW or
EVRP-TW checkpoint. This script therefore lets POMO choose routes using only
coordinates, demand, and vehicle capacity, then checks the produced routes
against the original time windows with the project-local checker.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
POMO_ROOT = REPO_ROOT / "external" / "POMO" / "NEW_py_ver"
POMO_CVRP_ROOT = POMO_ROOT / "CVRP"
POMO_CVRP_CODE = POMO_CVRP_ROOT / "POMO"
DEFAULT_CHECKPOINT = (
    POMO_CVRP_CODE / "result" / "saved_CVRP100_model" / "checkpoint-30500.pt"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "src" / "results" / "method_comparison_ydkwon_pomo"

sys.path.insert(0, str(POMO_CVRP_CODE))
sys.path.insert(0, str(POMO_CVRP_ROOT))
sys.path.insert(0, str(POMO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "experiments"))
sys.path.insert(0, str(REPO_ROOT / "src" / "experiments" / "POMO"))

from CVRPEnv import CVRPEnv  # noqa: E402
from CVRPModel import CVRPModel  # noqa: E402
from CVRProblemDef import augment_xy_data_by_8_fold  # noqa: E402
from method_comparison_table import (  # noqa: E402
    DEFAULT_HOLMBERGER,
    DEFAULT_SOLOMON,
    build_cases,
)
from vrptw_support import check_solomon_actions  # noqa: E402


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the upstream yd-kwon/POMO CVRP checkpoint on comparison cases."
    )
    parser.add_argument("--solomon", type=Path, default=DEFAULT_SOLOMON)
    parser.add_argument("--holmberger", type=Path, default=DEFAULT_HOLMBERGER)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--augmentation", action="store_true", help="Use POMO 8-fold coordinate augmentation.")
    return parser.parse_args()


def normalize_case(case) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    rows = [case.instance.depot, *case.instance.customers]
    xs = [row.x for row in rows]
    ys = [row.y for row in rows]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1.0)

    depot_xy = torch.tensor(
        [[[(case.instance.depot.x - min_x) / span, (case.instance.depot.y - min_y) / span]]],
        dtype=torch.float32,
    )
    node_xy = torch.tensor(
        [
            [
                [(customer.x - min_x) / span, (customer.y - min_y) / span]
                for customer in case.instance.customers
            ]
        ],
        dtype=torch.float32,
    )
    node_demand = torch.tensor(
        [[customer.demand / case.instance.capacity for customer in case.instance.customers]],
        dtype=torch.float32,
    )
    return depot_xy, node_xy, node_demand


def load_model(checkpoint_path: Path, device: torch.device) -> CVRPModel:
    model = CVRPModel(**MODEL_PARAMS).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def rollout_case(case, model: CVRPModel, device: torch.device, use_augmentation: bool) -> dict[str, object]:
    started = time.perf_counter()
    depot_xy, node_xy, node_demand = normalize_case(case)
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

    env = CVRPEnv(problem_size=case.instance.num_clients, pomo_size=case.instance.num_clients)
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
    flat_best = rewards.reshape(-1).argmax()
    aug_idx = int(flat_best // env.pomo_size)
    pomo_idx = int(flat_best % env.pomo_size)
    actions = env.selected_node_list[aug_idx, pomo_idx].detach().cpu().tolist()
    check = check_solomon_actions(case.instance, actions)
    elapsed = time.perf_counter() - started
    selected = (
        ",".join(str(num) for num in case.selected_cust_no)
        if case.client_count < 100
        else f"all customers 1-{case.client_count}"
    )
    return {
        "method": "yd-kwon/POMO CVRP",
        "clients": case.client_count,
        "instance": case.label,
        "source": case.source,
        "selected_cust_no": selected,
        "objective_value": round(check.predicted_cost, 3),
        "feasibility_status_under_added_constraints": (
            "feasible under TW/capacity check; E disabled"
            if check.feasible
            else "infeasible under TW/capacity check; E disabled"
        ),
        "runtime_seconds": round(elapsed, 3),
        "convergence_details": (
            f"checkpoint=CVRP100 epoch 30500; aug_factor={aug_factor}; "
            f"best_aug={aug_idx}; best_pomo={pomo_idx}; "
            f"missing={check.missing_customers}; tw_violations={check.time_window_violations}; "
            f"capacity_violations={check.capacity_violations}; "
            f"depot_return_violations={check.depot_return_violations}"
        ),
        "seed": args_seed(),
        "model_status": "upstream yd-kwon/POMO CVRP100 pretrained checkpoint; no TW/E in model",
    }


_ARGS_SEED = 1234


def args_seed() -> int:
    return _ARGS_SEED


def write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    headers = [
        "method",
        "clients",
        "source",
        "selected_cust_no",
        "objective_value",
        "feasibility_status_under_added_constraints",
        "runtime_seconds",
        "convergence_details",
        "model_status",
    ]
    with path.open("w", encoding="utf-8") as file:
        file.write("# yd-kwon/POMO Method Comparison Run\n\n")
        file.write(
            "The upstream checkpoint is trained for CVRP100. It does not model "
            "time windows or electric-vehicle constraints; those are checked after rollout.\n\n"
        )
        file.write("| " + " | ".join(headers) + " |\n")
        file.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for row in rows:
            values = [str(row[header]).replace("|", "\\|") for header in headers]
            file.write("| " + " | ".join(values) + " |\n")


def main() -> None:
    global _ARGS_SEED
    args = parse_args()
    _ARGS_SEED = args.seed
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")
    if not args.checkpoint.exists():
        raise FileNotFoundError(args.checkpoint)

    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    torch.set_default_device(device)
    model = load_model(args.checkpoint, device)
    cases = build_cases(args.solomon, args.holmberger, args.seed)

    rows = [rollout_case(case, model, device, args.augmentation) for case in cases]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "ydkwon_pomo_method_comparison.csv"
    md_path = args.output_dir / "ydkwon_pomo_method_comparison.md"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(rows, md_path)

    print("ydkwon_pomo_method_comparison_ok: True")
    print(f"csv: {csv_path}")
    print(f"markdown: {md_path}")
    for row in rows:
        print(
            f"{row['method']} clients={row['clients']} objective={row['objective_value']} "
            f"runtime={row['runtime_seconds']} {row['feasibility_status_under_added_constraints']}"
        )


if __name__ == "__main__":
    main()


