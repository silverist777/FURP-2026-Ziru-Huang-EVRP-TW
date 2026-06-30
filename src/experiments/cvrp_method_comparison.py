"""Compare GA, PyVRP, and yd-kwon/POMO on pure CVRP cases.

The cases match the earlier method-comparison setup:
20/50/100 clients are sampled from Solomon C101, and 200 clients come from
Holmberger C1_2_1. This script ignores time windows and EV constraints.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import time
from pathlib import Path

import torch
from pyvrp import Model
from pyvrp.stop import MaxRuntime


REPO_ROOT = Path(__file__).resolve().parents[2]
POMO_ROOT = REPO_ROOT / "external" / "POMO" / "NEW_py_ver"
POMO_CVRP_ROOT = POMO_ROOT / "CVRP"
POMO_CVRP_CODE = POMO_CVRP_ROOT / "POMO"
DEFAULT_CHECKPOINT = POMO_CVRP_CODE / "result" / "saved_CVRP100_model" / "checkpoint-30500.pt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "src" / "results" / "method_comparison_cvrp"
SCALE = 1000

sys.path.insert(0, str(POMO_CVRP_CODE))
sys.path.insert(0, str(POMO_CVRP_ROOT))
sys.path.insert(0, str(POMO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "experiments"))
sys.path.insert(0, str(REPO_ROOT / "src" / "experiments" / "POMO"))

from CVRPEnv import CVRPEnv  # noqa: E402
from CVRPModel import CVRPModel  # noqa: E402
from CVRProblemDef import augment_xy_data_by_8_fold  # noqa: E402
from method_comparison_table import DEFAULT_HOLMBERGER, DEFAULT_SOLOMON, build_cases  # noqa: E402


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
    parser = argparse.ArgumentParser(description="Generate a pure-CVRP comparison table.")
    parser.add_argument("--solomon", type=Path, default=DEFAULT_SOLOMON)
    parser.add_argument("--holmberger", type=Path, default=DEFAULT_HOLMBERGER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--no-pomo-augmentation", action="store_true")
    parser.add_argument("--pyvrp-runtime-seconds", type=int, default=1)
    parser.add_argument("--ga-pop-size", type=int, default=240)
    parser.add_argument("--ga-generations", type=int, default=220)
    return parser.parse_args()


def euclidean(a, b) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def route_distance(instance, routes: list[list[int]]) -> float:
    nodes = [instance.depot, *instance.customers]
    total = 0.0
    for route in routes:
        current = 0
        for node in route:
            total += euclidean(nodes[current], nodes[node])
            current = node
        total += euclidean(nodes[current], nodes[0])
    return total


def split_by_capacity(instance, individual: list[int]) -> list[list[int]]:
    routes: list[list[int]] = []
    current: list[int] = []
    load = 0.0
    for customer_idx in individual:
        demand = instance.customers[customer_idx - 1].demand
        if current and load + demand > instance.capacity:
            routes.append(current)
            current = []
            load = 0.0
        current.append(customer_idx)
        load += demand
    if current:
        routes.append(current)
    return routes


def evaluate_ga_individual(instance, individual: list[int]) -> float:
    return route_distance(instance, split_by_capacity(instance, individual))


def order_crossover(parent_a: list[int], parent_b: list[int], rng: random.Random) -> list[int]:
    size = len(parent_a)
    left, right = sorted(rng.sample(range(size), 2))
    child = [None] * size
    child[left : right + 1] = parent_a[left : right + 1]
    used = set(child[left : right + 1])
    fill = [gene for gene in parent_b if gene not in used]
    fill_idx = 0
    for idx in list(range(0, left)) + list(range(right + 1, size)):
        child[idx] = fill[fill_idx]
        fill_idx += 1
    return [int(gene) for gene in child]


def mutate_reverse(individual: list[int], rng: random.Random) -> None:
    left, right = sorted(rng.sample(range(len(individual)), 2))
    individual[left : right + 1] = reversed(individual[left : right + 1])


def tournament(population: list[list[int]], scores: list[float], rng: random.Random, k: int = 3) -> list[int]:
    candidates = rng.sample(range(len(population)), k)
    best = min(candidates, key=lambda idx: scores[idx])
    return list(population[best])


def run_ga(case, pop_size: int, generations: int, seed: int) -> dict[str, object]:
    started = time.perf_counter()
    rng = random.Random(seed + case.client_count)
    base = list(range(1, case.instance.num_clients + 1))
    population = [rng.sample(base, len(base)) for _ in range(pop_size)]
    best_score = float("inf")

    for _ in range(generations):
        scores = [evaluate_ga_individual(case.instance, ind) for ind in population]
        best_score = min(best_score, min(scores))
        elite = [list(population[idx]) for idx in sorted(range(len(population)), key=lambda i: scores[i])[:4]]
        next_population = elite
        while len(next_population) < pop_size:
            parent_a = tournament(population, scores, rng)
            parent_b = tournament(population, scores, rng)
            child = order_crossover(parent_a, parent_b, rng)
            if rng.random() < 0.2:
                mutate_reverse(child, rng)
            next_population.append(child)
        population = next_population

    scores = [evaluate_ga_individual(case.instance, ind) for ind in population]
    best_score = min(best_score, min(scores))
    return make_row("GA", case.client_count, time.perf_counter() - started, best_score)


def scaled(value: float) -> int:
    return int(round(value * SCALE))


def build_pyvrp_cvrp_model(instance) -> Model:
    model = Model()
    depot = model.add_depot(x=scaled(instance.depot.x), y=scaled(instance.depot.y))
    clients = [
        model.add_client(x=scaled(customer.x), y=scaled(customer.y), delivery=int(customer.demand))
        for customer in instance.customers
    ]
    model.add_vehicle_type(
        num_available=instance.vehicles,
        capacity=int(instance.capacity),
        start_depot=depot,
        end_depot=depot,
    )
    original = [instance.depot, *instance.customers]
    locations = [depot, *clients]
    for i, frm in enumerate(locations):
        for j, to in enumerate(locations):
            if i == j:
                continue
            distance = scaled(euclidean(original[i], original[j]))
            model.add_edge(frm, to, distance=distance, duration=distance)
    return model


def run_pyvrp(case, runtime_seconds: int, seed: int) -> dict[str, object]:
    started = time.perf_counter()
    model = build_pyvrp_cvrp_model(case.instance)
    result = model.solve(MaxRuntime(runtime_seconds), seed=seed, display=False)
    runtime = time.perf_counter() - started
    objective = result.best.distance() / SCALE
    return make_row("PyVRP", case.client_count, runtime, objective)


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
        [[[(customer.x - min_x) / span, (customer.y - min_y) / span] for customer in case.instance.customers]],
        dtype=torch.float32,
    )
    node_demand = torch.tensor(
        [[customer.demand / case.instance.capacity for customer in case.instance.customers]],
        dtype=torch.float32,
    )
    return depot_xy, node_xy, node_demand


def load_pomo_model(checkpoint_path: Path, device: torch.device) -> CVRPModel:
    model = CVRPModel(**MODEL_PARAMS).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def actions_to_routes(actions: list[int]) -> list[list[int]]:
    routes: list[list[int]] = []
    current: list[int] = []
    seen: set[int] = set()
    for action in actions:
        action = int(action)
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


def run_pomo(case, model: CVRPModel, device: torch.device, augmentation: bool) -> dict[str, object]:
    started = time.perf_counter()
    depot_xy, node_xy, node_demand = normalize_case(case)
    aug_factor = 8 if augmentation else 1
    if augmentation:
        depot_xy = augment_xy_data_by_8_fold(depot_xy)
        node_xy = augment_xy_data_by_8_fold(node_xy)
        node_demand = node_demand.repeat(8, 1)
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
    objective = route_distance(case.instance, actions_to_routes(actions))
    runtime = time.perf_counter() - started
    return make_row("yd-kwon/POMO", case.client_count, runtime, objective)


def make_row(algorithm: str, clients: int, runtime: float, objective: float) -> dict[str, object]:
    return {
        "algorithm": algorithm,
        "clients": clients,
        "runtime_seconds": round(runtime, 3),
        "objective_value": round(objective, 3),
    }


def write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    headers = ["algorithm", "clients", "runtime_seconds", "objective_value"]
    with path.open("w", encoding="utf-8") as file:
        file.write("# CVRP Method Comparison\n\n")
        file.write("| " + " | ".join(headers) + " |\n")
        file.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for row in rows:
            file.write("| " + " | ".join(str(row[header]) for header in headers) + " |\n")


def main() -> None:
    args = parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")
    if not args.checkpoint.exists():
        raise FileNotFoundError(args.checkpoint)

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    cases = build_cases(args.solomon, args.holmberger, args.seed)

    rows: list[dict[str, object]] = []
    for case in cases:
        rows.append(run_ga(case, args.ga_pop_size, args.ga_generations, args.seed))
        rows.append(run_pyvrp(case, args.pyvrp_runtime_seconds, args.seed))

    device = torch.device(args.device)
    torch.set_default_device(device)
    pomo_model = load_pomo_model(args.checkpoint, device)
    for case in cases:
        rows.append(run_pomo(case, pomo_model, device, not args.no_pomo_augmentation))

    rows.sort(key=lambda row: (int(row["clients"]), str(row["algorithm"])))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "cvrp_method_comparison.csv"
    md_path = args.output_dir / "cvrp_method_comparison.md"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["algorithm", "clients", "runtime_seconds", "objective_value"])
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(rows, md_path)

    print("cvrp_method_comparison_ok: True")
    print(f"csv: {csv_path}")
    print(f"markdown: {md_path}")
    for row in rows:
        print(
            f"{row['algorithm']} clients={row['clients']} "
            f"runtime={row['runtime_seconds']} objective={row['objective_value']}"
        )


if __name__ == "__main__":
    main()
