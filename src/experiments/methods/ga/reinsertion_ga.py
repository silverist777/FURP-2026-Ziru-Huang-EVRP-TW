"""Benchmark-adapted remove-reinsert genetic algorithm for EVRP-TW.

The search operators follow Li, Zhu, and Lee's RI-GA: randomized nearest-
neighbour initialization, route-fragment crossover, related removal with an
adaptive removal count, and minimum-increment reinsertion.  Feasibility and
cost semantics intentionally come from the project's benchmark instead of the
paper's fuzzy-time-window and nonlinear-energy model.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, inf
import random
from typing import Iterable, Sequence


EPS = 1e-9


@dataclass(frozen=True)
class DecodedIndividual:
    permutation: tuple[str, ...]
    routes: tuple[tuple[str, ...], ...]
    distance: int
    feasible: bool
    reason: str = ""


@dataclass(frozen=True)
class SearchResult:
    best: DecodedIndividual
    candidates: tuple[DecodedIndividual, ...]
    convergence: tuple[dict, ...]


class ReinsertionGA:
    """RI-GA over customer permutations with a hard-feasible split decoder."""

    def __init__(
        self,
        instance,
        *,
        population_size: int = 80,
        generations: int = 50,
        crossover_probability: float = 0.85,
        mutation_probability: float = 0.8,
        neighbour_count: int = 3,
        max_removal_fraction: float = 0.3,
        elite_count: int = 2,
        seed: int = 1,
    ):
        if population_size < 2:
            raise ValueError("population_size must be at least 2")
        if generations < 0:
            raise ValueError("generations must be non-negative")
        if neighbour_count < 1:
            raise ValueError("neighbour_count must be positive")
        if not 0 < max_removal_fraction <= 1:
            raise ValueError("max_removal_fraction must be in (0, 1]")

        self.instance = instance
        self.population_size = population_size
        self.generations = generations
        self.crossover_probability = crossover_probability
        self.mutation_probability = mutation_probability
        self.neighbour_count = neighbour_count
        self.max_removal_fraction = max_removal_fraction
        self.elite_count = min(max(1, elite_count), population_size)
        self.rng = random.Random(seed)
        self.customers = {customer.name: customer for customer in instance.clients}
        self.customer_names = tuple(self.customers)
        self.max_distance = max(
            (
                instance.distance(left, right)
                for left in instance.clients
                for right in instance.clients
                if left.name != right.name
            ),
            default=1,
        )

    def _route_metrics(self, route: Sequence[str]) -> tuple[bool, int]:
        """Checks the benchmark's customer-only capacity and hard TW resources."""

        previous = self.instance.depot
        time_value = max(
            self.instance.depot.tw_early,
            self.instance.vehicle.tw_early,
        )
        load = 0
        distance = 0
        for name in route:
            customer = self.customers[name]
            leg_distance = self.instance.distance(previous, customer)
            distance += leg_distance
            time_value += self.instance.travel_duration(previous, customer)
            time_value = max(time_value, customer.tw_early)
            if time_value > customer.tw_late + EPS:
                return False, distance
            time_value += customer.service_duration
            load += customer.demand
            if load > self.instance.vehicle_capacity + EPS:
                return False, distance
            previous = customer

        distance += self.instance.distance(previous, self.instance.depot)
        time_value += self.instance.travel_duration(previous, self.instance.depot)
        latest_return = min(
            self.instance.depot.tw_late,
            self.instance.vehicle.tw_late,
        )
        return time_value <= latest_return + EPS, distance

    def decode(self, permutation: Sequence[str]) -> DecodedIndividual:
        """Finds the minimum-distance contiguous split using at most K vehicles."""

        permutation = tuple(permutation)
        if len(permutation) != len(self.customer_names) or set(permutation) != set(
            self.customer_names
        ):
            return DecodedIndividual(
                permutation, (), 10**15, False, "invalid_customer_permutation"
            )

        size = len(permutation)
        segment_cost: dict[tuple[int, int], int] = {}
        for start in range(size):
            for end in range(start + 1, size + 1):
                feasible, distance = self._route_metrics(permutation[start:end])
                if feasible:
                    segment_cost[start, end] = distance
                elif end == start + 1:
                    break
                else:
                    # Capacity and late-time resources are monotone for a fixed
                    # prefix under the benchmark's non-negative travel/service.
                    break

        max_vehicles = self.instance.num_vehicles
        dp = [[inf] * (size + 1) for _ in range(max_vehicles + 1)]
        previous: list[list[int | None]] = [
            [None] * (size + 1) for _ in range(max_vehicles + 1)
        ]
        dp[0][0] = 0
        for vehicle_count in range(1, max_vehicles + 1):
            for end in range(1, size + 1):
                for start in range(end):
                    cost = segment_cost.get((start, end))
                    if cost is None or dp[vehicle_count - 1][start] == inf:
                        continue
                    candidate = dp[vehicle_count - 1][start] + cost
                    if candidate < dp[vehicle_count][end]:
                        dp[vehicle_count][end] = candidate
                        previous[vehicle_count][end] = start

        choices = [
            (dp[count][size], count)
            for count in range(1, max_vehicles + 1)
            if dp[count][size] < inf
        ]
        if not choices:
            return DecodedIndividual(
                permutation, (), 10**15, False, "no_hard_feasible_split"
            )

        best_distance, vehicle_count = min(choices)
        routes = []
        end = size
        while end:
            start = previous[vehicle_count][end]
            if start is None:
                raise RuntimeError("split decoder predecessor chain is incomplete")
            routes.append(permutation[start:end])
            end = start
            vehicle_count -= 1
        routes.reverse()
        return DecodedIndividual(
            permutation,
            tuple(tuple(route) for route in routes),
            int(best_distance),
            True,
        )

    def nearest_neighbour_permutation(self) -> tuple[str, ...]:
        """Paper Algorithm 1's randomized k-nearest customer traversal."""

        unvisited = set(self.customer_names)
        current = self.instance.depot
        order = []
        while unvisited:
            nearest = sorted(
                unvisited,
                key=lambda name: (
                    self.instance.distance(current, self.customers[name]),
                    name,
                ),
            )[: self.neighbour_count]
            selected = self.rng.choice(nearest)
            order.append(selected)
            unvisited.remove(selected)
            current = self.customers[selected]
        return tuple(order)

    def feasible_neighbour_permutation(self) -> tuple[str, ...]:
        """Adapts Algorithm 1's resource checks to benchmark hard time windows.

        The paper checks capacity and battery during neighbour initialization
        but postpones its fuzzy-window penalty to the GA.  Here time windows are
        hard, so a route is closed as soon as no customer can be appended
        feasibly.  Flattening the routes still yields the paper's chromosome
        representation and lets the split decoder improve the boundaries.
        """

        unvisited = set(self.customer_names)
        routes: list[list[str]] = []
        while unvisited:
            route: list[str] = []
            current = self.instance.depot
            while unvisited:
                feasible = [
                    name
                    for name in unvisited
                    if self._route_metrics(route + [name])[0]
                ]
                if not feasible:
                    break
                nearest = sorted(
                    feasible,
                    key=lambda name: (
                        self.instance.distance(current, self.customers[name]),
                        self.customers[name].tw_late,
                        name,
                    ),
                )[: self.neighbour_count]
                selected = self.rng.choice(nearest)
                route.append(selected)
                unvisited.remove(selected)
                current = self.customers[selected]
            if not route:
                # A singleton-infeasible customer means no legal benchmark
                # solution exists under the current depot and vehicle windows.
                route.append(min(unvisited))
                unvisited.remove(route[0])
            routes.append(route)
        compacted = self._compact_to_fleet(routes)
        if compacted is not None:
            routes = compacted
        return tuple(name for route in routes for name in route)

    def _compact_to_fleet(self, routes: Sequence[Sequence[str]]) -> list[list[str]] | None:
        """Reinserts customers from excess routes into at most K hard-feasible routes."""

        routes = [list(route) for route in routes if route]
        target = self.instance.num_vehicles
        if len(routes) <= target:
            return routes

        ranked = sorted(
            enumerate(routes), key=lambda item: (-len(item[1]), item[0])
        )
        retained = [list(route) for _, route in sorted(ranked[:target])]
        pending = [name for _, route in sorted(ranked[target:]) for name in route]

        while pending:
            customer_choices = []
            for pending_index, name in enumerate(pending):
                moves = []
                for route_index, route in enumerate(retained):
                    _, old_distance = self._route_metrics(route)
                    for position in range(len(route) + 1):
                        candidate = route[:position] + [name] + route[position:]
                        feasible, new_distance = self._route_metrics(candidate)
                        if feasible:
                            moves.append(
                                (
                                    new_distance - old_distance,
                                    route_index,
                                    position,
                                    candidate,
                                )
                            )
                if not moves:
                    continue
                moves.sort(key=lambda move: move[:3])
                regret = inf if len(moves) == 1 else moves[1][0] - moves[0][0]
                customer_choices.append(
                    (
                        len(moves),
                        -regret,
                        moves[0][0],
                        name,
                        pending_index,
                        moves[0],
                    )
                )

            if not customer_choices:
                return None
            customer_choices.sort(key=lambda choice: choice[:5])
            _, _, _, _, pending_index, best_move = customer_choices[0]
            _, route_index, _, proposed = best_move
            pending.pop(pending_index)
            retained[route_index] = proposed

        return retained

    def initial_population(self) -> list[tuple[str, ...]]:
        population = []
        seen = set()

        due_order = tuple(
            customer.name
            for customer in sorted(
                self.instance.clients,
                key=lambda customer: (customer.tw_late, customer.tw_early, customer.name),
            )
        )
        population.append(due_order)
        seen.add(due_order)
        attempts = 0
        while len(population) < self.population_size and attempts < self.population_size * 20:
            attempts += 1
            if attempts % 5:
                individual = self.feasible_neighbour_permutation()
            else:
                individual = self.nearest_neighbour_permutation()
            if individual not in seen:
                seen.add(individual)
                population.append(individual)

        while len(population) < self.population_size:
            shuffled = list(self.customer_names)
            self.rng.shuffle(shuffled)
            population.append(tuple(shuffled))
        return population

    def route_fragment_crossover(
        self,
        first: DecodedIndividual,
        second: DecodedIndividual,
    ) -> tuple[str, ...]:
        """Grafts one complete route from parent 1 onto parent 2's head."""

        source_routes = first.routes or (first.permutation,)
        fragment = tuple(self.rng.choice(source_routes))
        fragment_set = set(fragment)
        return fragment + tuple(
            name for name in second.permutation if name not in fragment_set
        )

    def adaptive_removal_count(
        self,
        individual: DecodedIndividual,
        population: Sequence[DecodedIndividual],
    ) -> int:
        """Implements Eq. (20)'s intended fitness-adaptive destruction scale."""

        fitnesses = [1.0 / max(1, item.distance) for item in population]
        fitness = 1.0 / max(1, individual.distance)
        average = sum(fitnesses) / len(fitnesses)
        maximum = max(fitnesses)
        if fitness <= average or maximum <= average + EPS:
            eta = 1.0
        else:
            eta = exp(-(fitness - average) / (maximum - average))
        paper_count = int(eta * max(1, len(individual.routes)) * len(self.customer_names) * 0.1)
        upper = max(1, int(len(self.customer_names) * self.max_removal_fraction))
        return min(max(1, paper_count), upper, max(1, len(self.customer_names) - 1))

    def related_remove(
        self,
        individual: DecodedIndividual,
        count: int,
    ) -> tuple[list[list[str]], list[str]]:
        """Paper Algorithm 2, using the textual same-route preference in Eq. (19)."""

        routes = [list(route) for route in individual.routes]
        route_of = {
            name: route_index
            for route_index, route in enumerate(routes)
            for name in route
        }
        removed = [self.rng.choice(list(individual.permutation))]
        remaining = set(individual.permutation) - set(removed)
        while remaining and len(removed) < count:
            anchor = self.rng.choice(removed)

            def relevance(name: str) -> tuple[float, str]:
                normalized_distance = (
                    self.instance.distance(
                        self.customers[anchor], self.customers[name]
                    )
                    / max(1, self.max_distance)
                )
                # The paper's prose says same-route nodes are more related, while
                # its printed v_ij definition would do the opposite.  A zero
                # penalty for the same route follows the stated intent.
                route_penalty = 0 if route_of[anchor] == route_of[name] else 1
                score = 1.0 / (normalized_distance + route_penalty + EPS)
                return score, name

            selected = max(remaining, key=relevance)
            removed.append(selected)
            remaining.remove(selected)

        removed_set = set(removed)
        return [
            [name for name in route if name not in removed_set]
            for route in routes
            if any(name not in removed_set for name in route)
        ], removed

    def minimum_increment_reinsert(
        self,
        routes: list[list[str]],
        removed: Iterable[str],
    ) -> tuple[str, ...]:
        """Paper Algorithm 3 under hard TW/capacity and linear benchmark energy."""

        routes = [list(route) for route in routes]
        removed = list(removed)
        self.rng.shuffle(removed)
        deferred = []
        for name in removed:
            choices = []
            for route_index, route in enumerate(routes):
                _, old_distance = self._route_metrics(route)
                for position in range(len(route) + 1):
                    candidate = route[:position] + [name] + route[position:]
                    feasible, new_distance = self._route_metrics(candidate)
                    if feasible:
                        energy_increment = (
                            new_distance - old_distance
                        ) * (self.instance.energy.consumption_per_distance or 1)
                        choices.append(
                            (energy_increment, new_distance, route_index, position)
                        )
            if len(routes) < self.instance.num_vehicles:
                feasible, new_distance = self._route_metrics([name])
                if feasible:
                    choices.append((new_distance, new_distance, len(routes), 0))

            if not choices:
                deferred.append(name)
                continue
            _, _, route_index, position = min(choices)
            if route_index == len(routes):
                routes.append([name])
            else:
                routes[route_index].insert(position, name)

        permutation = tuple(name for route in routes for name in route) + tuple(deferred)
        return permutation

    def mutate(
        self,
        individual: DecodedIndividual,
        population: Sequence[DecodedIndividual],
    ) -> tuple[str, ...]:
        count = self.adaptive_removal_count(individual, population)
        routes, removed = self.related_remove(individual, count)
        return self.minimum_increment_reinsert(routes, removed)

    def _roulette(self, population: Sequence[DecodedIndividual]) -> DecodedIndividual:
        finite_distances = [item.distance for item in population if item.feasible]
        baseline = min(finite_distances, default=0)
        weights = [
            1.0 / (1.0 + item.distance - baseline) if item.feasible else EPS
            for item in population
        ]
        return self.rng.choices(population, weights=weights, k=1)[0]

    def solve(self) -> SearchResult:
        population = [self.decode(item) for item in self.initial_population()]
        archive: dict[tuple[str, ...], DecodedIndividual] = {}
        convergence = []

        for generation in range(self.generations + 1):
            population.sort(key=lambda item: (not item.feasible, item.distance))
            for item in population[: max(self.elite_count, 10)]:
                existing = archive.get(item.permutation)
                if existing is None or item.distance < existing.distance:
                    archive[item.permutation] = item
            best = population[0]
            feasible_population = [item for item in population if item.feasible]
            convergence.append(
                {
                    "generation": generation,
                    "best_distance": best.distance if best.feasible else None,
                    "best_vehicle_count": len(best.routes),
                    "feasible_population": len(feasible_population),
                    "population_size": len(population),
                }
            )
            if generation == self.generations:
                break

            next_population = [item.permutation for item in population[: self.elite_count]]
            while len(next_population) < self.population_size:
                first = self._roulette(population)
                second = self._roulette(population)
                if self.rng.random() < self.crossover_probability:
                    child = self.route_fragment_crossover(first, second)
                else:
                    child = first.permutation
                decoded_child = self.decode(child)
                if decoded_child.feasible and self.rng.random() < self.mutation_probability:
                    child = self.mutate(decoded_child, population)
                next_population.append(child)
            population = [self.decode(item) for item in next_population]

        ranked = sorted(
            archive.values(), key=lambda item: (not item.feasible, item.distance)
        )
        return SearchResult(ranked[0], tuple(ranked), tuple(convergence))
