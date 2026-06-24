"""Focused self-tests for the project-local VRPTW POMO support code."""

from __future__ import annotations

from pathlib import Path

import torch
from tensordict import TensorDict

from vrptw_support import (
    SolomonLikeVRPTWGenerator,
    StrictCVRPTWEnv,
    check_tensordict_actions,
    parse_solomon_instance,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def assert_ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def make_env(num_loc: int) -> StrictCVRPTWEnv:
    generator = SolomonLikeVRPTWGenerator(
        num_loc=num_loc,
        capacity=1.0,
        max_time=100.0,
        service_duration=0.0,
    )
    return StrictCVRPTWEnv(generator=generator)


def test_solomon_parser() -> None:
    instance = parse_solomon_instance(REPO_ROOT / "src" / "data" / "Solomon" / "C101.txt")
    assert_ok(instance.depot.cust_no == 0, "depot row should have cust_no=0")
    assert_ok(instance.vehicles == 25, "C101 vehicle count should be parsed")
    assert_ok(instance.capacity == 200, "C101 capacity should be parsed")
    assert_ok(instance.known_cost == 827.3, "C101 known cost should be parsed as float")
    assert_ok(instance.num_clients == 100, "C101 should contain 100 customers")


def test_action_masks() -> None:
    env = make_env(4)
    td_input = TensorDict(
        {
            "depot": torch.tensor([[0.0, 0.0]]),
            "locs": torch.tensor([[[10.0, 0.0], [1.0, 0.0], [20.0, 0.0], [1.0, 1.0]]]),
            "demand": torch.tensor([[0.1, 0.1, 0.1, 1.1]]),
            "durations": torch.tensor([[0.0, 0.0, 0.0, 10.0, 0.0]]),
            "time_windows": torch.tensor(
                [[[0.0, 45.0], [0.0, 5.0], [10.0, 20.0], [0.0, 90.0], [0.0, 40.0]]]
            ),
        },
        batch_size=[1],
    )
    td = env.reset(td_input)
    mask = td["action_mask"][0].tolist()
    assert_ok(mask[0] is False, "depot should be masked while already at depot")
    assert_ok(mask[1] is False, "late customer should be masked")
    assert_ok(mask[2] is True, "early arrival should wait and remain feasible")
    assert_ok(mask[3] is False, "customer that prevents depot return should be masked")
    assert_ok(mask[4] is False, "over-capacity customer should be masked")

    td["action"] = torch.tensor([2])
    td = env.step(td)["next"]
    assert_ok(td["action_mask"][0, 0].item() is True, "depot should be allowed after leaving depot")


def test_waiting_checker() -> None:
    env = make_env(1)
    td_input = TensorDict(
        {
            "depot": torch.tensor([[0.0, 0.0]]),
            "locs": torch.tensor([[[1.0, 0.0]]]),
            "demand": torch.tensor([[0.1]]),
            "durations": torch.tensor([[0.0, 0.0]]),
            "time_windows": torch.tensor([[[0.0, 30.0], [10.0, 20.0]]]),
        },
        batch_size=[1],
    )
    td = env.reset(td_input)
    result = check_tensordict_actions(td, [1, 0])
    assert_ok(result.feasible, "early arrival with waiting should be feasible")
    assert_ok(result.time_window_violations == 0, "waiting should not be a TW violation")


def main() -> None:
    test_solomon_parser()
    test_action_masks()
    test_waiting_checker()
    print("vrptw_self_test_ok: True")


if __name__ == "__main__":
    main()
