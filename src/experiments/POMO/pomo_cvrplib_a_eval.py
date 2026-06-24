"""Evaluate a small RL4CO POMO CVRP model on CVRPLIB Augerat A instances.

The script can optionally run a short random-data training phase before evaluating.
It reports predicted CVRPLIB-style route cost, known solution cost from .sol,
and percentage gap for each instance.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_ROOT = REPO_ROOT / ".cache" / "pomo_a_eval"
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("WANDB_DISABLED", "true")
CACHE_ROOT.mkdir(parents=True, exist_ok=True)
(CACHE_ROOT / "matplotlib").mkdir(parents=True, exist_ok=True)

import torch
from tensordict import TensorDict
from rl4co.envs import CVRPEnv
from rl4co.models.zoo.pomo import POMO
from rl4co.utils.ops import unbatchify
from rl4co.utils.trainer import RL4COTrainer


@dataclass
class CVRPLIBInstance:
    name: str
    vrp_path: Path
    sol_path: Path | None
    capacity: int
    depot_id: int
    coords_by_id: dict[int, tuple[float, float]]
    demand_by_id: dict[int, int]
    known_cost: int | None

    @property
    def customer_ids(self) -> list[int]:
        return [node_id for node_id in sorted(self.coords_by_id) if node_id != self.depot_id]

    @property
    def num_clients(self) -> int:
        return len(self.customer_ids)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate POMO on src/data/A CVRPLIB instances.")
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "src" / "data" / "A")
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N instances.")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--train-first", action="store_true", help="Run a short random CVRP training phase before eval.")
    parser.add_argument("--train-num-loc", type=int, default=79)
    parser.add_argument("--train-data-size", type=int, default=256)
    parser.add_argument("--val-data-size", type=int, default=64)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--output-csv", type=Path, default=REPO_ROOT / "src" / "experiments" / "POMO" / "pomo_a_eval_results.csv")
    return parser.parse_args()


def choose_device(requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is false.")
    return requested


def parse_vrp(path: Path) -> tuple[int, int, dict[int, tuple[float, float]], dict[int, int]]:
    capacity: int | None = None
    coords: dict[int, tuple[float, float]] = {}
    demands: dict[int, int] = {}
    depot_id: int | None = None
    section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "NODE_COORD_SECTION":
            section = "coords"
            continue
        if line == "DEMAND_SECTION":
            section = "demands"
            continue
        if line == "DEPOT_SECTION":
            section = "depot"
            continue
        if line == "EOF":
            break
        if line.startswith("CAPACITY"):
            capacity = int(line.split(":", 1)[1].strip())
            continue

        parts = line.split()
        if section == "coords" and len(parts) >= 3:
            coords[int(parts[0])] = (float(parts[1]), float(parts[2]))
        elif section == "demands" and len(parts) >= 2:
            demands[int(parts[0])] = int(parts[1])
        elif section == "depot":
            value = int(parts[0])
            if value != -1:
                depot_id = value

    if capacity is None or depot_id is None or not coords or not demands:
        raise ValueError(f"Could not parse required CVRPLIB fields from {path}")
    return capacity, depot_id, coords, demands


def parse_known_cost(path: Path | None) -> int | None:
    if path is None or not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("Cost"):
            return int(line.split()[-1])
    return None


def load_instances(data_dir: Path) -> list[CVRPLIBInstance]:
    instances = []
    for vrp_path in sorted(data_dir.glob("*.vrp")):
        capacity, depot_id, coords, demands = parse_vrp(vrp_path)
        sol_path = vrp_path.with_suffix(".sol")
        instances.append(
            CVRPLIBInstance(
                name=vrp_path.stem,
                vrp_path=vrp_path,
                sol_path=sol_path if sol_path.exists() else None,
                capacity=capacity,
                depot_id=depot_id,
                coords_by_id=coords,
                demand_by_id=demands,
                known_cost=parse_known_cost(sol_path),
            )
        )
    return instances


def instance_to_tensordict(instance: CVRPLIBInstance, device: str) -> TensorDict:
    customer_ids = instance.customer_ids
    all_x = [xy[0] for xy in instance.coords_by_id.values()]
    all_y = [xy[1] for xy in instance.coords_by_id.values()]
    scale = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 1.0)
    min_x, min_y = min(all_x), min(all_y)

    def normalize(node_id: int) -> tuple[float, float]:
        x, y = instance.coords_by_id[node_id]
        return ((x - min_x) / scale, (y - min_y) / scale)

    depot = torch.tensor([normalize(instance.depot_id)], dtype=torch.float32, device=device)
    locs = torch.tensor([[normalize(node_id) for node_id in customer_ids]], dtype=torch.float32, device=device)
    demand = torch.tensor(
        [[instance.demand_by_id[node_id] / instance.capacity for node_id in customer_ids]],
        dtype=torch.float32,
        device=device,
    )
    capacity = torch.tensor([[instance.capacity]], dtype=torch.float32, device=device)
    return TensorDict({"depot": depot, "locs": locs, "demand": demand, "capacity": capacity}, batch_size=[1], device=device)


def rounded_euclidean(a: tuple[float, float], b: tuple[float, float]) -> int:
    return int(math.floor(math.dist(a, b) + 0.5))


def actions_to_cvrplib_cost(instance: CVRPLIBInstance, actions: list[int]) -> int:
    customer_ids = instance.customer_ids
    current_id = instance.depot_id
    total = 0
    visited: set[int] = set()

    for action in actions:
        if action == 0:
            next_id = instance.depot_id
        else:
            if action < 0 or action > len(customer_ids):
                raise ValueError(f"Action {action} out of customer range for {instance.name}")
            next_id = customer_ids[action - 1]
            visited.add(next_id)
        if next_id != current_id:
            total += rounded_euclidean(instance.coords_by_id[current_id], instance.coords_by_id[next_id])
            current_id = next_id
        if len(visited) == len(customer_ids) and current_id == instance.depot_id:
            break

    if current_id != instance.depot_id:
        total += rounded_euclidean(instance.coords_by_id[current_id], instance.coords_by_id[instance.depot_id])
    return total


def make_model(env: CVRPEnv, args: argparse.Namespace) -> POMO:
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
        optimizer_kwargs={"lr": args.lr},
        dataloader_num_workers=0,
        log_on_step=True,
    )


def train_if_requested(model: POMO, args: argparse.Namespace, device: str) -> None:
    if not args.train_first:
        print("training_skipped: True (evaluating current randomly initialized model)")
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


def evaluate_instance(model: POMO, instance: CVRPLIBInstance, device: str) -> dict[str, object]:
    env = CVRPEnv(generator_params={"num_loc": instance.num_clients, "capacity": instance.capacity})
    td = instance_to_tensordict(instance, device)
    reset_td = env.reset(td)
    num_starts = env.get_num_starts(reset_td)
    with torch.inference_mode():
        out = model.policy(reset_td, env, phase="test", num_starts=num_starts, return_actions=True)
    rewards = unbatchify(out["reward"], (1, num_starts)).squeeze(0).squeeze(0)
    actions = unbatchify(out["actions"], (1, num_starts)).squeeze(0).squeeze(0)

    best_idx = rewards.argmax().item()
    best_actions = actions[best_idx].detach().cpu().tolist()
    predicted_cost = actions_to_cvrplib_cost(instance, best_actions)
    known_cost = instance.known_cost
    gap_pct = None if known_cost in (None, 0) else (predicted_cost - known_cost) / known_cost * 100.0
    return {
        "instance": instance.name,
        "clients": instance.num_clients,
        "capacity": instance.capacity,
        "known_cost": known_cost,
        "predicted_cost": predicted_cost,
        "gap_pct": gap_pct,
        "num_starts": num_starts,
    }


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = choose_device(args.device)
    instances = load_instances(args.data_dir)
    if args.limit is not None:
        instances = instances[: args.limit]
    if not instances:
        raise RuntimeError(f"No .vrp files found in {args.data_dir}")

    print("POMO CVRPLIB A-set evaluation")
    print("=============================")
    print(f"data_dir: {args.data_dir}")
    print(f"instances: {len(instances)}")
    print(f"clients_range: {min(i.num_clients for i in instances)}..{max(i.num_clients for i in instances)}")
    print(f"torch: {torch.__version__}")
    print(f"device: {device}")
    if device == "cuda":
        print(f"cuda_device_name: {torch.cuda.get_device_name(0)}")

    train_env = CVRPEnv(generator_params={"num_loc": args.train_num_loc, "capacity": 100})
    model = make_model(train_env, args)
    train_if_requested(model, args, device)
    model.eval()
    model.to(device)

    rows = []
    for instance in instances:
        row = evaluate_instance(model, instance, device)
        rows.append(row)
        gap_text = "n/a" if row["gap_pct"] is None else f"{row['gap_pct']:.2f}%"
        print(
            f"{row['instance']}: clients={row['clients']} known={row['known_cost']} "
            f"pred={row['predicted_cost']} gap={gap_text}"
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    gaps = [row["gap_pct"] for row in rows if row["gap_pct"] is not None]
    print("summary")
    print("-------")
    print(f"results_csv: {args.output_csv}")
    print(f"evaluated_instances: {len(rows)}")
    if gaps:
        print(f"mean_gap_pct: {mean(gaps):.2f}")
        print(f"min_gap_pct: {min(gaps):.2f}")
        print(f"max_gap_pct: {max(gaps):.2f}")
    print("evaluation_ok: True")


if __name__ == "__main__":
    main()
