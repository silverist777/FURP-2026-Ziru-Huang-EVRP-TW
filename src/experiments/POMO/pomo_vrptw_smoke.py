"""Smoke test for POMO on capacitated VRP with time windows.

This uses synthetic Solomon-like VRPTW data. It verifies training, inference,
and hard-mask feasibility without adding electric vehicle constraints.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_ROOT = REPO_ROOT / ".cache" / "pomo_vrptw_smoke"
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("WANDB_DISABLED", "true")
CACHE_ROOT.mkdir(parents=True, exist_ok=True)
(CACHE_ROOT / "matplotlib").mkdir(parents=True, exist_ok=True)

import torch
from lightning.pytorch.callbacks import ModelCheckpoint
from lightning.pytorch.loggers import CSVLogger
from rl4co.models.zoo.pomo import POMO
from rl4co.utils.ops import unbatchify
from rl4co.utils.trainer import RL4COTrainer

from vrptw_support import (
    SolomonLikeVRPTWGenerator,
    StrictCVRPTWEnv,
    check_tensordict_actions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="POMO VRPTW smoke test.")
    parser.add_argument("--num-loc", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--train-data-size", type=int, default=256)
    parser.add_argument("--val-data-size", type=int, default=64)
    parser.add_argument("--infer-batch-size", type=int, default=4)
    parser.add_argument("--max-epochs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=REPO_ROOT / "src" / "experiments" / "POMO" / "runs",
        help="Directory where training logs and model checkpoints are saved.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Optional run folder name. Defaults to a timestamped name.",
    )
    parser.add_argument(
        "--save-every-epoch",
        action="store_true",
        help="Save one checkpoint per epoch instead of only last.ckpt.",
    )
    parser.add_argument(
        "--no-save-final-model",
        action="store_true",
        help="Skip saving final_model_state_dict.pt after training.",
    )
    parser.add_argument(
        "--enable-progress-bar",
        action="store_true",
        help="Show Lightning's progress bar. Disabled by default for Windows console compatibility.",
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
        max_time=480,
        service_duration=10,
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


def make_run_dir(args: argparse.Namespace) -> Path:
    run_name = args.run_name
    if run_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"vrptw_smoke_seed{args.seed}_epochs{args.max_epochs}_{timestamp}"
    run_dir = args.runs_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_run_args(args: argparse.Namespace, run_dir: Path) -> None:
    serializable_args = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }
    (run_dir / "args.json").write_text(
        json.dumps(serializable_args, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = choose_device(args.device)
    env = make_env(args.num_loc)
    model = make_model(env, args)
    run_dir = make_run_dir(args)
    save_run_args(args, run_dir)
    checkpoint_dir = run_dir / "checkpoints"
    checkpoint_callback = ModelCheckpoint(
        dirpath=str(checkpoint_dir),
        filename="epoch{epoch:02d}-step{step}",
        save_last=True,
        save_top_k=-1 if args.save_every_epoch else 0,
        every_n_epochs=1,
    )
    csv_logger = CSVLogger(save_dir=str(run_dir), name="csv_logs")

    print("POMO VRPTW smoke")
    print("================")
    print(f"torch: {torch.__version__}")
    print(f"device: {device}")
    if device == "cuda":
        print(f"cuda_device_name: {torch.cuda.get_device_name(0)}")
    print("electric_constraints: disabled")

    trainer = RL4COTrainer(
        accelerator="gpu" if device == "cuda" else "cpu",
        devices=1,
        max_epochs=args.max_epochs,
        precision="32-true",
        logger=csv_logger,
        callbacks=[checkpoint_callback],
        enable_checkpointing=True,
        enable_progress_bar=args.enable_progress_bar,
        num_sanity_val_steps=0,
        default_root_dir=str(run_dir / "lightning"),
    )
    trainer.fit(model)
    print("training_ok: True")
    print(f"run_dir: {run_dir}")
    print(f"log_dir: {csv_logger.log_dir}")
    print(f"checkpoint_dir: {checkpoint_dir}")
    if checkpoint_callback.last_model_path:
        print(f"last_checkpoint: {checkpoint_callback.last_model_path}")
    if not args.no_save_final_model:
        final_model_path = run_dir / "final_model_state_dict.pt"
        torch.save(model.state_dict(), final_model_path)
        print(f"final_model_state_dict: {final_model_path}")

    model.eval()
    model.to(device)
    sample = env.generator([args.infer_batch_size]).to(device)
    td = env.reset(sample)
    num_starts = env.get_num_starts(td)
    with torch.inference_mode():
        out = model.policy(td, env, phase="test", num_starts=num_starts, return_actions=True)

    rewards = unbatchify(out["reward"], (1, num_starts)).squeeze(1)
    actions = unbatchify(out["actions"], (1, num_starts)).squeeze(1)
    best_idx = rewards[0].argmax()
    best_actions = actions[0, best_idx].detach().cpu().tolist()
    check = check_tensordict_actions(td.detach().cpu(), best_actions)

    print("inference_ok: True")
    print(f"time_window_violations: {check.time_window_violations}")
    print(f"capacity_violations: {check.capacity_violations}")
    print(f"missing_customers: {check.missing_customers}")
    print(f"all_customers_served: {check.all_customers_served}")
    print(f"depot_return_violations: {check.depot_return_violations}")
    print(f"mean_distance: {-rewards.max(dim=-1).values.mean().item():.6f}")
    if not check.feasible:
        raise RuntimeError("VRPTW smoke inference produced an infeasible route.")


if __name__ == "__main__":
    main()
