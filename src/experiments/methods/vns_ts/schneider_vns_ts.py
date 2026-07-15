"""Schneider, Stenger, and Goeke (2014) style VNS/TS for E-VRPTW.

The implementation follows Part 4 of the paper:

* charging-station visits are vertices of the searched solution;
* infeasible solutions are retained and ranked by a dynamic generalized cost;
* cyclic exchange is used for VNS shaking;
* 2-opt*, relocate, exchange, and stationInRe form the TS neighborhood;
* deleted arcs are tabu and a feasible global-best move satisfies aspiration;
* simulated annealing accepts some deteriorating VNS outcomes; and
* vehicle-count feasibility and distance improvement are separate phases.

It deliberately does not call the repository's charging repair layer. Route
profiles are cached, so moves that revisit a route sequence avoid replaying it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, ceil, exp, hypot, log, sqrt
import random
import time
from typing import Iterable


EPS = 1e-9
DEPOT_ANCHOR = "@depot"


@dataclass(frozen=True)
class PenaltyWeights:
    capacity: float
    time_window: float
    battery: float


@dataclass
class PenaltyManager:
    """Dynamically adapts alpha, beta, and gamma as described in Section 4.2."""

    weights: PenaltyWeights
    lower: float = 0.01
    upper: float = 10_000.0
    factor: float = 1.2
    interval: int = 5
    _violating: dict[str, int] = field(
        default_factory=lambda: {"capacity": 0, "time_window": 0, "battery": 0}
    )
    _satisfied: dict[str, int] = field(
        default_factory=lambda: {"capacity": 0, "time_window": 0, "battery": 0}
    )

    def update(self, evaluation: "SolutionEvaluation") -> None:
        values = {
            "capacity": evaluation.capacity_violation,
            "time_window": evaluation.time_window_violation,
            "battery": evaluation.battery_violation,
        }
        current = {
            "capacity": self.weights.capacity,
            "time_window": self.weights.time_window,
            "battery": self.weights.battery,
        }
        for name, violation in values.items():
            if violation > EPS:
                self._violating[name] += 1
                self._satisfied[name] = 0
                if self._violating[name] >= self.interval:
                    current[name] = min(self.upper, current[name] * self.factor)
                    self._violating[name] = 0
            else:
                self._satisfied[name] += 1
                self._violating[name] = 0
                if self._satisfied[name] >= self.interval:
                    current[name] = max(self.lower, current[name] / self.factor)
                    self._satisfied[name] = 0
        self.weights = PenaltyWeights(**current)


@dataclass(frozen=True)
class RouteEvaluation:
    distance: float
    capacity_violation: float
    time_window_violation: float
    battery_violation: float
    charging_count: int
    charging_time: float


@dataclass(frozen=True)
class SolutionEvaluation:
    routes: tuple[tuple[str, ...], ...]
    route_evaluations: tuple[RouteEvaluation, ...]
    distance: float
    capacity_violation: float
    time_window_violation: float
    battery_violation: float
    charging_count: int
    charging_time: float
    missing_customers: int = 0
    duplicate_customers: int = 0

    @property
    def vehicle_count(self) -> int:
        return sum(bool(route) for route in self.routes)

    @property
    def feasible(self) -> bool:
        return (
            self.capacity_violation <= EPS
            and self.time_window_violation <= EPS
            and self.battery_violation <= EPS
            and self.missing_customers == 0
            and self.duplicate_customers == 0
        )

    def generalized_cost(self, weights: PenaltyWeights) -> float:
        coverage = 1_000_000.0 * (self.missing_customers + self.duplicate_customers)
        return (
            self.distance
            + weights.capacity * self.capacity_violation
            + weights.time_window * self.time_window_violation
            + weights.battery * self.battery_violation
            + coverage
        )

    def objective_rank(self, weights: PenaltyWeights) -> tuple[float, ...]:
        return (self.vehicle_count, self.generalized_cost(weights))

    def feasible_rank(self) -> tuple[float, ...]:
        return (self.vehicle_count, self.distance, self.charging_count, self.charging_time)


class SolutionEvaluator:
    """Evaluates full-recharge routes and caches immutable route profiles."""

    def __init__(self, instance):
        self.instance = instance
        self.depot = instance.depot
        self.customers = {customer.name: customer for customer in instance.clients}
        self.stations = {
            station.name: station for station in instance.charging_stations
        }
        self.locations = {self.depot.name: self.depot, **self.customers, **self.stations}
        self.customer_names = set(self.customers)
        self.station_names = set(self.stations)
        self._route_cache: dict[tuple[str, ...], RouteEvaluation] = {}

    def route(self, route: tuple[str, ...]) -> RouteEvaluation:
        cached = self._route_cache.get(route)
        if cached is not None:
            return cached

        load = sum(
            self.customers[name].demand for name in route if name in self.customers
        )
        capacity_violation = max(0.0, load - self.instance.vehicle_capacity)
        distance = 0.0
        time_window_violation = 0.0
        battery_violation = 0.0
        charging_count = 0
        charging_time = 0.0
        current = self.depot
        current_time = float(self.depot.tw_early)
        battery_capacity = self.instance.vehicle.battery_capacity
        battery = self.instance.vehicle.initial_battery
        if battery is None:
            battery = battery_capacity
        energy_rate = self.instance.energy.consumption_per_distance
        minimum_battery = self.instance.energy.minimum_battery or 0.0

        for name in (*route, self.depot.name):
            location = self.locations[name]
            leg_distance = self.instance.distance(current, location)
            distance += leg_distance
            arrival = current_time + self.instance.travel_duration(current, location)
            if battery is not None and energy_rate is not None:
                battery -= leg_distance * energy_rate

            start = max(arrival, location.tw_early)
            if start > location.tw_late:
                time_window_violation += start - location.tw_late
                # The paper's time-travel evaluation prevents one late visit
                # from propagating the same violation through the whole route.
                start = float(location.tw_late)

            if name in self.customers:
                current_time = start + location.service_duration
            elif name in self.stations:
                if battery is not None and battery_capacity is not None:
                    battery_violation += max(0.0, minimum_battery - battery)
                    charging_rate = location.charging_rate
                    if charging_rate is None:
                        charging_rate = self.instance.charging.charging_rate
                    if charging_rate is None or charging_rate <= 0:
                        battery_violation += max(1.0, battery_capacity - battery)
                        charge_duration = 0.0
                    else:
                        # Schneider et al. assume complete recharge at a station.
                        charge_duration = ceil(max(0.0, battery_capacity - battery) / charging_rate)
                    battery = float(battery_capacity)
                    charging_count += 1
                    charging_time += charge_duration
                else:
                    charge_duration = 0.0
                current_time = start + location.service_duration + charge_duration
            else:  # return to depot
                if battery is not None:
                    battery_violation += max(0.0, minimum_battery - battery)
                current_time = start
            current = location

        result = RouteEvaluation(
            distance=distance,
            capacity_violation=capacity_violation,
            time_window_violation=time_window_violation,
            battery_violation=battery_violation,
            charging_count=charging_count,
            charging_time=charging_time,
        )
        self._route_cache[route] = result
        return result

    def solution(self, routes: Iterable[Iterable[str]]) -> SolutionEvaluation:
        immutable = tuple(tuple(route) for route in routes)
        profiles = tuple(self.route(route) for route in immutable)
        counts = {name: 0 for name in self.customer_names}
        for route in immutable:
            for name in route:
                if name in counts:
                    counts[name] += 1
        return SolutionEvaluation(
            routes=immutable,
            route_evaluations=profiles,
            distance=sum(profile.distance for profile in profiles),
            capacity_violation=sum(profile.capacity_violation for profile in profiles),
            time_window_violation=sum(
                profile.time_window_violation for profile in profiles
            ),
            battery_violation=sum(profile.battery_violation for profile in profiles),
            charging_count=sum(profile.charging_count for profile in profiles),
            charging_time=sum(profile.charging_time for profile in profiles),
            missing_customers=sum(count == 0 for count in counts.values()),
            duplicate_customers=sum(count > 1 for count in counts.values()),
        )


@dataclass(frozen=True)
class ArcAttribute:
    arc: tuple[str, str]
    route_index: int
    left_anchor: str
    right_anchor: str


@dataclass(frozen=True)
class MoveCandidate:
    kind: str
    evaluation: SolutionEvaluation
    deleted_attributes: tuple[ArcAttribute, ...]
    added_attributes: tuple[ArcAttribute, ...]


class CandidatePool:
    """Reservoir samples a bounded set without bias toward early operators."""

    def __init__(self, maximum: int, rng: random.Random):
        self.maximum = max(1, maximum)
        self.rng = rng
        self.items: list[MoveCandidate] = []
        self.seen = 0

    def add(self, item: MoveCandidate) -> None:
        self.seen += 1
        if len(self.items) < self.maximum:
            self.items.append(item)
            return
        index = self.rng.randrange(self.seen)
        if index < self.maximum:
            self.items[index] = item


@dataclass(frozen=True)
class SearchConfig:
    seed: int = 1
    max_vehicles: int = 100
    initial_vehicles: int | None = None
    feasibility_iterations: int = 80
    distance_iterations: int = 80
    tabu_iterations: int = 20
    max_candidate_moves: int = 250
    candidate_list_size: int = 12
    station_candidates_per_arc: int = 3
    tabu_tenure_min: int = 5
    tabu_tenure_max: int = 15
    penalty_initial: float = 1.0
    penalty_min: float = 0.01
    penalty_max: float = 10_000.0
    penalty_factor: float = 1.2
    penalty_update_interval: int = 5
    diversification_lambda: float = 0.01
    sa_worsening_fraction: float = 0.04
    time_limit_seconds: float | None = None
    progress_interval: int = 1


@dataclass
class SearchResult:
    best: SolutionEvaluation
    history: list[dict]
    outer_iterations: int
    tabu_steps: int
    evaluated_moves: int
    final_weights: PenaltyWeights
    stopped_by_time_limit: bool
    removed_arc_count: int


class SchneiderVNSTS:
    def __init__(self, instance, config: SearchConfig):
        self.instance = instance
        self.config = config
        self.rng = random.Random(config.seed)
        self.evaluator = SolutionEvaluator(instance)
        self.forbidden_arcs = self._preprocess_infeasible_arcs()
        self.penalties = PenaltyManager(
            weights=PenaltyWeights(
                config.penalty_initial,
                config.penalty_initial,
                config.penalty_initial,
            ),
            lower=config.penalty_min,
            upper=config.penalty_max,
            factor=config.penalty_factor,
            interval=config.penalty_update_interval,
        )
        self.frequency: dict[tuple[str, int, str, str], int] = {}
        self.accepted_moves = 0
        self.nearest = self._build_candidate_lists(config.candidate_list_size)
        self.started = 0.0
        self.outer_iterations = 0
        self.tabu_steps = 0
        self.evaluated_moves = 0
        self.history: list[dict] = []
        self.best_feasible: SolutionEvaluation | None = None
        self.best_any: SolutionEvaluation | None = None

    def run(self) -> SearchResult:
        self.started = time.perf_counter()
        maximum = min(
            max(1, self.config.max_vehicles),
            max(1, len(self.instance.clients)),
        )
        lower_bound = max(
            1,
            ceil(
                sum(customer.demand for customer in self.instance.clients)
                / max(1, self.instance.vehicle_capacity)
            ),
        )
        vehicle_count = self.config.initial_vehicles or lower_bound
        vehicle_count = min(maximum, max(1, vehicle_count))
        current = self.evaluator.solution(self.initial_solution(vehicle_count))
        self._consider_best(current)
        self._record("initial", current, phase="feasibility", k=1)

        k = 1
        feasibility_counter = 0
        stopped_by_time = False
        while self.best_feasible is None:
            if self._time_exceeded():
                stopped_by_time = True
                break
            if feasibility_counter >= self.config.feasibility_iterations:
                if len(current.routes) >= maximum:
                    break
                current = self.evaluator.solution(self._add_vehicle(current.routes))
                feasibility_counter = 0
                k = 1
                self._record("add_vehicle", current, phase="feasibility", k=k)

            candidate = self._vns_iteration(current, k, phase="feasibility")
            accepted = self._accept_sa(current, candidate, feasibility_counter, self.config.feasibility_iterations)
            if accepted:
                current = candidate
                k = 1
            else:
                k = k % 15 + 1
            feasibility_counter += 1
            self.outer_iterations += 1
            self._consider_best(candidate)
            self._record(
                "accepted" if accepted else "rejected",
                current,
                phase="feasibility",
                k=k,
            )

        if self.best_feasible is not None and not stopped_by_time:
            current = self.best_feasible
            k = 1
            for iteration in range(self.config.distance_iterations):
                if self._time_exceeded():
                    stopped_by_time = True
                    break
                candidate = self._vns_iteration(current, k, phase="distance")
                accepted = self._accept_sa(
                    current,
                    candidate,
                    iteration,
                    self.config.distance_iterations,
                )
                if accepted:
                    current = candidate
                    k = 1
                else:
                    k = k % 15 + 1
                self.outer_iterations += 1
                self._consider_best(candidate)
                self._record(
                    "accepted" if accepted else "rejected",
                    current,
                    phase="distance",
                    k=k,
                )

        best = self.best_feasible or self.best_any or current
        return SearchResult(
            best=best,
            history=self.history,
            outer_iterations=self.outer_iterations,
            tabu_steps=self.tabu_steps,
            evaluated_moves=self.evaluated_moves,
            final_weights=self.penalties.weights,
            stopped_by_time_limit=stopped_by_time,
            removed_arc_count=len(self.forbidden_arcs),
        )

    def initial_solution(self, vehicle_count: int) -> list[list[str]]:
        """Section 4.1 angular order and active-route insertion construction."""

        depot = self.instance.depot
        reference_angle = self.rng.random() * 2.0 * 3.141592653589793
        customers = sorted(
            self.instance.clients,
            key=lambda customer: (
                (atan2(customer.y - depot.y, customer.x - depot.x) - reference_angle)
                % (2.0 * 3.141592653589793),
                customer.name,
            ),
        )
        routes: list[list[str]] = [[]]
        active = 0
        for customer in customers:
            route = routes[active]
            if not route:
                route.append(customer.name)
                continue
            feasible_positions = []
            for position in range(len(route) + 1):
                previous_early = (
                    depot.tw_early
                    if position == 0
                    else self.evaluator.locations[route[position - 1]].tw_early
                )
                next_early = (
                    depot.tw_late
                    if position == len(route)
                    else self.evaluator.locations[route[position]].tw_early
                )
                if previous_early <= customer.tw_early <= next_early:
                    proposed = (*route[:position], customer.name, *route[position:])
                    profile = self.evaluator.route(tuple(proposed))
                    # The paper ignores recharging when testing initial battery
                    # capacity and guarantees capacity/battery except last route.
                    if (
                        profile.capacity_violation <= EPS
                        and profile.battery_violation <= EPS
                    ):
                        feasible_positions.append(
                            (self._insertion_delta(route, position, customer.name), position)
                        )

            if feasible_positions:
                _, position = min(feasible_positions)
                route.insert(position, customer.name)
                continue

            if len(routes) < vehicle_count:
                routes.append([customer.name])
                active += 1
                continue

            position = min(
                range(len(route) + 1),
                key=lambda pos: self._insertion_delta(route, pos, customer.name),
            )
            route.insert(position, customer.name)

        while len(routes) < vehicle_count:
            split_index = max(range(len(routes)), key=lambda index: len(routes[index]))
            route = routes[split_index]
            if len(route) < 2:
                break
            midpoint = len(route) // 2
            routes[split_index] = route[:midpoint]
            routes.append(route[midpoint:])
        return routes

    def cyclic_exchange(self, evaluation: SolutionEvaluation, k: int) -> SolutionEvaluation:
        route_count = 2 + (max(1, min(15, k)) - 1) // 5
        max_chain = 1 + (max(1, min(15, k)) - 1) % 5
        routes = [list(route) for route in evaluation.routes]
        if len(routes) < route_count:
            route_count = len(routes)
        if route_count < 2:
            return evaluation
        indices = self.rng.sample(range(len(routes)), route_count)
        chains: list[list[str]] = []
        starts: list[int] = []
        for route_index in indices:
            route = routes[route_index]
            length = self.rng.randint(0, min(max_chain, len(route)))
            start = self.rng.randint(0, len(route) - length) if length else 0
            starts.append(start)
            chains.append(route[start : start + length])
        if not any(chains):
            nonempty = [i for i, route_index in enumerate(indices) if routes[route_index]]
            if not nonempty:
                return evaluation
            chosen = self.rng.choice(nonempty)
            route = routes[indices[chosen]]
            starts[chosen] = self.rng.randrange(len(route))
            chains[chosen] = [route[starts[chosen]]]
        for index, route_index in enumerate(indices):
            start = starts[index]
            del routes[route_index][start : start + len(chains[index])]
        for index, route_index in enumerate(indices):
            incoming = chains[index - 1]
            position = min(starts[index], len(routes[route_index]))
            routes[route_index][position:position] = incoming
        if not self._all_routes_serve_customers(routes):
            return evaluation
        return self.evaluator.solution(routes)

    def _vns_iteration(
        self, current: SolutionEvaluation, k: int, phase: str
    ) -> SolutionEvaluation:
        shaken = self.cyclic_exchange(current, k)
        seed_deleted, _ = changed_arc_attributes(
            current.routes,
            shaken.routes,
            self.evaluator.station_names,
            self.instance.depot.name,
        )
        return self.tabu_search(shaken, seed_deleted, phase)

    def tabu_search(
        self,
        start: SolutionEvaluation,
        perturbation_deleted: tuple[ArcAttribute, ...] = (),
        phase: str = "feasibility",
    ) -> SolutionEvaluation:
        """Section 4.4 best non-tabu composite-neighborhood descent."""

        current = start
        local_best = start
        tabu: dict[ArcAttribute, int] = {}
        tenure = self.rng.randint(
            self.config.tabu_tenure_min, self.config.tabu_tenure_max
        )
        for attribute in perturbation_deleted:
            tabu[attribute] = tenure

        for step in range(1, self.config.tabu_iterations + 1):
            if self._time_exceeded():
                break
            moves = self.generate_moves(current)
            self.evaluated_moves += len(moves)
            best_move = None
            best_rank = None
            current_cost = current.generalized_cost(self.penalties.weights)
            for move in moves:
                candidate = move.evaluation
                aspiration = (
                    candidate.feasible
                    and (
                        self.best_feasible is None
                        or candidate.feasible_rank() < self.best_feasible.feasible_rank()
                    )
                )
                is_tabu = any(tabu.get(attribute, 0) >= step for attribute in move.added_attributes)
                if is_tabu and not aspiration:
                    continue
                generalized = candidate.generalized_cost(self.penalties.weights)
                diversification = 0.0
                if generalized >= current_cost - EPS:
                    diversification = self._diversification_penalty(candidate)
                rank = (candidate.vehicle_count, generalized + diversification)
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best_move = move

            if best_move is None:
                break
            current = best_move.evaluation
            tenure = self.rng.randint(
                self.config.tabu_tenure_min, self.config.tabu_tenure_max
            )
            for attribute in best_move.deleted_attributes:
                tabu[attribute] = step + tenure
            self._increment_frequencies(current)
            self.penalties.update(current)
            self.tabu_steps += 1
            self._consider_best(current)
            if self._better(current, local_best):
                local_best = current

        return local_best

    def generate_moves(self, current: SolutionEvaluation) -> list[MoveCandidate]:
        pool = CandidatePool(self.config.max_candidate_moves, self.rng)
        routes = current.routes
        depot = self.instance.depot.name

        # Relocate customers or stations, intra- and interroute.
        for source_route, route in enumerate(routes):
            for source_pos, vertex in enumerate(route):
                near = self.nearest.get(vertex, set())
                for destination_route, destination in enumerate(routes):
                    for destination_pos in range(len(destination) + 1):
                        if source_route == destination_route and destination_pos in (
                            source_pos,
                            source_pos + 1,
                        ):
                            continue
                        previous = depot if destination_pos == 0 else destination[destination_pos - 1]
                        following = depot if destination_pos == len(destination) else destination[destination_pos]
                        if near and previous not in near and following not in near:
                            continue
                        updated = [list(item) for item in routes]
                        moved = updated[source_route].pop(source_pos)
                        adjusted = destination_pos
                        if source_route == destination_route and destination_pos > source_pos:
                            adjusted -= 1
                        updated[destination_route].insert(adjusted, moved)
                        self._offer_move(pool, "relocate", current, updated)

        # Exchange applies to customers only.
        positions = [
            (route_index, position, vertex)
            for route_index, route in enumerate(routes)
            for position, vertex in enumerate(route)
            if vertex in self.evaluator.customer_names
        ]
        for left_index, (lr, lp, left) in enumerate(positions):
            near = self.nearest.get(left, set())
            for rr, rp, right in positions[left_index + 1 :]:
                if near and right not in near:
                    continue
                updated = [list(item) for item in routes]
                updated[lr][lp], updated[rr][rp] = updated[rr][rp], updated[lr][lp]
                self._offer_move(pool, "exchange", current, updated)

        # 2-opt* exchanges route tails without reversing their direction.
        for left_route in range(len(routes)):
            for right_route in range(left_route + 1, len(routes)):
                left = routes[left_route]
                right = routes[right_route]
                for left_cut in range(len(left) + 1):
                    left_boundary = depot if left_cut == len(left) else left[left_cut]
                    near = self.nearest.get(left_boundary, set())
                    for right_cut in range(len(right) + 1):
                        right_boundary = depot if right_cut == len(right) else right[right_cut]
                        if near and right_boundary not in near:
                            continue
                        if left_cut == len(left) and right_cut == len(right):
                            continue
                        updated = [list(item) for item in routes]
                        updated[left_route] = [*left[:left_cut], *right[right_cut:]]
                        updated[right_route] = [*right[:right_cut], *left[left_cut:]]
                        self._offer_move(pool, "2-opt*", current, updated)

        # stationInRe removal and insertion on every route arc.
        for route_index, route in enumerate(routes):
            for position, vertex in enumerate(route):
                if vertex in self.evaluator.station_names:
                    updated = [list(item) for item in routes]
                    updated[route_index].pop(position)
                    self._offer_move(pool, "stationInRe-remove", current, updated)

            for position in range(len(route) + 1):
                previous = self.instance.depot if position == 0 else self.evaluator.locations[route[position - 1]]
                following = self.instance.depot if position == len(route) else self.evaluator.locations[route[position]]
                stations = sorted(
                    self.instance.charging_stations,
                    key=lambda station: (
                        self.instance.distance(previous, station)
                        + self.instance.distance(station, following)
                        - self.instance.distance(previous, following),
                        station.name,
                    ),
                )[: self.config.station_candidates_per_arc]
                for station in stations:
                    if position > 0 and route[position - 1] == station.name:
                        continue
                    if position < len(route) and route[position] == station.name:
                        continue
                    updated = [list(item) for item in routes]
                    updated[route_index].insert(position, station.name)
                    self._offer_move(pool, "stationInRe-insert", current, updated)

        return pool.items

    def _offer_move(
        self,
        pool: CandidatePool,
        kind: str,
        current: SolutionEvaluation,
        routes: list[list[str]],
    ) -> None:
        if not self._all_routes_serve_customers(routes):
            return
        candidate = self.evaluator.solution(routes)
        if candidate.routes == current.routes:
            return
        if self._forbidden_arc_count(candidate.routes) > self._forbidden_arc_count(
            current.routes
        ):
            return
        deleted, added = changed_arc_attributes(
            current.routes,
            candidate.routes,
            self.evaluator.station_names,
            self.instance.depot.name,
        )
        pool.add(MoveCandidate(kind, candidate, deleted, added))

    def _accept_sa(
        self,
        current: SolutionEvaluation,
        candidate: SolutionEvaluation,
        iteration: int,
        limit: int,
    ) -> bool:
        current_rank = current.objective_rank(self.penalties.weights)
        candidate_rank = candidate.objective_rank(self.penalties.weights)
        if candidate_rank < current_rank:
            return True
        if candidate.vehicle_count > current.vehicle_count:
            return False
        delta = candidate.generalized_cost(self.penalties.weights) - current.generalized_cost(
            self.penalties.weights
        )
        if delta <= EPS:
            return True
        baseline = max(1.0, current.distance)
        initial_temperature = (
            self.config.sa_worsening_fraction * baseline / log(2.0)
        )
        progress = min(1.0, iteration / max(1, int(0.8 * max(1, limit))))
        temperature = max(0.0001, initial_temperature * (1.0 - progress))
        return self.rng.random() < exp(-delta / temperature)

    def _better(self, left: SolutionEvaluation, right: SolutionEvaluation) -> bool:
        if left.feasible and right.feasible:
            return left.feasible_rank() < right.feasible_rank()
        if left.feasible != right.feasible:
            return left.feasible
        return left.objective_rank(self.penalties.weights) < right.objective_rank(
            self.penalties.weights
        )

    def _consider_best(self, candidate: SolutionEvaluation) -> None:
        if self.best_any is None or self._best_any_rank(candidate) < self._best_any_rank(
            self.best_any
        ):
            self.best_any = candidate
        if candidate.feasible and (
            self.best_feasible is None
            or candidate.feasible_rank() < self.best_feasible.feasible_rank()
        ):
            self.best_feasible = candidate

    def _best_any_rank(self, evaluation: SolutionEvaluation) -> tuple[float, ...]:
        if evaluation.feasible:
            return (0, *evaluation.feasible_rank())
        return (
            1,
            evaluation.generalized_cost(self.penalties.weights),
            evaluation.vehicle_count,
        )

    def _all_routes_serve_customers(self, routes: Iterable[Iterable[str]]) -> bool:
        return all(
            any(vertex in self.evaluator.customer_names for vertex in route)
            for route in routes
        )

    def _add_vehicle(
        self, routes: tuple[tuple[str, ...], ...]
    ) -> tuple[tuple[str, ...], ...]:
        """Implements addVehicle by splitting the largest active customer route."""

        customer_routes = [
            [vertex for vertex in route if vertex in self.evaluator.customer_names]
            for route in routes
        ]
        split_index = max(
            range(len(customer_routes)),
            key=lambda index: (len(customer_routes[index]), index),
        )
        route = customer_routes[split_index]
        if len(route) < 2:
            return routes
        midpoint = len(route) // 2
        updated = [tuple(item) for item in routes]
        updated[split_index] = tuple(route[:midpoint])
        updated.append(tuple(route[midpoint:]))
        return tuple(updated)

    def _build_candidate_lists(self, size: int) -> dict[str, set[str]]:
        locations = [self.instance.depot, *self.instance.clients, *self.instance.charging_stations]
        result = {}
        for location in locations:
            nearest = sorted(
                (
                    other
                    for other in locations
                    if other.name != location.name
                    and (location.name, other.name) not in self.forbidden_arcs
                ),
                key=lambda other: (
                    self.instance.distance(location, other),
                    other.name,
                ),
            )[: max(1, size)]
            result[location.name] = {other.name for other in nearest}
        return result

    def _preprocess_infeasible_arcs(self) -> set[tuple[str, str]]:
        """Applies the sufficient infeasibility tests in Equations (13)-(16)."""

        depot = self.instance.depot
        customers = list(self.instance.clients)
        customer_by_name = {customer.name: customer for customer in customers}
        route_vertices = [depot, *customers]
        all_vertices = [depot, *customers, *self.instance.charging_stations]
        forbidden: set[tuple[str, str]] = set()

        for left in route_vertices:
            for right in route_vertices:
                if left.name == right.name:
                    continue
                left_customer = customer_by_name.get(left.name)
                right_customer = customer_by_name.get(right.name)
                if (
                    left_customer is not None
                    and right_customer is not None
                    and left_customer.demand + right_customer.demand
                    > self.instance.vehicle_capacity
                ):
                    forbidden.add((left.name, right.name))
                    continue
                left_service = getattr(left, "service_duration", 0)
                right_service = getattr(right, "service_duration", 0)
                earliest_right = (
                    left.tw_early
                    + left_service
                    + self.instance.travel_duration(left, right)
                )
                if earliest_right > right.tw_late:
                    forbidden.add((left.name, right.name))
                    continue
                earliest_return = (
                    earliest_right
                    + right_service
                    + self.instance.travel_duration(right, depot)
                )
                if earliest_return > depot.tw_late:
                    forbidden.add((left.name, right.name))

        battery_capacity = self.instance.vehicle.battery_capacity
        energy_rate = self.instance.energy.consumption_per_distance
        minimum = self.instance.energy.minimum_battery or 0.0
        anchors = [depot, *self.instance.charging_stations]
        if battery_capacity is not None and energy_rate is not None:
            usable = battery_capacity - minimum
            for left in customers:
                for right in customers:
                    if left.name == right.name:
                        continue
                    inbound = min(
                        self.instance.distance(anchor, left) for anchor in anchors
                    )
                    outbound = min(
                        self.instance.distance(right, anchor) for anchor in anchors
                    )
                    required = energy_rate * (
                        inbound + self.instance.distance(left, right) + outbound
                    )
                    if required > usable + EPS:
                        forbidden.add((left.name, right.name))

        # Self loops are never useful. Station arcs are retained because their
        # recharge-time feasibility depends on the arrival charge and prefix.
        forbidden.update((vertex.name, vertex.name) for vertex in all_vertices)
        return forbidden

    def _forbidden_arc_count(
        self, routes: Iterable[Iterable[str]]
    ) -> int:
        depot = self.instance.depot.name
        return sum(
            (left, right) in self.forbidden_arcs
            for route in routes
            for left, right in route_arcs(tuple(route), depot)
        )

    def _insertion_delta(self, route: list[str], position: int, name: str) -> float:
        previous = self.instance.depot if position == 0 else self.evaluator.locations[route[position - 1]]
        following = self.instance.depot if position == len(route) else self.evaluator.locations[route[position]]
        vertex = self.evaluator.locations[name]
        return (
            self.instance.distance(previous, vertex)
            + self.instance.distance(vertex, following)
            - self.instance.distance(previous, following)
        )

    def _solution_attributes(
        self, evaluation: SolutionEvaluation
    ) -> list[tuple[str, int, str, str]]:
        attributes = []
        for route_index, route in enumerate(evaluation.routes):
            anchors = surrounding_anchors(
                route, self.evaluator.station_names, self.instance.depot.name
            )
            for position, vertex in enumerate(route):
                attributes.append((vertex, route_index, *anchors[position]))
        return attributes

    def _increment_frequencies(self, evaluation: SolutionEvaluation) -> None:
        for attribute in self._solution_attributes(evaluation):
            self.frequency[attribute] = self.frequency.get(attribute, 0) + 1
        self.accepted_moves += 1

    def _diversification_penalty(self, evaluation: SolutionEvaluation) -> float:
        if not self.frequency or self.config.diversification_lambda <= 0:
            return 0.0
        frequency_sum = sum(
            self.frequency.get(attribute, 0)
            for attribute in self._solution_attributes(evaluation)
        ) / max(1, self.accepted_moves)
        vertex_count = sum(len(route) for route in evaluation.routes)
        scale = evaluation.distance * sqrt(
            max(1, vertex_count) * max(1, evaluation.vehicle_count)
        )
        return self.config.diversification_lambda * scale * frequency_sum

    def _record(self, event: str, evaluation: SolutionEvaluation, *, phase: str, k: int) -> None:
        self.history.append(
            {
                "iteration": self.outer_iterations,
                "phase": phase,
                "event": event,
                "neighborhood_k": k,
                "feasible": evaluation.feasible,
                "vehicle_count": evaluation.vehicle_count,
                "total_distance": round(evaluation.distance, 3),
                "capacity_violation": round(evaluation.capacity_violation, 3),
                "time_window_violation": round(evaluation.time_window_violation, 3),
                "battery_violation": round(evaluation.battery_violation, 3),
                "penalty_capacity": round(self.penalties.weights.capacity, 6),
                "penalty_time_window": round(self.penalties.weights.time_window, 6),
                "penalty_battery": round(self.penalties.weights.battery, 6),
                "tabu_steps": self.tabu_steps,
                "evaluated_moves": self.evaluated_moves,
            }
        )
        if (
            self.config.progress_interval > 0
            and event in {"initial", "add_vehicle", "accepted", "rejected"}
            and self.outer_iterations % self.config.progress_interval == 0
        ):
            print(
                "VNS/TS progress "
                f"phase={phase} iteration={self.outer_iterations} event={event} "
                f"vehicles={evaluation.vehicle_count} feasible={evaluation.feasible} "
                f"distance={evaluation.distance:.0f} "
                f"violations=({evaluation.capacity_violation:.1f},"
                f"{evaluation.time_window_violation:.1f},"
                f"{evaluation.battery_violation:.1f}) "
                f"moves={self.evaluated_moves}",
                flush=True,
            )

    def _time_exceeded(self) -> bool:
        return (
            self.config.time_limit_seconds is not None
            and time.perf_counter() - self.started >= self.config.time_limit_seconds
        )


def route_arcs(route: tuple[str, ...], depot_name: str) -> tuple[tuple[str, str], ...]:
    vertices = (depot_name, *route, depot_name)
    return tuple(zip(vertices, vertices[1:]))


def surrounding_anchors(
    route: tuple[str, ...], station_names: set[str], depot_name: str
) -> list[tuple[str, str]]:
    anchors = []
    left = depot_name
    right_by_position = [depot_name] * len(route)
    right = depot_name
    for position in range(len(route) - 1, -1, -1):
        if route[position] in station_names:
            right = route[position]
        right_by_position[position] = right
    for position, vertex in enumerate(route):
        if vertex in station_names:
            left = vertex
        anchors.append((left, right_by_position[position]))
    return anchors


def arc_attributes(
    routes: tuple[tuple[str, ...], ...], station_names: set[str], depot_name: str
) -> dict[tuple[int, tuple[str, str]], ArcAttribute]:
    result = {}
    for route_index, route in enumerate(routes):
        vertices = (depot_name, *route, depot_name)
        for arc_position, arc in enumerate(zip(vertices, vertices[1:])):
            left = depot_name
            for vertex in reversed(vertices[: arc_position + 1]):
                if vertex == depot_name or vertex in station_names:
                    left = vertex
                    break
            right = depot_name
            for vertex in vertices[arc_position + 1 :]:
                if vertex == depot_name or vertex in station_names:
                    right = vertex
                    break
            result[(route_index, arc)] = ArcAttribute(arc, route_index, left, right)
    return result


def changed_arc_attributes(
    before: tuple[tuple[str, ...], ...],
    after: tuple[tuple[str, ...], ...],
    station_names: set[str],
    depot_name: str,
) -> tuple[tuple[ArcAttribute, ...], tuple[ArcAttribute, ...]]:
    before_attributes = arc_attributes(before, station_names, depot_name)
    after_attributes = arc_attributes(after, station_names, depot_name)
    deleted_keys = before_attributes.keys() - after_attributes.keys()
    added_keys = after_attributes.keys() - before_attributes.keys()
    return (
        tuple(before_attributes[key] for key in sorted(deleted_keys)),
        tuple(after_attributes[key] for key in sorted(added_keys)),
    )
