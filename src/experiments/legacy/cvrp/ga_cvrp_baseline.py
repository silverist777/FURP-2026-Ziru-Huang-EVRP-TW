"""Run a standalone GA baseline on Solomon-like CVRP data.

This runner intentionally ignores time windows and electric-vehicle constraints.
It reads Solomon/Holmberger-style `.txt` files from `src/data` and optimises
capacity-feasible CVRP route distance with a simple permutation GA.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = REPO_ROOT / "src" / "log" / "week1" / "ga-baseline" / "ga_cvrp_baseline.csv"

sys.path.insert(0, str(REPO_ROOT / "src" / "experiments"))

from core.experiment_record import build_experiment_record, format_constraint_violations  # noqa: E402


@dataclass(frozen=True)
class Customer:
    cust_no: int
    x: float
    y: float
    demand: float
    ready_time: float
    due_time: float
    service_time: float


@dataclass(frozen=True)
class Instance:
    name: str
    path: Path
    vehicles: int
    capacity: float
    depot: Customer
    customers: list[Customer]

    @property
    def num_clients(self) -> int:
        return len(self.customers)


def parse_solomon_like(path: Path) -> Instance:
    vehicles = None
    capacity = None
    rows: list[Customer] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    for idx, raw_line in enumerate(lines):
        parts = raw_line.split()
        if len(parts) == 2 and all(part.replace(".", "", 1).isdigit() for part in parts):
            prev = lines[idx - 1].upper() if idx > 0 else ""
            if "CAPACITY" in prev:
                vehicles = int(float(parts[0]))
                capacity = float(parts[1])
                continue

        if len(parts) == 7 and parts[0].lstrip("-").isdigit():
            rows.append(
                Customer(
                    cust_no=int(parts[0]),
                    x=float(parts[1]),
                    y=float(parts[2]),
                    demand=float(parts[3]),
                    ready_time=float(parts[4]),
                    due_time=float(parts[5]),
                    service_time=float(parts[6]),
                )
            )

    if vehicles is None or capacity is None:
        raise ValueError(f"Could not parse vehicle capacity block from {path}")
    if not rows or rows[0].cust_no != 0:
        raise ValueError(f"Could not parse depot row cust_no=0 from {path}")

    return Instance(
        name=path.stem,
        path=path,
        vehicles=vehicles,
        capacity=capacity,
        depot=rows[0],
        customers=rows[1:],
    )


def select_customers(instance: Instance, client_count: int | None, seed: int) -> Instance:
    if client_count is None or client_count >= instance.num_clients:
        return instance
    if client_count <= 0:
        raise ValueError("--client-count must be positive")

    rng = random.Random(seed + client_count)
    selected = set(rng.sample([c.cust_no for c in instance.customers], client_count))
    customers = [customer for customer in instance.customers if customer.cust_no in selected]
    return Instance(
        name=f"{instance.name}_{client_count}",
        path=instance.path,
        vehicles=instance.vehicles,
        capacity=instance.capacity,
        depot=instance.depot,
        customers=customers,
    )


def euclidean(a: Customer, b: Customer) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def split_by_capacity(instance: Instance, individual: list[int]) -> list[list[int]]:
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


def route_distance(instance: Instance, routes: list[list[int]]) -> float:
    nodes = [instance.depot, *instance.customers]
    total = 0.0

    for route in routes:
        current = 0
        for customer_idx in route:
            total += euclidean(nodes[current], nodes[customer_idx])
            current = customer_idx
        total += euclidean(nodes[current], nodes[0])

    return total


def cvrp_constraint_violations(instance: Instance, routes: list[list[int]]) -> dict[str, int]:
    served = [customer_idx for route in routes for customer_idx in route]
    expected = set(range(1, instance.num_clients + 1))
    valid_served = [customer_idx for customer_idx in served if customer_idx in expected]

    capacity_violations = 0
    for route in routes:
        load = sum(
            instance.customers[customer_idx - 1].demand
            for customer_idx in route
            if customer_idx in expected
        )
        if load > instance.capacity + 1e-6:
            capacity_violations += 1

    return {
        "missing_customers": len(expected - set(valid_served)),
        "duplicate_customers": len(valid_served) - len(set(valid_served)),
        "capacity_violations": capacity_violations,
        "vehicle_limit_overage": max(0, len(routes) - instance.vehicles),
        "invalid_customer_ids": len(served) - len(valid_served),
    }


def evaluate(instance: Instance, individual: list[int]) -> float:
    return route_distance(instance, split_by_capacity(instance, individual))


def order_crossover(parent_a: list[int], parent_b: list[int], rng: random.Random) -> list[int]:
    size = len(parent_a)
    left, right = sorted(rng.sample(range(size), 2))
    child: list[int | None] = [None] * size
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


def tournament(
    population: list[list[int]],
    scores: list[float],
    rng: random.Random,
    tournament_size: int,
) -> list[int]:
    candidates = rng.sample(range(len(population)), tournament_size)
    best = min(candidates, key=lambda idx: scores[idx])
    return list(population[best])


def run_ga(
    instance: Instance,
    pop_size: int,
    generations: int,
    seed: int,
    mutation_prob: float,
    elite_size: int,
    tournament_size: int,
) -> tuple[float, list[list[int]], float, list[dict[str, float | int | str]]]:
    started = time.perf_counter()
    rng = random.Random(seed + instance.num_clients)
    base = list(range(1, instance.num_clients + 1))
    population = [rng.sample(base, len(base)) for _ in range(pop_size)]
    best_individual: list[int] | None = None
    best_score = float("inf")
    initial_best_score: float | None = None
    previous_best_score: float | None = None
    convergence_curve: list[dict[str, float | int | str]] = []

    for generation in range(1, generations + 1):
        scores = [evaluate(instance, individual) for individual in population]
        current_best_idx = min(range(len(population)), key=lambda idx: scores[idx])
        generation_best = scores[current_best_idx]
        if initial_best_score is None:
            initial_best_score = generation_best
        if generation_best < best_score:
            best_score = generation_best
            best_individual = list(population[current_best_idx])
        convergence_curve.append(
            progress_point(
                generation=generation,
                stage="generation",
                generation_best=generation_best,
                best_score=best_score,
                initial_best_score=initial_best_score,
                previous_best_score=previous_best_score,
            )
        )
        previous_best_score = best_score

        elite_count = min(elite_size, len(population))
        elites = [
            list(population[idx])
            for idx in sorted(range(len(population)), key=lambda idx: scores[idx])[:elite_count]
        ]
        next_population = elites
        while len(next_population) < pop_size:
            parent_a = tournament(population, scores, rng, tournament_size)
            parent_b = tournament(population, scores, rng, tournament_size)
            child = order_crossover(parent_a, parent_b, rng)
            if rng.random() < mutation_prob:
                mutate_reverse(child, rng)
            next_population.append(child)
        population = next_population

    scores = [evaluate(instance, individual) for individual in population]
    current_best_idx = min(range(len(population)), key=lambda idx: scores[idx])
    generation_best = scores[current_best_idx]
    if initial_best_score is None:
        initial_best_score = generation_best
    if generation_best < best_score or best_individual is None:
        best_score = generation_best
        best_individual = list(population[current_best_idx])
        convergence_curve.append(
            progress_point(
                generation=generations + 1,
                stage="final_population",
                generation_best=generation_best,
                best_score=best_score,
                initial_best_score=initial_best_score,
                previous_best_score=previous_best_score,
            )
        )

    runtime = time.perf_counter() - started
    routes = split_by_capacity(instance, best_individual)
    return best_score, routes, runtime, convergence_curve


def progress_point(
    generation: int,
    stage: str,
    generation_best: float,
    best_score: float,
    initial_best_score: float,
    previous_best_score: float | None,
) -> dict[str, float | int | str]:
    previous = best_score if previous_best_score is None else previous_best_score
    return {
        "generation": generation,
        "stage": stage,
        "generation_best": round(generation_best, 3),
        "best_objective": round(best_score, 3),
        "improvement_from_start": round(initial_best_score - best_score, 3),
        "improvement_from_previous": round(previous - best_score, 3),
    }


def write_csv(row: dict[str, object], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run standalone GA CVRP baseline.")
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--client-count", type=int, default=None)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--pop-size", type=int, default=80)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--mutation-prob", type=float, default=0.2)
    parser.add_argument("--elite-size", type=int, default=4)
    parser.add_argument("--tournament-size", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_instance = parse_solomon_like(args.instance)
    instance = select_customers(base_instance, args.client_count, args.seed)
    objective, routes, runtime, convergence_curve = run_ga(
        instance=instance,
        pop_size=args.pop_size,
        generations=args.generations,
        seed=args.seed,
        mutation_prob=args.mutation_prob,
        elite_size=args.elite_size,
        tournament_size=args.tournament_size,
    )
    constraint_violations = format_constraint_violations(
        cvrp_constraint_violations(instance, routes)
    )
    feasibility_status = (
        "feasible under CVRP check; TW/E disabled"
        if constraint_violations == "none"
        else "infeasible under CVRP check; TW/E disabled"
    )
    row = build_experiment_record(
        instance_name=instance.name,
        instance_size=instance.num_clients,
        method_name="GA CVRP",
        objective_value=objective,
        runtime_seconds=runtime,
        feasibility_status=feasibility_status,
        vehicles_used=len(routes),
        constraint_violations=constraint_violations,
        random_seed=args.seed,
        best_solution_found=routes,
        reference_value=None,
        convergence_curve=convergence_curve,
        improvement_over_time=convergence_curve,
        generations=args.generations,
        search_steps=args.pop_size * args.generations,
    )
    row.update({
        "method": "GA",
        "instance": instance.name,
        "source": str(args.instance),
        "clients": instance.num_clients,
        "objective_value": round(objective, 3),
        "routes_used": len(routes),
        "runtime_seconds": round(runtime, 3),
        "seed": args.seed,
        "pop_size": args.pop_size,
        "generations": args.generations,
        "mutation_prob": args.mutation_prob,
        "constraint_scope": "CVRP only; time windows disabled; EV constraints disabled",
    })
    write_csv(row, args.output_csv)

    print("ga_cvrp_baseline_ok: True")
    print(f"csv: {args.output_csv}")
    print(
        f"GA instance={instance.name} clients={instance.num_clients} "
        f"objective={row['objective_value']} routes={len(routes)} "
        f"runtime={row['runtime_seconds']}"
    )


if __name__ == "__main__":
    main()
