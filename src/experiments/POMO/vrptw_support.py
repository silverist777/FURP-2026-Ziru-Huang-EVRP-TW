"""Project-local VRPTW helpers for RL4CO POMO experiments.

This module intentionally covers capacitated VRP with time windows only. It does
not model battery, charging stations, energy consumption, or charging time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

import torch
from tensordict import TensorDict

from rl4co.envs import CVRPTWEnv
from rl4co.envs.routing.cvrp.env import CVRPEnv
from rl4co.envs.routing.cvrp.generator import CVRPGenerator
from rl4co.envs.routing.cvrptw.generator import CVRPTWGenerator
from rl4co.utils.ops import gather_by_index, get_distance


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


class SolomonLikeVRPTWGenerator(CVRPTWGenerator):
    """Small synthetic VRPTW generator with non-zero service durations."""

    def __init__(self, *args, service_duration: float = 10.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_duration = service_duration

    def _generate(self, batch_size) -> TensorDict:
        batch_size = [batch_size] if isinstance(batch_size, int) else batch_size
        td = CVRPGenerator._generate(self, batch_size)

        if self.scale:
            td["depot"] = td["depot"] / self.max_time
            td["locs"] = td["locs"] / self.max_time
            horizon = 1.0
            service_duration = self.service_duration / self.max_time
        else:
            horizon = self.max_time
            service_duration = self.service_duration

        durations = torch.zeros(*batch_size, self.num_loc + 1, dtype=torch.float32)
        durations[..., 1:] = service_duration

        locs_with_depot = torch.cat((td["depot"][..., None, :], td["locs"]), -2)
        dist_to_depot = get_distance(locs_with_depot, td["depot"][..., None, :])
        time_windows = torch.zeros(*batch_size, self.num_loc + 1, 2, dtype=torch.float32)
        time_windows[..., :, 0] = 0.0
        time_windows[..., :, 1] = torch.clamp(
            horizon - dist_to_depot - durations - 1e-4,
            min=1e-3,
            max=horizon,
        )
        time_windows[..., 0, 0] = 0.0
        time_windows[..., 0, 1] = horizon
        durations[..., 0] = 0.0
        td.update({"durations": durations, "time_windows": time_windows})
        return td


class StrictCVRPTWEnv(CVRPTWEnv):
    """CVRPTW env with a stricter time-window action mask.

    RL4CO already provides CVRPTWEnv and cvrptw embeddings. This subclass keeps
    those interfaces, but masks a customer if service at that customer would make
    the current route unable to return to the depot before the depot due time.
    """

    name = "cvrptw"

    @staticmethod
    def get_action_mask(td: TensorDict) -> torch.Tensor:
        base_mask = CVRPEnv.get_action_mask(td)
        current_loc = gather_by_index(td["locs"], td["current_node"])
        dist = get_distance(current_loc[..., None, :], td["locs"])
        arrival = td["current_time"] + dist
        ready = td["time_windows"][..., 0]
        due = td["time_windows"][..., 1]
        start_service = torch.maximum(arrival, ready)
        finish_service = start_service + td["durations"]
        depot_due = td["time_windows"][..., 0, 1][..., None]
        dist_to_depot = get_distance(td["locs"], td["locs"][..., 0:1, :])

        can_start_service = start_service <= due + 1e-6
        can_return_depot = finish_service + dist_to_depot <= depot_due + 1e-6
        time_mask = can_start_service & can_return_depot

        action_mask = base_mask & time_mask
        all_customers_visited = td["visited"][..., 1:].bool().all(-1)
        action_mask[..., 0] = (td["current_node"].squeeze(-1) != 0) | all_customers_visited
        return action_mask

    def _step(self, td: TensorDict) -> TensorDict:
        batch_size = td["locs"].shape[0]
        current_loc = gather_by_index(td["locs"], td["current_node"])
        dist = get_distance(current_loc[..., None, :], td["locs"])
        td.update({"current_loc": current_loc, "distances": dist})

        distance = gather_by_index(td["distances"], td["action"]).reshape(batch_size, 1)
        duration = gather_by_index(td["durations"], td["action"]).reshape(batch_size, 1)
        ready = gather_by_index(td["time_windows"], td["action"])[..., 0].reshape(
            batch_size, 1
        )
        next_time = torch.maximum(td["current_time"] + distance, ready) + duration
        td["current_time"] = (td["action"][:, None] != 0) * next_time
        return CVRPEnv._step(self, td)


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
                vehicles = int(parts[0])
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


def solomon_to_tensordict(instance: SolomonInstance, device: str = "cpu") -> TensorDict:
    """Convert a Solomon instance to RL4CO CVRPTW TensorDict.

    Coordinates, time windows, and service durations are all divided by the depot
    due time so Euclidean travel time remains in the same units as time windows.
    """

    horizon = max(instance.depot.due_time, 1.0)
    depot = torch.tensor(
        [[instance.depot.x / horizon, instance.depot.y / horizon]],
        dtype=torch.float32,
        device=device,
    )
    locs = torch.tensor(
        [[[customer.x / horizon, customer.y / horizon] for customer in instance.customers]],
        dtype=torch.float32,
        device=device,
    )
    demand = torch.tensor(
        [[customer.demand / instance.capacity for customer in instance.customers]],
        dtype=torch.float32,
        device=device,
    )
    durations = torch.tensor(
        [[0.0] + [customer.service_time / horizon for customer in instance.customers]],
        dtype=torch.float32,
        device=device,
    )
    time_windows = torch.tensor(
        [
            [[instance.depot.ready_time / horizon, instance.depot.due_time / horizon]]
            + [
                [customer.ready_time / horizon, customer.due_time / horizon]
                for customer in instance.customers
            ]
        ],
        dtype=torch.float32,
        device=device,
    )
    return TensorDict(
        {
            "depot": depot,
            "locs": locs,
            "demand": demand,
            "capacity": torch.tensor([[instance.capacity]], dtype=torch.float32, device=device),
            "durations": durations,
            "time_windows": time_windows,
        },
        batch_size=[1],
        device=device,
    )


def _euclidean(a: SolomonCustomer, b: SolomonCustomer) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def check_solomon_actions(instance: SolomonInstance, actions: Iterable[int]) -> VRPTWCheckResult:
    nodes = [instance.depot] + instance.customers
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



def check_tensordict_actions(td: TensorDict, actions: Iterable[int]) -> VRPTWCheckResult:
    """Check an RL4CO-format CVRPTW TensorDict action sequence."""

    locs = td["locs"][0].detach().cpu()
    demand = td["demand"][0].detach().cpu()
    durations = td["durations"][0].detach().cpu()
    time_windows = td["time_windows"][0].detach().cpu()
    vehicle_capacity = float(td["vehicle_capacity"][0, 0].detach().cpu())

    visited: set[int] = set()
    current_idx = 0
    current_time = 0.0
    current_load = 0.0
    total_distance = 0.0
    time_window_violations = 0
    capacity_violations = 0
    duplicate_customers = 0
    depot_return_violations = 0

    def dist(i: int, j: int) -> float:
        return float(torch.linalg.vector_norm(locs[i] - locs[j]).item())

    for raw_action in actions:
        action = int(raw_action)
        if action < 0 or action >= locs.shape[0]:
            time_window_violations += 1
            continue

        if action == 0:
            if current_idx == 0:
                if len(visited) == demand.numel():
                    break
                continue
            return_time = current_time + dist(current_idx, 0)
            total_distance += dist(current_idx, 0)
            if return_time > float(time_windows[0, 1]) + 1e-6:
                depot_return_violations += 1
            current_idx = 0
            current_time = 0.0
            current_load = 0.0
            if len(visited) == demand.numel():
                break
            continue

        travel = dist(current_idx, action)
        total_distance += travel
        arrival = current_time + travel
        start_service = max(arrival, float(time_windows[action, 0]))
        if start_service > float(time_windows[action, 1]) + 1e-6:
            time_window_violations += 1
        current_load += float(demand[action - 1])
        if current_load > vehicle_capacity + 1e-6:
            capacity_violations += 1
        if action in visited:
            duplicate_customers += 1
        visited.add(action)
        current_time = start_service + float(durations[action])
        current_idx = action

    if current_idx != 0:
        return_time = current_time + dist(current_idx, 0)
        total_distance += dist(current_idx, 0)
        if return_time > float(time_windows[0, 1]) + 1e-6:
            depot_return_violations += 1

    missing_customers = demand.numel() - len(visited)
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




