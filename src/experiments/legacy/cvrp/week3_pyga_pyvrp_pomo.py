"""Run Week 3 experiments for py-ga-VRPTW, PyVRP, and yd-kwon/POMO.

This file is experiment glue only. The solver implementations remain in their
own packages:

- py-ga-VRPTW: external submodule under ``py-ga-VRPTW``.
- PyVRP: installed package in the repo environment.
- yd-kwon/POMO: external submodule under ``external/POMO``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any


os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_EXPERIMENTS = REPO_ROOT / "src" / "experiments"
POMO_CODE = REPO_ROOT / "external" / "POMO" / "NEW_py_ver" / "CVRP" / "POMO"
POMO_ROOT = REPO_ROOT / "external" / "POMO" / "NEW_py_ver"
DEFAULT_INSTANCE = REPO_ROOT / "src" / "data" / "Solomon" / "C101.txt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "src" / "log" / "week3" / "baseline-comparison"
DEFAULT_RESULT_DIR = REPO_ROOT / "src" / "results" / "week3" / "baseline-comparison"
DEFAULT_SEEDS = (1234, 2026, 114514)
DEFAULT_SIZES = (20, 50, 100)
PYVRP_SCALE = 1000

sys.path.insert(0, str(SRC_EXPERIMENTS))

from core.experiment_record import build_experiment_record, format_constraint_violations  # noqa: E402
from core.vrptw_support import SolomonInstance, check_solomon_actions, parse_solomon_instance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or aggregate Week 3 experiment records.")
    parser.add_argument(
        "--method",
        choices=("pyga", "pyvrp", "pomo", "aggregate"),
        required=True,
    )
    parser.add_argument("--instance", type=Path, default=DEFAULT_INSTANCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--result-dir",
        type=Path,
        default=DEFAULT_RESULT_DIR,
        help="Reader-facing Markdown and plot directory used by aggregate mode.",
    )
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--pyga-pop-size", type=int, default=80)
    parser.add_argument("--pyga-generations", type=int, default=50)
    parser.add_argument("--pyvrp-runtime-seconds", type=int, default=1)
    parser.add_argument("--pomo-augmentation", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    return parser.parse_args()


def case_for_size(base: SolomonInstance, size: int) -> SolomonInstance:
    if size > base.num_clients:
        raise ValueError(f"Requested {size} customers, but {base.path} has {base.num_clients}.")
    customers = list(base.customers[:size])
    return replace(
        base,
        name=f"{base.name}_{size}",
        customers=customers,
        known_cost=None if size != base.num_clients else base.known_cost,
    )


def route_distance(instance: SolomonInstance, routes: list[list[int]]) -> float:
    nodes = [instance.depot, *instance.customers]
    total = 0.0
    for route in routes:
        current = 0
        for node in route:
            total += math.dist(
                (nodes[current].x, nodes[current].y),
                (nodes[node].x, nodes[node].y),
            )
            current = node
        total += math.dist((nodes[current].x, nodes[current].y), (nodes[0].x, nodes[0].y))
    return total


def routes_to_actions(routes: list[list[int]]) -> list[int]:
    actions: list[int] = []
    for route in routes:
        actions.extend(route)
        actions.append(0)
    return actions


def violations_for_routes(instance: SolomonInstance, routes: list[list[int]]) -> tuple[str, bool, float]:
    check = check_solomon_actions(instance, routes_to_actions(routes))
    violations = format_constraint_violations(
        {
            "missing_customers": check.missing_customers,
            "duplicate_customers": check.duplicate_customers,
            "time_window_violations": check.time_window_violations,
            "capacity_violations": check.capacity_violations,
            "depot_return_violations": check.depot_return_violations,
        }
    )
    return violations, check.feasible, check.predicted_cost


def build_row(
    *,
    instance: SolomonInstance,
    method_name: str,
    objective: float | None,
    runtime: float | None,
    routes: list[list[int]],
    seed: int,
    constraint_scope: str,
    source_detail: str,
    convergence_curve: Any = None,
    improvement_over_time: Any = None,
    generations: int | None = None,
    search_steps: int | None = None,
) -> dict[str, Any]:
    violations, feasible, checked_cost = violations_for_routes(instance, routes)
    objective_value = checked_cost if objective is None else objective
    row = build_experiment_record(
        instance_name=instance.name,
        instance_size=instance.num_clients,
        method_name=method_name,
        objective_value=objective_value,
        runtime_seconds=runtime,
        feasibility_status=(
            "feasible under Solomon TW/capacity check; E disabled"
            if feasible
            else "infeasible under Solomon TW/capacity check; E disabled"
        ),
        vehicles_used=len(routes),
        constraint_violations=violations,
        random_seed=seed,
        best_solution_found=routes,
        reference_value=instance.known_cost,
        convergence_curve=convergence_curve,
        improvement_over_time=improvement_over_time,
        generations=generations,
        search_steps=search_steps,
    )
    row.update(
        {
            "method": method_name,
            "size_group": size_group(instance.num_clients),
            "source_instance": str(instance.path.relative_to(REPO_ROOT)),
            "constraint_scope": constraint_scope,
            "source_detail": source_detail,
            "is_feasible": str(feasible),
        }
    )
    return row


def size_group(size: int) -> str:
    if size <= 20:
        return "small"
    if size <= 50:
        return "medium"
    return "large"


def write_records(rows: list[dict[str, Any]], output_dir: Path, method: str) -> Path:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"week3_{method}_records.csv"
    if not rows:
        raise RuntimeError(f"No rows produced for {method}.")
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"records_csv: {path}")
    return path


def run_pyga(args: argparse.Namespace) -> None:
    base = parse_solomon_instance(args.instance)
    rows: list[dict[str, Any]] = []
    for size in args.sizes:
        instance = case_for_size(base, size)
        for seed in args.seeds:
            rows.append(run_pyga_once(args, instance, seed))
    write_records(rows, args.output_dir, "pyga")


def run_pyga_once(args: argparse.Namespace, instance: SolomonInstance, seed: int) -> dict[str, Any]:
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_path = raw_dir / f"pyga_{instance.name}_seed{seed}.csv"
    log_path = raw_dir / f"pyga_{instance.name}_seed{seed}.log"
    cmd = [
        sys.executable,
        str(SRC_EXPERIMENTS / "GA" / "run_py_ga_vrptw.py"),
        "--instance",
        instance.path.stem,
        "--ind-size",
        str(instance.num_clients),
        "--pop-size",
        str(args.pyga_pop_size),
        "--generations",
        str(args.pyga_generations),
        "--unit-cost",
        "1",
        "--init-cost",
        "0",
        "--wait-cost",
        "0",
        "--delay-cost",
        "0",
        "--seed",
        str(seed),
        "--export-csv",
        "--output-csv",
        str(csv_path),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    runtime = time.perf_counter() - started
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    routes = parse_pyga_routes(completed.stdout)
    convergence = pyga_convergence(csv_path)
    final_objective = convergence[-1]["best_objective"] if convergence else parse_total_cost(completed.stdout)
    return build_row(
        instance=instance,
        method_name="py-ga-VRPTW",
        objective=final_objective,
        runtime=runtime,
        routes=routes,
        seed=seed,
        constraint_scope=(
            "Solomon VRPTW check; py-ga run with unit_cost=1, init/wait/delay cost=0; E disabled"
        ),
        source_detail=f"external py-ga-VRPTW; pop={args.pyga_pop_size}; generations={args.pyga_generations}",
        convergence_curve=convergence,
        improvement_over_time=convergence,
        generations=args.pyga_generations,
        search_steps=args.pyga_pop_size * args.pyga_generations,
    )


def parse_total_cost(stdout: str) -> float | None:
    match = re.search(r"Total cost:\s*([0-9.]+)", stdout)
    return float(match.group(1)) if match else None


def parse_pyga_routes(stdout: str) -> list[list[int]]:
    routes: list[list[int]] = []
    for line in stdout.splitlines():
        if "Vehicle" not in line or "route:" not in line:
            continue
        _, route_part = line.split("route:", 1)
        nums = [int(item) for item in re.findall(r"\d+", route_part)]
        route = [num for num in nums if num != 0]
        if route:
            routes.append(route)
    return routes


def pyga_convergence(path: Path) -> list[dict[str, float | int]]:
    rows = read_csv(path)
    curve: list[dict[str, float | int]] = []
    best_so_far: float | None = None
    start_best: float | None = None
    previous_best: float | None = None
    for row in rows:
        generation = int(row["generation"]) + 1
        generation_best = 1.0 / float(row["max_fitness"])
        best_so_far = generation_best if best_so_far is None else min(best_so_far, generation_best)
        start_best = best_so_far if start_best is None else start_best
        curve.append(
            {
                "generation": generation,
                "generation_best": round(generation_best, 3),
                "best_objective": round(best_so_far, 3),
                "improvement_from_start": round(start_best - best_so_far, 3),
                "improvement_from_previous": round(
                    0.0 if previous_best is None else previous_best - best_so_far,
                    3,
                ),
            }
        )
        previous_best = best_so_far
    return curve


def run_pyvrp(args: argparse.Namespace) -> None:
    from pyvrp import Model
    from pyvrp.stop import MaxRuntime

    base = parse_solomon_instance(args.instance)
    rows: list[dict[str, Any]] = []
    for size in args.sizes:
        instance = case_for_size(base, size)
        for seed in args.seeds:
            started = time.perf_counter()
            model = build_pyvrp_model(instance, Model)
            result = model.solve(MaxRuntime(args.pyvrp_runtime_seconds), seed=seed, display=False)
            runtime = time.perf_counter() - started
            routes = pyvrp_routes(result.best, instance)
            rows.append(
                build_row(
                    instance=instance,
                    method_name="PyVRP",
                    objective=result.best.distance() / PYVRP_SCALE,
                    runtime=runtime,
                    routes=routes,
                    seed=seed,
                    constraint_scope="Solomon VRPTW: capacity and time windows enforced; E disabled",
                    source_detail=f"PyVRP HGS; MaxRuntime={args.pyvrp_runtime_seconds}s",
                    convergence_curve="not captured by PyVRP API",
                    improvement_over_time="not captured by PyVRP API",
                    search_steps=None,
                )
            )
    write_records(rows, args.output_dir, "pyvrp")


def scaled(value: float) -> int:
    return int(round(value * PYVRP_SCALE))


def build_pyvrp_model(instance: SolomonInstance, model_cls):
    model = model_cls()
    depot = model.add_depot(
        x=scaled(instance.depot.x),
        y=scaled(instance.depot.y),
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
        name=str(instance.depot.cust_no),
    )
    clients = [
        model.add_client(
            x=scaled(customer.x),
            y=scaled(customer.y),
            delivery=int(customer.demand),
            service_duration=scaled(customer.service_time),
            tw_early=scaled(customer.ready_time),
            tw_late=scaled(customer.due_time),
            name=str(customer.cust_no),
        )
        for customer in instance.customers
    ]
    model.add_vehicle_type(
        num_available=instance.vehicles,
        capacity=int(instance.capacity),
        start_depot=depot,
        end_depot=depot,
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
    )
    original = [instance.depot, *instance.customers]
    locations = [depot, *clients]
    for frm_idx, frm in enumerate(locations):
        for to_idx, to in enumerate(locations):
            if frm is to:
                continue
            distance = scaled(
                math.dist(
                    (original[frm_idx].x, original[frm_idx].y),
                    (original[to_idx].x, original[to_idx].y),
                )
            )
            model.add_edge(frm, to, distance=distance, duration=distance)
    return model


def pyvrp_routes(solution, instance: SolomonInstance) -> list[list[int]]:
    valid_indices = set(range(1, instance.num_clients + 1))
    return [
        [customer_idx for customer_idx in route.visits() if customer_idx in valid_indices]
        for route in solution.routes()
    ]


def run_pomo(args: argparse.Namespace) -> None:
    import torch

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")
    if not POMO_CODE.exists():
        raise RuntimeError("external/POMO is missing. Run: git submodule update --init external/POMO")

    sys.path.insert(0, str(POMO_CODE))
    sys.path.insert(0, str(POMO_CODE.parent))
    sys.path.insert(0, str(POMO_ROOT))
    from CVRPEnv import CVRPEnv
    from CVRPModel import CVRPModel
    from CVRProblemDef import augment_xy_data_by_8_fold

    device = torch.device(args.device)
    torch.set_default_device(device)
    model = load_pomo_model(CVRPModel, torch, device)
    base = parse_solomon_instance(args.instance)
    rows: list[dict[str, Any]] = []
    for size in args.sizes:
        instance = case_for_size(base, size)
        for seed in args.seeds:
            torch.manual_seed(seed)
            rows.append(
                run_pomo_once(
                    args,
                    instance,
                    seed,
                    model,
                    device,
                    torch,
                    CVRPEnv,
                    augment_xy_data_by_8_fold,
                )
            )
    write_records(rows, args.output_dir, "pomo")


def load_pomo_model(model_cls, torch_module, device):
    model_params = {
        "embedding_dim": 128,
        "sqrt_embedding_dim": 128**0.5,
        "encoder_layer_num": 6,
        "qkv_dim": 16,
        "head_num": 8,
        "logit_clipping": 10,
        "ff_hidden_dim": 512,
        "eval_type": "argmax",
    }
    checkpoint_path = POMO_CODE / "result" / "saved_CVRP100_model" / "checkpoint-30500.pt"
    model = model_cls(**model_params).to(device)
    checkpoint = torch_module.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def run_pomo_once(
    args: argparse.Namespace,
    instance: SolomonInstance,
    seed: int,
    model,
    device,
    torch_module,
    env_cls,
    augment_xy_data_by_8_fold,
) -> dict[str, Any]:
    started = time.perf_counter()
    depot_xy, node_xy, node_demand = normalize_for_pomo(instance, torch_module)
    aug_factor = 8 if args.pomo_augmentation else 1
    if args.pomo_augmentation:
        depot_xy = augment_xy_data_by_8_fold(depot_xy)
        node_xy = augment_xy_data_by_8_fold(node_xy)
        node_demand = node_demand.repeat(8, 1)
    depot_xy = depot_xy.to(device)
    node_xy = node_xy.to(device)
    node_demand = node_demand.to(device)

    env = env_cls(problem_size=instance.num_clients, pomo_size=instance.num_clients)
    env.FLAG__use_saved_problems = True
    env.saved_depot_xy = depot_xy
    env.saved_node_xy = node_xy
    env.saved_node_demand = node_demand
    env.saved_index = 0

    with torch_module.inference_mode():
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
    routes = actions_to_routes(actions)
    runtime = time.perf_counter() - started
    return build_row(
        instance=instance,
        method_name="yd-kwon/POMO",
        objective=None,
        runtime=runtime,
        routes=routes,
        seed=seed,
        constraint_scope=(
            "POMO CVRP100 checkpoint inference; TW checked after rollout; E disabled"
        ),
        source_detail=(
            f"yd-kwon/POMO checkpoint-30500.pt; augmentation={args.pomo_augmentation}; "
            f"best_aug={aug_idx}; best_pomo={pomo_idx}"
        ),
        convergence_curve="single inference rollout; no training curve",
        improvement_over_time="not applicable during inference",
        search_steps=len(actions),
    )


def normalize_for_pomo(instance: SolomonInstance, torch_module):
    rows = [instance.depot, *instance.customers]
    xs = [row.x for row in rows]
    ys = [row.y for row in rows]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1.0)
    depot_xy = torch_module.tensor(
        [[[(instance.depot.x - min_x) / span, (instance.depot.y - min_y) / span]]],
        dtype=torch_module.float32,
    )
    node_xy = torch_module.tensor(
        [
            [
                [(customer.x - min_x) / span, (customer.y - min_y) / span]
                for customer in instance.customers
            ]
        ],
        dtype=torch_module.float32,
    )
    node_demand = torch_module.tensor(
        [[customer.demand / instance.capacity for customer in instance.customers]],
        dtype=torch_module.float32,
    )
    return depot_xy, node_xy, node_demand


def actions_to_routes(actions: list[int]) -> list[list[int]]:
    routes: list[list[int]] = []
    current: list[int] = []
    seen: set[int] = set()
    for raw_action in actions:
        action = int(raw_action)
        if action == 0:
            if current:
                routes.append(current)
                current = []
            continue
        if action in seen:
            continue
        current.append(action)
        seen.add(action)
    if current:
        routes.append(current)
    return routes


def aggregate(args: argparse.Namespace) -> None:
    raw_dir = args.output_dir / "raw"
    records: list[dict[str, str]] = []
    for method in ("pyga", "pyvrp", "pomo"):
        path = raw_dir / f"week3_{method}_records.csv"
        if path.exists():
            records.extend(read_csv(path))
    if not records:
        raise RuntimeError(f"No method record CSVs found under {raw_dir}.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.result_dir.mkdir(parents=True, exist_ok=True)
    combined_csv = args.output_dir / "week3_raw_records.csv"
    write_csv(combined_csv, records)
    summary = build_summary(records)
    summary_csv = args.output_dir / "week3_summary_by_method_size.csv"
    write_csv(summary_csv, summary)
    summary_md = args.result_dir / "summary.md"
    write_summary_markdown(summary_md, records, summary)
    plot_outputs(args.result_dir, records, summary)
    print(f"combined_csv: {combined_csv}")
    print(f"summary_csv: {summary_csv}")
    print(f"summary_markdown: {summary_md}")


def build_summary(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in records:
        key = (row["size_group"], row["instance_size"], row["method_name"])
        grouped.setdefault(key, []).append(row)

    summary: list[dict[str, Any]] = []
    for (group, size, method), rows in sorted(grouped.items(), key=lambda item: (int(item[0][1]), item[0][2])):
        objectives = [float(row["objective_value"]) for row in rows if row.get("objective_value")]
        runtimes = [float(row["runtime_seconds"]) for row in rows if row.get("runtime_seconds")]
        vehicles = [float(row["vehicles_used"]) for row in rows if row.get("vehicles_used")]
        feasible_count = sum(row["is_feasible"] == "True" for row in rows)
        summary.append(
            {
                "size_group": group,
                "instance_size": int(size),
                "method_name": method,
                "runs": len(rows),
                "feasible_rate": round(feasible_count / len(rows), 3),
                "best_objective": round(min(objectives), 3) if objectives else "",
                "avg_objective": round(statistics.mean(objectives), 3) if objectives else "",
                "std_objective": round(statistics.pstdev(objectives), 3) if len(objectives) > 1 else 0,
                "avg_runtime_seconds": round(statistics.mean(runtimes), 3) if runtimes else "",
                "avg_vehicles_used": round(statistics.mean(vehicles), 3) if vehicles else "",
            }
        )
    add_best_observed_gaps(summary)
    return summary


def add_best_observed_gaps(summary: list[dict[str, Any]]) -> None:
    best_by_size: dict[int, float] = {}
    for row in summary:
        objective = row["best_objective"]
        if objective == "":
            continue
        size = int(row["instance_size"])
        best_by_size[size] = min(best_by_size.get(size, float("inf")), float(objective))
    for row in summary:
        objective = row["best_objective"]
        best = best_by_size.get(int(row["instance_size"]))
        row["gap_to_best_observed_pct"] = (
            ""
            if objective == "" or not best
            else round((float(objective) - best) / best * 100.0, 3)
        )


def write_summary_markdown(
    path: Path,
    records: list[dict[str, str]],
    summary: list[dict[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8") as file:
        file.write("# Week 3 Experiment Summary\n\n")
        file.write("## Aggregated Results\n\n")
        write_md_table(file, summary)
        file.write("\n## Per-run Records\n\n")
        per_run_fields = [
            "instance_size",
            "method_name",
            "random_seed",
            "is_feasible",
            "objective_value",
            "runtime_seconds",
            "vehicles_used",
            "constraint_violations",
        ]
        write_md_table(file, [{field: row.get(field, "") for field in per_run_fields} for row in records])


def write_md_table(file, rows: list[dict[str, Any]]) -> None:
    if not rows:
        file.write("(empty)\n")
        return
    headers = list(rows[0].keys())
    file.write("| " + " | ".join(headers) + " |\n")
    file.write("| " + " | ".join("---" for _ in headers) + " |\n")
    for row in rows:
        file.write("| " + " | ".join(escape_md(row.get(header, "")) for header in headers) + " |\n")


def escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def plot_outputs(result_dir: Path, records: list[dict[str, str]], summary: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir = result_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    methods = sorted({row["method_name"] for row in summary})
    sizes = sorted({int(row["instance_size"]) for row in summary})

    fig, ax = plt.subplots(figsize=(8, 5))
    for method in methods:
        xs: list[int] = []
        ys: list[float] = []
        for size in sizes:
            row = find_summary(summary, method, size)
            if row and row["avg_objective"] != "":
                xs.append(size)
                ys.append(float(row["avg_objective"]))
        if xs:
            ax.plot(xs, ys, marker="o", linewidth=2, label=method)
    ax.set_xlabel("Customers")
    ax.set_ylabel("Average objective")
    ax.set_title("Week 3 objective by instance size")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "objective_by_size.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for method in methods:
        xs = []
        ys = []
        for size in sizes:
            row = find_summary(summary, method, size)
            if row and row["avg_runtime_seconds"] != "":
                xs.append(size)
                ys.append(float(row["avg_runtime_seconds"]))
        if xs:
            ax.plot(xs, ys, marker="o", linewidth=2, label=method)
    ax.set_xlabel("Customers")
    ax.set_ylabel("Average runtime (s)")
    ax.set_title("Week 3 runtime by instance size")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "runtime_by_size.png", dpi=200)
    plt.close(fig)

    plot_pyga_convergence(records, plot_dir, plt)


def find_summary(summary: list[dict[str, Any]], method: str, size: int) -> dict[str, Any] | None:
    for row in summary:
        if row["method_name"] == method and int(row["instance_size"]) == size:
            return row
    return None


def plot_pyga_convergence(records: list[dict[str, str]], plot_dir: Path, plt) -> None:
    pyga_rows = [
        row for row in records if row["method_name"] == "py-ga-VRPTW" and row["random_seed"] == str(DEFAULT_SEEDS[0])
    ]
    if not pyga_rows:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for row in sorted(pyga_rows, key=lambda item: int(item["instance_size"])):
        curve = json.loads(row["convergence_curve"])
        xs = [point["generation"] for point in curve]
        ys = [point["best_objective"] for point in curve]
        ax.plot(xs, ys, linewidth=2, label=f"{row['instance_size']} customers")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Best-so-far objective")
    ax.set_title("py-ga-VRPTW best-so-far convergence, seed 1234")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "pyga_convergence_seed1234.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for row in sorted(pyga_rows, key=lambda item: int(item["instance_size"])):
        curve = json.loads(row["convergence_curve"])
        xs = [point["generation"] for point in curve]
        ys = [point["generation_best"] for point in curve]
        ax.plot(xs, ys, linewidth=2, label=f"{row['instance_size']} customers")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Generation-best objective")
    ax.set_title("py-ga-VRPTW generation-best objective, seed 1234")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "pyga_generation_best_seed1234.png", dpi=200)
    plt.close(fig)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    if args.method == "pyga":
        run_pyga(args)
    elif args.method == "pyvrp":
        run_pyvrp(args)
    elif args.method == "pomo":
        run_pomo(args)
    else:
        aggregate(args)
    print("week3_experiment_ok: True")


if __name__ == "__main__":
    main()
