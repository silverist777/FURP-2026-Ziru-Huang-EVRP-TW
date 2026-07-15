"""Regression checks for the shared EVRPTW vehicle-limit policy."""

from core.evrptw_fleet_policy import apply_evrptw_vehicle_limit, evrptw_vehicle_limit


def sample(problem_type="EVRPTW", clients=10, stations=5, vehicles=999):
    return {
        "problem_type": problem_type,
        "clients": [{} for _ in range(clients)],
        "charging_stations": [{} for _ in range(stations)],
        "vehicles": {"num_available": vehicles},
    }


def main() -> None:
    data = sample()
    assert evrptw_vehicle_limit(data) == 4
    assert apply_evrptw_vehicle_limit(data) == 4
    assert data["vehicles"]["num_available"] == 4
    assert data["vehicle_limit_policy"]["formula"] == "ceil((clients + charging_stations) / 4)"

    small = sample(clients=5, stations=3)
    assert apply_evrptw_vehicle_limit(small) == 2

    vrptw = sample(problem_type="VRPTW")
    assert apply_evrptw_vehicle_limit(vrptw) is None
    assert vrptw["vehicles"]["num_available"] == 999
    print("EVRPTW fleet-policy self-test passed.")


if __name__ == "__main__":
    main()
