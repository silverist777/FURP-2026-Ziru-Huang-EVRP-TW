"""Solomon-style VRPTW parsing and feasibility checks shared by baselines.

This module intentionally has no reinforcement-learning dependencies. The
retained POMO path uses an upstream yd-kwon CVRP checkpoint and checks time
windows after rollout.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


@dataclass
class SolomonCustomer:
    cust_no: int
    x: float
    y: float
    demand: float
    ready_time: float
    due_time: float
    service_time: float


@dataclass
class SolomonInstance:
    name: str
    path: Path
    solution_path: Path | None
    vehicles: int
    capacity: float
    depot: SolomonCustomer
    customers: list[SolomonCustomer]
    known_cost: float | None

    @property
    def num_clients(self) -> int:
        return len(self.customers)


@dataclass
class VRPTWCheckResult:
    predicted_cost: float
    time_window_violations: int
    capacity_violations: int
    missing_customers: int
    duplicate_customers: int
    depot_return_violations: int
    all_customers_served: bool
    feasible: bool


def parse_solomon_solution(path: Path | None) -> float | None:
    if path is None or not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("Cost"):
            return float(line.split()[-1])
    return None


def parse_solomon_instance(path: Path) -> SolomonInstance:
    vehicles: int | None = None
    capacity: float | None = None
    rows: list[SolomonCustomer] = []
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
                SolomonCustomer(
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
        raise ValueError(f"Could not parse VEHICLE capacity block from {path}")
    if not rows or rows[0].cust_no != 0:
        raise ValueError(f"Could not parse depot row cust_no=0 from {path}")

    solution_path = path.with_suffix(".sol")
    return SolomonInstance(
        name=path.stem,
        path=path,
        solution_path=solution_path if solution_path.exists() else None,
        vehicles=vehicles,
        capacity=capacity,
        depot=rows[0],
        customers=rows[1:],
        known_cost=parse_solomon_solution(solution_path),
    )


def load_solomon_instances(data_dir: Path, limit: int | None = None) -> list[SolomonInstance]:
    instances = [parse_solomon_instance(path) for path in sorted(data_dir.glob("*.txt"))]
    return instances if limit is None else instances[:limit]


def _euclidean(a: SolomonCustomer, b: SolomonCustomer) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def check_solomon_actions(instance: SolomonInstance, actions: Iterable[int]) -> VRPTWCheckResult:
    nodes = [instance.depot, *instance.customers]
    visited: set[int] = set()
    current = instance.depot
    current_time = 0.0
    current_load = 0.0
    total_distance = 0.0
    time_window_violations = 0
    capacity_violations = 0
    duplicate_customers = 0
    depot_return_violations = 0

    for raw_action in actions:
        action = int(raw_action)
        if action < 0 or action >= len(nodes):
            time_window_violations += 1
            continue

        if action == 0:
            if current.cust_no == 0:
                if len(visited) == instance.num_clients:
                    break
                continue

            return_time = current_time + _euclidean(current, instance.depot)
            total_distance += _euclidean(current, instance.depot)
            if return_time > instance.depot.due_time + 1e-6:
                depot_return_violations += 1
            current = instance.depot
            current_time = 0.0
            current_load = 0.0
            if len(visited) == instance.num_clients:
                break
            continue

        customer = nodes[action]
        total_distance += _euclidean(current, customer)
        arrival = current_time + _euclidean(current, customer)
        start_service = max(arrival, customer.ready_time)
        if start_service > customer.due_time + 1e-6:
            time_window_violations += 1
        current_load += customer.demand
        if current_load > instance.capacity + 1e-6:
            capacity_violations += 1
        if action in visited:
            duplicate_customers += 1
        visited.add(action)
        current_time = start_service + customer.service_time
        current = customer

    if current.cust_no != 0:
        return_time = current_time + _euclidean(current, instance.depot)
        total_distance += _euclidean(current, instance.depot)
        if return_time > instance.depot.due_time + 1e-6:
            depot_return_violations += 1

    missing_customers = instance.num_clients - len(visited)
    all_customers_served = missing_customers == 0 and duplicate_customers == 0
    feasible = (
        all_customers_served
        and time_window_violations == 0
        and capacity_violations == 0
        and depot_return_violations == 0
    )
    return VRPTWCheckResult(
        predicted_cost=total_distance,
        time_window_violations=time_window_violations,
        capacity_violations=capacity_violations,
        missing_customers=missing_customers,
        duplicate_customers=duplicate_customers,
        depot_return_violations=depot_return_violations,
        all_customers_served=all_customers_served,
        feasible=feasible,
    )


def summarize_gaps(rows: list[dict[str, object]]) -> dict[str, float]:
    gaps = [float(row["gap_pct"]) for row in rows if row.get("gap_pct") not in (None, "")]
    return {
        "mean_gap_pct": mean(gaps) if gaps else float("nan"),
        "min_gap_pct": min(gaps) if gaps else float("nan"),
        "max_gap_pct": max(gaps) if gaps else float("nan"),
    }
