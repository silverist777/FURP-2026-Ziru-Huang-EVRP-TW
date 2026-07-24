"""Fleet-constrained compaction for RouteFinder customer routes.

The compactor preserves the instance capacity and time-window constraints. It
does not approximate battery feasibility: complete compacted routes still pass
through the shared EVRP-TW partial-recharge repair and independent checker.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter


@dataclass(frozen=True)
class FleetCompactionResult:
    feasible: bool
    routes: list[list[str]]
    input_route_count: int
    output_route_count: int
    target_max_vehicles: int
    moved_customers: int
    evaluated_insertions: int
    runtime_seconds: float
    failure_reason: str = ""


def is_vrptw_customer_sequence_feasible(
    customer_names: list[str],
    instance,
    customers_by_name: dict,
) -> bool:
    """Checks capacity, customer TWs, and the final depot return."""

    if (
        sum(customers_by_name[name].demand for name in customer_names)
        > instance.vehicle_capacity
    ):
        return False

    current = instance.depot
    current_time = 0
    for name in customer_names:
        customer = customers_by_name[name]
        arrival = current_time + instance.travel_duration(current, customer)
        service_start = max(arrival, customer.tw_early)
        if service_start > customer.tw_late:
            return False
        current_time = service_start + customer.service_duration
        current = customer

    return (
        current_time + instance.travel_duration(current, instance.depot)
        <= instance.depot.tw_late
    )


def insertion_distance_delta(
    route: list[str],
    customer_name: str,
    position: int,
    instance,
    customers_by_name: dict,
) -> int:
    customer = customers_by_name[customer_name]
    previous = (
        instance.depot
        if position == 0
        else customers_by_name[route[position - 1]]
    )
    following = (
        instance.depot
        if position == len(route)
        else customers_by_name[route[position]]
    )
    return (
        instance.distance(previous, customer)
        + instance.distance(customer, following)
        - instance.distance(previous, following)
    )


def compact_routes_to_vehicle_limit(
    customer_routes: list[list[str]],
    instance,
) -> FleetCompactionResult:
    """Compacts exact customer coverage to the instance's hard fleet limit.

    The longest RouteFinder routes are retained as anchors. Customers from
    excess routes are reinserted using fail-first regret insertion. Every move
    is screened against exact project capacity and forward TW calculations.
    """

    started = perf_counter()
    routes = [list(route) for route in customer_routes if route]
    input_route_count = len(routes)
    target = int(instance.num_vehicles)
    customers_by_name = {customer.name: customer for customer in instance.clients}
    flattened = [name for route in routes for name in route]
    expected = [customer.name for customer in instance.clients]

    def result(
        *,
        feasible: bool,
        output_routes: list[list[str]],
        moved_customers: int,
        evaluated_insertions: int,
        failure_reason: str = "",
    ) -> FleetCompactionResult:
        return FleetCompactionResult(
            feasible=feasible,
            routes=output_routes,
            input_route_count=input_route_count,
            output_route_count=len(output_routes),
            target_max_vehicles=target,
            moved_customers=moved_customers,
            evaluated_insertions=evaluated_insertions,
            runtime_seconds=round(perf_counter() - started, 6),
            failure_reason=failure_reason,
        )

    if target <= 0:
        return result(
            feasible=False,
            output_routes=routes,
            moved_customers=0,
            evaluated_insertions=0,
            failure_reason="invalid_vehicle_limit",
        )
    if sorted(flattened) != sorted(expected):
        return result(
            feasible=False,
            output_routes=routes,
            moved_customers=0,
            evaluated_insertions=0,
            failure_reason="customer_coverage_mismatch",
        )
    invalid_route_indexes = [
        index
        for index, route in enumerate(routes, start=1)
        if not is_vrptw_customer_sequence_feasible(
            route,
            instance,
            customers_by_name,
        )
    ]
    if invalid_route_indexes:
        return result(
            feasible=False,
            output_routes=routes,
            moved_customers=0,
            evaluated_insertions=0,
            failure_reason=(
                "input_route_capacity_or_time_window_infeasible:"
                + ",".join(str(index) for index in invalid_route_indexes)
            ),
        )
    if input_route_count <= target:
        return result(
            feasible=True,
            output_routes=routes,
            moved_customers=0,
            evaluated_insertions=0,
        )

    ranked = sorted(
        enumerate(routes),
        key=lambda item: (-len(item[1]), item[0]),
    )
    retained = sorted(ranked[:target], key=lambda item: item[0])
    removed = sorted(ranked[target:], key=lambda item: item[0])
    compacted = [list(route) for _, route in retained]
    route_loads = [
        sum(customers_by_name[name].demand for name in route)
        for route in compacted
    ]
    pending = [name for _, route in removed for name in route]
    moved_customers = len(pending)
    evaluated_insertions = 0

    while pending:
        customer_choices = []
        for pending_index, customer_name in enumerate(pending):
            customer = customers_by_name[customer_name]
            moves = []
            for route_index, route in enumerate(compacted):
                if (
                    route_loads[route_index] + customer.demand
                    > instance.vehicle_capacity
                ):
                    continue
                for position in range(len(route) + 1):
                    evaluated_insertions += 1
                    proposed = [
                        *route[:position],
                        customer_name,
                        *route[position:],
                    ]
                    if not is_vrptw_customer_sequence_feasible(
                        proposed,
                        instance,
                        customers_by_name,
                    ):
                        continue
                    moves.append(
                        (
                            insertion_distance_delta(
                                route,
                                customer_name,
                                position,
                                instance,
                                customers_by_name,
                            ),
                            route_index,
                            position,
                            proposed,
                        )
                    )

            if not moves:
                continue
            moves.sort(key=lambda move: (move[0], move[1], move[2]))
            regret = inf if len(moves) == 1 else moves[1][0] - moves[0][0]
            customer_choices.append(
                (
                    len(moves),
                    -regret,
                    moves[0][0],
                    customer_name,
                    pending_index,
                    moves[0],
                )
            )

        if not customer_choices:
            return result(
                feasible=False,
                output_routes=compacted,
                moved_customers=moved_customers,
                evaluated_insertions=evaluated_insertions,
                failure_reason=(
                    "no_capacity_and_time_window_feasible_insertion:"
                    + ",".join(pending)
                ),
            )

        customer_choices.sort(key=lambda choice: choice[:5])
        _, _, _, _, pending_index, best_move = customer_choices[0]
        _, route_index, _, proposed = best_move
        customer_name = pending.pop(pending_index)
        compacted[route_index] = proposed
        route_loads[route_index] += customers_by_name[customer_name].demand

    if sorted(name for route in compacted for name in route) != sorted(expected):
        return result(
            feasible=False,
            output_routes=compacted,
            moved_customers=moved_customers,
            evaluated_insertions=evaluated_insertions,
            failure_reason="customer_coverage_changed_after_compaction",
        )

    return result(
        feasible=True,
        output_routes=compacted,
        moved_customers=moved_customers,
        evaluated_insertions=evaluated_insertions,
    )
