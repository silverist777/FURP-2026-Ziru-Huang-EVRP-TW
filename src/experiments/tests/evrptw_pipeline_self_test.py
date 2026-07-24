import argparse

from checkers.feasibility_checker import check_explicit_routes
from core.instance_loader import load_instance_data
from methods.pyvrp.evrptw_v3_repair import (
    Label,
    charge_decisions_payload,
    dominates,
    dominates_for_feasibility,
    repair_customer_sequence,
    repair_routes_with_splitting,
)
from methods.pyvrp.parse_schneider_instance import convert_schneider_instance


def assert_ok(condition, message):
    if not condition:
        raise AssertionError(message)


def make_instance(
    clients,
    stations,
    vehicles=1,
    capacity=5,
    battery_capacity=10,
):
    return load_instance_data(
        {
            "name": "repair_unit",
            "problem_type": "EVRPTW",
            "distance": {"metric": "euclidean", "scale": 1},
            "duration": {"metric": "euclidean", "scale": 1},
            "solver": {"runtime_seconds": 1, "seed": 1, "display": False},
            "vehicles": {
                "num_available": vehicles,
                "capacity": capacity,
                "start_depot": "D0",
                "end_depot": "D0",
                "tw_early": 0,
                "tw_late": 100,
                "battery_capacity": battery_capacity,
                "initial_battery": battery_capacity,
            },
            "depot": {"name": "D0", "x": 0, "y": 0, "tw_early": 0, "tw_late": 100},
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


def customer(name, x, y=0, demand=1, tw_late=100):
    return {
        "name": name,
        "x": x,
        "y": y,
        "demand": demand,
        "service_duration": 0,
        "tw_early": 0,
        "tw_late": tw_late,
    }


def station(name, x, y=0):
    return {
        "name": name,
        "x": x,
        "y": y,
        "service_duration": 0,
        "tw_early": 0,
        "tw_late": 100,
        "charging_rate": 1,
    }


def test_station_repair():
    instance = make_instance(
        clients=[customer("C1", 8)],
        stations=[station("S1", 4)],
    )
    result = repair_customer_sequence(["C1"], instance)
    assert_ok(result.feasible, "Station-assisted route should be repairable.")
    assert_ok("S1" in result.route, "Repair should insert charging station S1.")


def test_partial_recharge_beats_full_recharge():
    instance = make_instance(
        clients=[customer("C1", 8, tw_late=10)],
        stations=[station("S1", 4)],
        battery_capacity=10,
    )
    result = repair_customer_sequence(["C1"], instance)
    assert_ok(result.feasible, "Partial-recharge route should be repairable.")
    assert_ok(result.charging_count == 2, "Expected two station charging visits.")
    assert_ok(
        result.charge_decisions[0].departure_battery < instance.vehicle.battery_capacity,
        "First station visit should use partial recharge, not full recharge.",
    )

    report = check_explicit_routes(
        routes=[result.route],
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=[charge_decisions_payload(result.charge_decisions)],
    )
    assert_ok(report.feasible, "Checker should accept v3 partial charging plan.")
    assert_ok(report.time_window_violations == 0, "Partial charge should satisfy TW.")


def test_split_repair():
    instance = make_instance(
        clients=[customer("C1", 8), customer("C2", -8)],
        # Five non-depot nodes keep two vehicles available under the shared
        # ceil((clients + charging_stations) / 4) EVRPTW fleet policy.
        stations=[station("S1", 4), station("S2", -4), station("S3", 100)],
        vehicles=2,
        capacity=1,
    )
    plan = repair_routes_with_splitting([["C1", "C2"]], instance)
    assert_ok(plan.feasible, "Capacity failure should be repaired by splitting.")
    assert_ok(plan.split_count == 1, "Expected exactly one split.")
    assert_ok(len(plan.routes) == 2, "Expected two repaired routes.")


def test_unsolved_route():
    instance = make_instance(
        clients=[customer("C1", 10)],
        stations=[],
        battery_capacity=5,
    )
    result = repair_customer_sequence(["C1"], instance)
    assert_ok(not result.feasible, "Unreachable customer should remain unsolved.")


def test_dominance_respects_station_visit_budget():
    fewer_visits = Label(
        location_name="S1",
        position=1,
        time=5,
        battery=5,
        distance=5,
        path=["D0", "S1"],
        charging_time=1,
        station_visits=1,
    )
    more_visits = Label(
        location_name="S1",
        position=1,
        time=4,
        battery=6,
        distance=4,
        path=["D0", "S2", "S1"],
        charging_time=0,
        station_visits=2,
    )
    assert_ok(
        not dominates(more_visits, fewer_visits),
        "A label with less station-visit budget must not be dominated.",
    )
    assert_ok(
        not dominates_for_feasibility(more_visits, fewer_visits),
        "Feasibility dominance must retain the station-visit resource.",
    )


def test_feasibility_first_repair():
    instance = make_instance(
        clients=[customer("C1", 8)],
        stations=[station("S1", 4)],
    )
    result = repair_customer_sequence(
        ["C1"],
        instance,
        feasibility_first=True,
    )
    assert_ok(result.feasible, "Feasibility-first repair should find a route.")

    report = check_explicit_routes(
        routes=[result.route],
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=[charge_decisions_payload(result.charge_decisions)],
    )
    assert_ok(report.feasible, "Checker should accept feasibility-first output.")


def test_real_schneider_parser(path):
    data = convert_schneider_instance(path, num_vehicles=2, solver_runtime_seconds=1)
    assert_ok(data["vehicles"]["battery_capacity"] == 77.75, "Q parse failed.")
    assert_ok(data["vehicles"]["capacity"] == 200, "C parse failed.")
    assert_ok(data["energy"]["consumption_per_distance"] == 1, "r parse failed.")
    assert_ok(
        round(1 / data["charging"]["charging_rate"], 2) == 3.47,
        "g parse failed.",
    )
    assert_ok(data["duration"]["scale"] == 1, "v parse failed.")


def main():
    parser = argparse.ArgumentParser(description="EVRP-TW pipeline regression tests.")
    parser.add_argument("--schneider", default=None)
    args = parser.parse_args()

    test_station_repair()
    test_partial_recharge_beats_full_recharge()
    test_split_repair()
    test_unsolved_route()
    test_dominance_respects_station_visit_budget()
    test_feasibility_first_repair()
    if args.schneider is not None:
        test_real_schneider_parser(args.schneider)
    print("EVRP-TW pipeline self-test passed.")


if __name__ == "__main__":
    main()
