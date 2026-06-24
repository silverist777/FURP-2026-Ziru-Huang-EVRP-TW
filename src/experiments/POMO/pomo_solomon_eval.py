"""Evaluate POMO VRPTW on Solomon instances.

The model uses VRPTW hard masks only. Electric vehicle constraints are not part
of this experiment.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_ROOT = REPO_ROOT / ".cache" / "pomo_solomon_eval"
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("WANDB_DISABLED", "true")
CACHE_ROOT.mkdir(parents=True, exist_ok=True)
(CACHE_ROOT / "matplotlib").mkdir(parents=True, exist_ok=True)

import torch
from rl4co.models.zoo.pomo import POMO
from rl4co.utils.ops import unbatchify
from rl4co.utils.trainer import RL4COTrainer

from vrptw_support import (
    SolomonLikeVRPTWGenerator,
    StrictCVRPTWEnv,
    check_solomon_actions,
    load_solomon_instances,
    solomon_to_tensordict,
    summarize_gaps,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate POMO VRPTW on Solomon data.")
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "src" / "data" / "Solomon")
    parser.add_argument("--instance", type=str, default=None, help="Evaluate one instance by stem, e.g. C1_2_1.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--train-first", action="store_true")
    parser.add_argument("--train-num-loc", type=int, default=100)
    parser.add_argument("--train-data-size", type=int, default=256)
    parser.add_argument("--val-data-size", type=int, default=64)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-epochs", type=int, default=1)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "src" / "experiments" / "POMO" / "pomo_solomon_eval_results.csv",
    )
    return parser.parse_args()


def choose_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is false.")
    return requested


def make_env(num_loc: int) -> StrictCVRPTWEnv:
    generator = SolomonLikeVRPTWGenerator(
        num_loc=num_loc,
        min_loc=0.0,
        max_loc=150.0,
        capacity=200,
        min_demand=1,
        max_demand=10,
        max_time=1236,
        service_duration=90,
        scale=True,
    )
    return StrictCVRPTWEnv(generator=generator)


def make_model(env: StrictCVRPTWEnv, args: argparse.Namespace) -> POMO:
    return POMO(
        env,
        num_augment=1,
        policy_kwargs={
            "embed_dim": 64,
            "num_encoder_layers": 2,
            "num_heads": 4,
            "feedforward_hidden": 128,
        },
        batch_size=args.batch_size,
        val_batch_size=args.batch_size,
        test_batch_size=args.batch_size,
        train_data_size=args.train_data_size,
        val_data_size=args.val_data_size,
        test_data_size=args.val_data_size,
        optimizer_kwargs={"lr": 1e-4},
        dataloader_num_workers=0,
        log_on_step=True,
    )


def maybe_train(model: POMO, args: argparse.Namespace, device: str) -> None:
    if not args.train_first:
        print("training_skipped: True")
        return
    trainer = RL4COTrainer(
        accelerator="gpu" if device == "cuda" else "cpu",
        devices=1,
        max_epochs=args.max_epochs,
        precision="32-true",
        logger=False,
        enable_checkpointing=False,
        enable_progress_bar=False,
        num_sanity_val_steps=0,
        default_root_dir=str(CACHE_ROOT / "lightning"),
    )
    trainer.fit(model)
    print("training_ok: True")


def evaluate_one(model: POMO, instance, device: str) -> dict[str, object]:
    env = make_env(instance.num_clients)
    td_input = solomon_to_tensordict(instance, device=device)
    td = env.reset(td_input)
    num_starts = env.get_num_starts(td)
    with torch.inference_mode():
        out = model.policy(td, env, phase="test", num_starts=num_starts, return_actions=True)

    rewards = unbatchify(out["reward"], (1, num_starts)).squeeze(1)
    actions = unbatchify(out["actions"], (1, num_starts)).squeeze(1)
    best_idx = rewards[0].argmax()
    best_actions = actions[0, best_idx].detach().cpu().tolist()
    check = check_solomon_actions(instance, best_actions)
    known_cost = instance.known_cost
    gap_pct = (
        None
        if known_cost in (None, 0)
        else (check.predicted_cost - known_cost) / known_cost * 100.0
    )
    return {
        "instance": instance.name,
        "clients": instance.num_clients,
        "vehicles": instance.vehicles,
        "capacity": instance.capacity,
        "known_cost": known_cost,
        "predicted_cost": check.predicted_cost,
        "gap_pct": gap_pct,
        "time_window_violations": check.time_window_violations,
        "capacity_violations": check.capacity_violations,
        "missing_customers": check.missing_customers,
        "duplicate_customers": check.duplicate_customers,
        "depot_return_violations": check.depot_return_violations,
        "all_customers_served": check.all_customers_served,
        "num_starts": num_starts,
    }


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = choose_device(args.device)
    instances = load_solomon_instances(args.data_dir, limit=None)
    if args.instance is not None:
        instances = [instance for instance in instances if instance.name == args.instance]
    if args.limit is not None:
        instances = instances[: args.limit]
    if not instances:
        raise RuntimeError(f"No Solomon .txt instances found in {args.data_dir}")

    print("POMO Solomon VRPTW evaluation")
    print("============================")
    print(f"data_dir: {args.data_dir}")
    print(f"instances: {len(instances)}")
    print(f"clients_range: {min(i.num_clients for i in instances)}..{max(i.num_clients for i in instances)}")
    print(f"device: {device}")
    if device == "cuda":
        print(f"cuda_device_name: {torch.cuda.get_device_name(0)}")
    print("electric_constraints: disabled")

    train_env = make_env(args.train_num_loc)
    model = make_model(train_env, args)
    maybe_train(model, args, device)
    model.eval()
    model.to(device)

    rows = []
    for instance in instances:
        row = evaluate_one(model, instance, device)
        rows.append(row)
        gap = "n/a" if row["gap_pct"] is None else f"{row['gap_pct']:.2f}%"
        print(
            f"{row['instance']}: known={row['known_cost']} pred={row['predicted_cost']:.2f} "
            f"gap={gap} tw={row['time_window_violations']} cap={row['capacity_violations']} "
            f"missing={row['missing_customers']}"
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_gaps(rows)
    print("summary")
    print("-------")
    print(f"results_csv: {args.output_csv}")
    print(f"evaluated_instances: {len(rows)}")
    print(f"mean_gap_pct: {summary['mean_gap_pct']:.2f}")
    print(f"min_gap_pct: {summary['min_gap_pct']:.2f}")
    print(f"max_gap_pct: {summary['max_gap_pct']:.2f}")
    print("evaluation_ok: True")


if __name__ == "__main__":
    main()


