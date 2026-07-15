"""Focused self-tests for the Schneider Part 4 VNS/TS implementation."""

from __future__ import annotations

from collections import Counter
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
EXPERIMENTS_ROOT = SRC_ROOT / "experiments"
sys.path.insert(0, str(EXPERIMENTS_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from core.instance_loader import load_instance_data  # noqa: E402
from methods.vns_ts.schneider_vns_ts import SchneiderVNSTS, SearchConfig, SolutionEvaluator  # noqa: E402


def test_instance(battery_capacity: int = 10):
    return load_instance_data(
        {
            "name": "schneider_vns_ts_unit",
            "problem_type": "EVRPTW",
            "distance": {"metric": "euclidean", "scale": 1},
            "duration": {"metric": "euclidean", "scale": 1},
            "vehicles": {
                "num_available": 3,
                "capacity": 10,
                "start_depot": "D0",
                "end_depot": "D0",
                "tw_early": 0,
                "tw_late": 1_000,
                "battery_capacity": battery_capacity,
                "initial_battery": battery_capacity,
            },
            "depot": {"name": "D0", "x": 0, "y": 0, "tw_early": 0, "tw_late": 1_000},
            "energy": {"consumption_per_distance": 1, "minimum_battery": 0},
            "charging": {
                "policy": "full_recharge",
                "allow_partial_recharge": False,
                "charging_rate": 2,
                "fixed_service_duration": 0,
            },
            "charging_stations": [
                {
                    "name": "S1",
                    "x": 4,
                    "y": 0,
                    "service_duration": 0,
                    "tw_early": 0,
                    "tw_late": 1_000,
                    "charging_rate": 2,
                }
            ],
            "clients": [
                {
                    "name": "C1",
                    "x": 8,
                    "y": 0,
                    "demand": 1,
                    "service_duration": 0,
                    "tw_early": 0,
                    "tw_late": 1_000,
                },
                {
                    "name": "C2",
                    "x": 2,
                    "y": 1,
                    "demand": 1,
                    "service_duration": 0,
                    "tw_early": 0,
                    "tw_late": 1_000,
                },
            ],
        }
    )


def test_full_recharge_evaluation() -> None:
    evaluator = SolutionEvaluator(test_instance())
    direct = evaluator.solution([["C1"], ["C2"]])
    with_station = evaluator.solution([["S1", "C1", "S1"], ["C2"]])
    assert direct.battery_violation > 0
    assert with_station.battery_violation == 0
    assert with_station.charging_count == 2
    assert with_station.feasible


def test_cyclic_exchange_preserves_vertices() -> None:
    solver = SchneiderVNSTS(
        test_instance(30),
        SearchConfig(seed=4, max_vehicles=3, tabu_iterations=1, distance_iterations=0, progress_interval=0),
    )
    original = solver.evaluator.solution([["C1", "S1"], ["C2"], []])
    shaken = solver.cyclic_exchange(original, 15)
    assert Counter(name for route in original.routes for name in route) == Counter(
        name for route in shaken.routes for name in route
    )


def test_composite_neighborhood() -> None:
    solver = SchneiderVNSTS(
        test_instance(30),
        SearchConfig(
            seed=2,
            max_vehicles=3,
            max_candidate_moves=1_000,
            candidate_list_size=10,
            station_candidates_per_arc=1,
            tabu_iterations=1,
            distance_iterations=0,
            progress_interval=0,
        ),
    )
    evaluation = solver.evaluator.solution([["C1", "S1"], ["C2"]])
    kinds = {move.kind for move in solver.generate_moves(evaluation)}
    assert "relocate" in kinds
    assert "exchange" in kinds
    assert "2-opt*" in kinds
    assert "stationInRe-insert" in kinds
    assert "stationInRe-remove" in kinds


def test_search_finds_station_solution_without_repair() -> None:
    solver = SchneiderVNSTS(
        test_instance(),
        SearchConfig(
            seed=1,
            max_vehicles=3,
            initial_vehicles=2,
            feasibility_iterations=2,
            distance_iterations=2,
            tabu_iterations=3,
            max_candidate_moves=200,
            candidate_list_size=10,
            station_candidates_per_arc=1,
            penalty_update_interval=2,
            progress_interval=0,
        ),
    )
    result = solver.run()
    assert result.best.feasible
    assert any("S1" in route for route in result.best.routes)
    assert result.evaluated_moves > 0


def test_initial_solution_has_no_empty_active_route() -> None:
    solver = SchneiderVNSTS(
        test_instance(),
        SearchConfig(seed=1, max_vehicles=2, initial_vehicles=2, progress_interval=0),
    )
    routes = solver.initial_solution(2)
    assert len(routes) == 2
    assert all(any(name.startswith("C") for name in route) for route in routes)


def main() -> None:
    test_full_recharge_evaluation()
    test_cyclic_exchange_preserves_vertices()
    test_composite_neighborhood()
    test_search_finds_station_solution_without_repair()
    test_initial_solution_has_no_empty_active_route()
    print("Schneider Part 4 VNS/TS self-tests passed.")


if __name__ == "__main__":
    main()
