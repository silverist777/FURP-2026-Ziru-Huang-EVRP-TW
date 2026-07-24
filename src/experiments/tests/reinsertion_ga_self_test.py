"""Regression tests for the benchmark-adapted Li-Zhu-Lee RI-GA."""

from __future__ import annotations

import argparse

from checkers.feasibility_checker import check_explicit_routes
from core.instance_loader import load_instance_data
from methods.ga.reinsertion_ga import ReinsertionGA
from methods.pyvrp.evrptw_v3_repair import repair_routes_with_splitting
from methods.pyvrp.parse_schneider_instance import convert_schneider_instance


def assert_ok(condition, message):
    if not condition:
        raise AssertionError(message)


def make_instance():
    return load_instance_data(
        {
            "name": "ri_ga_unit",
            "problem_type": "EVRPTW",
            "distance": {"metric": "euclidean", "scale": 1},
            "duration": {"metric": "euclidean", "scale": 1},
            "solver": {"runtime_seconds": 0, "seed": 7, "display": False},
            "vehicles": {
                "num_available": 2,
                "capacity": 2,
                "start_depot": "D0",
                "end_depot": "D0",
                "tw_early": 0,
                "tw_late": 100,
                "battery_capacity": 12,
                "initial_battery": 12,
            },
            "depot": {"name": "D0", "x": 0, "y": 0, "tw_early": 0, "tw_late": 100},
            "energy": {"consumption_per_distance": 1, "minimum_battery": 0},
            "charging": {
                "policy": "partial_recharge",
                "allow_partial_recharge": True,
                "charging_rate": 1,
                "fixed_service_duration": 0,
            },
            "charging_stations": [
                {
                    "name": "S1",
                    "x": 4,
                    "y": 0,
                    "service_duration": 0,
                    "tw_early": 0,
                    "tw_late": 100,
                    "charging_rate": 1,
                },
                {
                    "name": "S2",
                    "x": -4,
                    "y": 0,
                    "service_duration": 0,
                    "tw_early": 0,
                    "tw_late": 100,
                    "charging_rate": 1,
                },
            ],
            "clients": [
                {"name": "C1", "x": 3, "y": 0, "demand": 1, "service_duration": 0, "tw_early": 0, "tw_late": 30},
                {"name": "C2", "x": 6, "y": 0, "demand": 1, "service_duration": 0, "tw_early": 0, "tw_late": 40},
                {"name": "C3", "x": -3, "y": 0, "demand": 1, "service_duration": 0, "tw_early": 0, "tw_late": 30},
            ],
        }
    )


def test_hard_feasible_split():
    instance = make_instance()
    ga = ReinsertionGA(instance, population_size=6, generations=0, seed=7)
    decoded = ga.decode(["C1", "C2", "C3"])
    assert_ok(decoded.feasible, "Capacity-feasible two-route split should exist.")
    assert_ok(len(decoded.routes) == 2, "Capacity two requires exactly two routes.")
    assert_ok(
        sorted(name for route in decoded.routes for name in route) == ["C1", "C2", "C3"],
        "Split decoder must preserve exact customer coverage.",
    )


def test_remove_reinsert_preserves_permutation():
    instance = make_instance()
    ga = ReinsertionGA(instance, population_size=6, generations=0, seed=7)
    decoded = ga.decode(["C1", "C2", "C3"])
    routes, removed = ga.related_remove(decoded, 2)
    reinserted = ga.minimum_increment_reinsert(routes, removed)
    assert_ok(sorted(reinserted) == ["C1", "C2", "C3"], "RI mutation lost a customer.")
    assert_ok(ga.decode(reinserted).feasible, "RI mutation should retain hard feasibility.")


def test_search_is_deterministic_and_complete():
    instance = make_instance()
    kwargs = dict(population_size=10, generations=4, seed=11)
    first = ReinsertionGA(instance, **kwargs).solve()
    second = ReinsertionGA(instance, **kwargs).solve()
    assert_ok(first.best == second.best, "Fixed seed must reproduce the same best individual.")
    assert_ok(first.best.feasible, "RI-GA should find a hard-feasible customer solution.")
    assert_ok(len(first.convergence) == 5, "Expected generation zero plus four iterations.")


def test_real_schneider_smoke(path):
    data = convert_schneider_instance(
        path,
        num_vehicles=2,
        solver_runtime_seconds=0,
        solver_seed=1,
        solver_display=False,
    )
    instance = load_instance_data(data, default_name="c101C5")
    search = ReinsertionGA(
        instance,
        population_size=12,
        generations=5,
        seed=1,
    ).solve()
    plan = repair_routes_with_splitting(
        [list(route) for route in search.best.routes],
        instance,
        feasibility_first=True,
    )
    report = check_explicit_routes(
        routes=plan.routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=plan.charging_plans,
    )
    assert_ok(plan.feasible and report.feasible, "c101C5 RI-GA smoke must be checker-feasible.")


def main():
    parser = argparse.ArgumentParser(description="RI-GA regression tests.")
    parser.add_argument("--schneider", default=None)
    args = parser.parse_args()
    test_hard_feasible_split()
    test_remove_reinsert_preserves_permutation()
    test_search_is_deterministic_and_complete()
    if args.schneider:
        test_real_schneider_smoke(args.schneider)
    print("Reinsertion GA self-test passed.")


if __name__ == "__main__":
    main()
