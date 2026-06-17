from pathlib import Path

from feasibility_checker import (
    CheckerConfig,
    ChargingStationSpec,
    CustomerSpec,
    DepotSpec,
    check_explicit_routes,
)
from instance_loader import load_instance
from parse_schneider_instance import convert_schneider_instance, write_instance_json


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_TEXT = ROOT / "data" / "schneider_sample.txt"
SAMPLE_JSON = ROOT / "results" / "schneider_sample_converted.json"


def assert_report(condition, message):
    if not condition:
        raise AssertionError(message)


def test_parser_round_trip():
    converted = convert_schneider_instance(
        SAMPLE_TEXT,
        num_vehicles=2,
        solver_runtime_seconds=1,
        solver_display=False,
    )
    write_instance_json(converted, SAMPLE_JSON)
    instance = load_instance(SAMPLE_JSON)

    assert_report(instance.name == "schneider_sample", "Unexpected instance name.")
    assert_report(len(instance.clients) == 2, "Expected two sample customers.")
    assert_report(
        len(instance.charging_stations) == 1,
        "Expected one sample charging station.",
    )
    assert_report(instance.vehicle.battery_capacity == 10, "Battery capacity mismatch.")
    assert_report(instance.vehicle.capacity == 5, "Vehicle capacity mismatch.")
    assert_report(
        instance.energy.consumption_per_distance == 1,
        "Energy consumption mismatch.",
    )
    assert_report(instance.charging.charging_rate == 1.0, "Charging rate mismatch.")
    return instance


def test_loaded_instance_explicit_route(instance):
    report = check_explicit_routes(
        routes=[["D0", "S1", "C2", "S1", "C1", "D0"]],
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
    )
    assert_report(report.feasible, "Station-assisted sample route should be feasible.")
    assert_report(report.energy_violations == 0, "No energy violations expected.")
    assert_report(report.charging_count > 0, "Route should include charging.")


def test_basic_checker_scenarios():
    depot = DepotSpec(name="D0", x=0, y=0, tw_early=0, tw_late=100)
    close = CustomerSpec(
        name="C1",
        x=2,
        y=0,
        demand=1,
        service_duration=0,
        tw_early=0,
        tw_late=100,
    )
    far = CustomerSpec(
        name="C2",
        x=8,
        y=0,
        demand=1,
        service_duration=0,
        tw_early=0,
        tw_late=100,
    )
    station = ChargingStationSpec(
        name="S1",
        x=4,
        y=0,
        service_duration=0,
        tw_early=0,
        tw_late=100,
        charging_rate=1.0,
    )
    config = CheckerConfig(
        vehicle_capacity=5,
        distance_scale=1,
        duration_scale=1,
        battery_capacity=10,
        initial_battery=10,
        energy_per_distance=1,
        minimum_battery=0,
        charging_rate=1.0,
    )

    no_charge = check_explicit_routes(
        routes=[["D0", "C1", "D0"]],
        depot=depot,
        customers=[close],
        charging_stations=[station],
        config=config,
    )
    assert_report(no_charge.feasible, "Short route should be feasible without charging.")

    needs_charge = check_explicit_routes(
        routes=[["D0", "C2", "D0"]],
        depot=depot,
        customers=[far],
        charging_stations=[station],
        config=config,
    )
    assert_report(not needs_charge.feasible, "Long route should be infeasible.")
    assert_report(
        needs_charge.energy_violations > 0,
        "Long route should report energy violations.",
    )

    with_charge = check_explicit_routes(
        routes=[["D0", "S1", "C2", "S1", "D0"]],
        depot=depot,
        customers=[far],
        charging_stations=[station],
        config=config,
    )
    assert_report(with_charge.feasible, "Station route should repair energy feasibility.")
    assert_report(with_charge.energy_violations == 0, "Repaired route should save energy.")
    assert_report(with_charge.charging_count > 0, "Repaired route should charge.")

    capacity = check_explicit_routes(
        routes=[["D0", "C1", "D0"]],
        depot=depot,
        customers=[
            CustomerSpec(
                name="C1",
                x=1,
                y=0,
                demand=6,
                service_duration=0,
                tw_early=0,
                tw_late=100,
            )
        ],
        charging_stations=[],
        config=config,
    )
    assert_report(not capacity.feasible, "Over-capacity route should be infeasible.")
    assert_report(
        capacity.capacity_violations > 0,
        "Over-capacity route should report capacity violations.",
    )

    duplicate_missing = check_explicit_routes(
        routes=[["D0", "C1", "C1", "D0"]],
        depot=depot,
        customers=[close, far],
        charging_stations=[],
        config=config,
    )
    assert_report(
        not duplicate_missing.feasible,
        "Duplicate and missing customers should be infeasible.",
    )
    assert_report(
        duplicate_missing.duplicate_customers == ["C1"],
        "Expected duplicate C1.",
    )
    assert_report(
        duplicate_missing.missing_customers == ["C2"],
        "Expected missing C2.",
    )


def main():
    instance = test_parser_round_trip()
    test_loaded_instance_explicit_route(instance)
    test_basic_checker_scenarios()
    print(f"EVRP-TW checker self-test passed. Sample JSON: {SAMPLE_JSON}")


if __name__ == "__main__":
    main()
