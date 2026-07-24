"""Regression checks for RouteFinder fleet-constrained compaction."""

from copy import deepcopy

from core.instance_loader import load_instance_data
from methods.routefinder.fleet_compaction import (
    compact_routes_to_vehicle_limit,
    is_vrptw_customer_sequence_feasible,
)


def make_instance(capacity=3):
    clients = [
        {
            "name": f"C{index}",
            "x": index,
            "y": 0,
            "demand": 1,
            "service_duration": 0,
            "tw_early": 0,
            "tw_late": 100,
        }
        for index in range(1, 6)
    ]
    stations = [
        {
            "name": f"S{index}",
            "x": 0,
            "y": index,
            "service_duration": 0,
            "tw_early": 0,
            "tw_late": 100,
            "charging_rate": 1,
        }
        for index in range(1, 4)
    ]
    return load_instance_data(
        {
            "name": "fleet_compaction_unit",
            "problem_type": "EVRPTW",
            "distance": {"metric": "euclidean", "scale": 1},
            "duration": {"metric": "euclidean", "scale": 1},
            "vehicles": {
                "num_available": 999,
                "capacity": capacity,
                "start_depot": "D0",
                "end_depot": "D0",
                "tw_early": 0,
                "tw_late": 100,
                "battery_capacity": 100,
                "initial_battery": 100,
            },
            "depot": {
                "name": "D0",
                "x": 0,
                "y": 0,
                "tw_early": 0,
                "tw_late": 100,
            },
            "energy": {"consumption_per_distance": 1, "minimum_battery": 0},
            "charging": {
                "policy": "partial_recharge",
                "allow_partial_recharge": True,
                "charging_rate": 1,
                "fixed_service_duration": 0,
            },
            "charging_stations": stations,
            "clients": clients,
        }
    )


def main():
    routes = [["C1", "C2"], ["C3"], ["C4"], ["C5"]]
    original = deepcopy(routes)
    instance = make_instance(capacity=3)
    result = compact_routes_to_vehicle_limit(routes, instance)

    assert routes == original, "Compaction must not mutate RouteFinder routes."
    assert instance.num_vehicles == 2
    assert result.feasible
    assert result.input_route_count == 4
    assert result.output_route_count == 2
    assert result.output_route_count <= instance.num_vehicles
    assert sorted(name for route in result.routes for name in route) == [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
    ]
    customers_by_name = {customer.name: customer for customer in instance.clients}
    assert all(
        is_vrptw_customer_sequence_feasible(
            route,
            instance,
            customers_by_name,
        )
        for route in result.routes
    )

    impossible = compact_routes_to_vehicle_limit(
        routes,
        make_instance(capacity=2),
    )
    assert not impossible.feasible
    assert impossible.failure_reason.startswith(
        "no_capacity_and_time_window_feasible_insertion"
    )

    invalid_input = compact_routes_to_vehicle_limit(
        [["C1", "C2", "C3"], ["C4", "C5"]],
        make_instance(capacity=2),
    )
    assert not invalid_input.feasible
    assert invalid_input.failure_reason == (
        "input_route_capacity_or_time_window_infeasible:1"
    )
    print("RouteFinder fleet-compaction self-test passed.")


if __name__ == "__main__":
    main()
