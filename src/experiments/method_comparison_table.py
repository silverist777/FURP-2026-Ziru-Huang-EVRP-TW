"""Build the PYVRP/POMO method comparison table requested for the report.

The table contains two methods (PYVRP and POMO) at four client counts:
20, 50, 100, and 200. The 20/50/100-client cases are derived from Solomon
C101; 20 and 50 are random customer subsets. The 200-client case uses the
Holmberger C1_2_1 instance. Electric-vehicle constraints are not modelled.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
POMO_DIR = REPO_ROOT / "src" / "experiments" / "POMO"
PYVRP_DIR = REPO_ROOT / "src" / "experiments" / "PyVRP"
CACHE_ROOT = REPO_ROOT / ".cache" / "method_comparison"
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("WANDB_DISABLED", "true")
CACHE_ROOT.mkdir(parents=True, exist_ok=True)
(CACHE_ROOT / "matplotlib").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(POMO_DIR))
sys.path.insert(0, str(PYVRP_DIR))

import torch
from pyvrp import Model
from pyvrp.stop import MaxRuntime
from rl4co.models.zoo.pomo import POMO
from rl4co.utils.ops import unbatchify

from vrptw_support import (
    SolomonCustomer,
    SolomonInstance,
    SolomonLikeVRPTWGenerator,
    StrictCVRPTWEnv,
    check_solomon_actions,
    parse_solomon_instance,
    solomon_to_tensordict,
)


SCALE = 10
DEFAULT_OUTPUT_DIR = REPO_ROOT / "src" / "results" / "method_comparison"
DEFAULT_SOLOMON = REPO_ROOT / "py-ga-VRPTW" / "data" / "text" / "C101.txt"
DEFAULT_HOLMBERGER = REPO_ROOT / "src" / "data" / "Holmberger" / "C1_2_1.txt"


@dataclass(frozen=True)
class ExperimentCase:
    label: str
    source: str
    client_count: int
    instance: SolomonInstance
    selected_cust_no: list[int]


def scaled(value: float) -> int:
    return int(round(value * SCALE))


def euclidean(a: SolomonCustomer, b: SolomonCustomer) -> float:
    return math.dist((a.x, a.y), (b.x, b.y))


def sample_instance(
    base: SolomonInstance,
    client_count: int,
    seed: int,
    source_label: str,
) -> ExperimentCase:
    rng = random.Random(seed + client_count)
    if client_count < base.num_clients:
        selected = sorted(rng.sample([c.cust_no for c in base.customers], client_count))
        customers = [customer for customer in base.customers if customer.cust_no in selected]
    else:
        selected = [customer.cust_no for customer in base.customers]
        customers = list(base.customers)

    instance = replace(
        base,
        name=f"{base.name}_{client_count}",
        customers=customers,
        known_cost=None,
        solution_path=None,
    )
    return ExperimentCase(
        label=instance.name,
        source=source_label,
        client_count=client_count,
        instance=instance,
        selected_cust_no=selected,
    )


def build_cases(solomon_path: Path, holmberger_path: Path, seed: int) -> list[ExperimentCase]:
    solomon = parse_solomon_instance(solomon_path)
    holmberger = parse_solomon_instance(holmberger_path)
    cases = [
        sample_instance(solomon, 20, seed, f"Solomon {solomon_path.name}"),
        sample_instance(solomon, 50, seed, f"Solomon {solomon_path.name}"),
        sample_instance(solomon, 100, seed, f"Solomon {solomon_path.name}"),
    ]
    cases.append(
        ExperimentCase(
            label=holmberger.name,
            source=f"Holmberger {holmberger_path.name}",
            client_count=holmberger.num_clients,
            instance=holmberger,
            selected_cust_no=[customer.cust_no for customer in holmberger.customers],
        )
    )
    return cases


def write_case_instance(case: ExperimentCase, output_dir: Path) -> Path:
    """Write the exact cropped benchmark instance used in a case."""

    path = output_dir / f"{case.label}.txt"
    instance = case.instance
    rows = [instance.depot, *instance.customers]
    with path.open("w", encoding="utf-8") as file:
        file.write(f"{case.label}\n\n")
        file.write("VEHICLE\n")
        file.write("NUMBER     CAPACITY\n")
        file.write(f"{instance.vehicles:4d}{int(instance.capacity):12d}\n\n")
        file.write("CUSTOMER\n")
        file.write(
            "CUST NO.  XCOORD.    YCOORD.    DEMAND   READY TIME  "
            "DUE DATE   SERVICE TIME\n"
        )
        file.write(" \n")
        for row in rows:
            file.write(
                f"{row.cust_no:5d}"
                f"{row.x:10.0f}"
                f"{row.y:11.0f}"
                f"{row.demand:11.0f}"
                f"{row.ready_time:11.0f}"
                f"{row.due_time:11.0f}"
                f"{row.service_time:11.0f}\n"
            )
    return path
def build_pyvrp_model(instance: SolomonInstance) -> Model:
    model = Model()
    depot = model.add_depot(
        x=scaled(instance.depot.x),
        y=scaled(instance.depot.y),
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
        name=str(instance.depot.cust_no),
    )
    clients = [
        model.add_client(
            x=scaled(customer.x),
            y=scaled(customer.y),
            delivery=int(customer.demand),
            service_duration=scaled(customer.service_time),
            tw_early=scaled(customer.ready_time),
            tw_late=scaled(customer.due_time),
            name=str(customer.cust_no),
        )
        for customer in instance.customers
    ]
    model.add_vehicle_type(
        num_available=instance.vehicles,
        capacity=int(instance.capacity),
        start_depot=depot,
        end_depot=depot,
        tw_early=scaled(instance.depot.ready_time),
        tw_late=scaled(instance.depot.due_time),
    )

    original_locations = [instance.depot, *instance.customers]
    pyvrp_locations = [depot, *clients]
    for frm_idx, frm in enumerate(pyvrp_locations):
        for to_idx, to in enumerate(pyvrp_locations):
            if frm is to:
                continue
            distance = scaled(euclidean(original_locations[frm_idx], original_locations[to_idx]))
            model.add_edge(frm, to, distance=distance, duration=distance)
    return model


def evaluate_pyvrp(case: ExperimentCase, runtime_seconds: int, seed: int) -> dict[str, object]:
    started = time.perf_counter()
    model = build_pyvrp_model(case.instance)
    result = model.solve(MaxRuntime(runtime_seconds), seed=seed, display=False)
    elapsed = time.perf_counter() - started
    solution = result.best
    objective = solution.distance() / SCALE
    feasible = solution.is_feasible()
    details = (
        f"MaxRuntime={runtime_seconds}s; routes={solution.num_routes()}; "
        f"time_warp={solution.time_warp() / SCALE:.1f}; "
        f"excess_load={list(solution.excess_load())}"
    )
    return make_row(
        method="PYVRP",
        case=case,
        objective=objective,
        feasible=feasible,
        runtime=elapsed,
        details=details,
        seed=seed,
        model_status="exact checkpoint not applicable",
    )


def make_pomo_env(num_loc: int, max_time: float, capacity: float) -> StrictCVRPTWEnv:
    generator = SolomonLikeVRPTWGenerator(
        num_loc=num_loc,
        min_loc=0.0,
        max_loc=max_time,
        capacity=capacity,
        min_demand=1,
        max_demand=10,
        max_time=max_time,
        service_duration=90,
        scale=True,
    )
    return StrictCVRPTWEnv(generator=generator)


def make_pomo_model(num_loc: int, max_time: float, capacity: float) -> POMO:
    env = make_pomo_env(num_loc, max_time, capacity)
    return POMO(
        env,
        num_augment=1,
        policy_kwargs={
            "embed_dim": 64,
            "num_encoder_layers": 2,
            "num_heads": 4,
            "feedforward_hidden": 128,
        },
        batch_size=1,
        val_batch_size=1,
        test_batch_size=1,
        train_data_size=1,
        val_data_size=1,
        test_data_size=1,
        optimizer_kwargs={"lr": 1e-4},
        dataloader_num_workers=0,
        log_on_step=False,
    )


def evaluate_pomo(
    case: ExperimentCase,
    model: POMO,
    device: str,
    seed: int,
    model_status: str,
) -> dict[str, object]:
    torch.manual_seed(seed)
    started = time.perf_counter()
    env = make_pomo_env(
        case.instance.num_clients,
        max(case.instance.depot.due_time, 1.0),
        case.instance.capacity,
    )
    td_input = solomon_to_tensordict(case.instance, device=device)
    td = env.reset(td_input)
    num_starts = env.get_num_starts(td)
    with torch.inference_mode():
        out = model.policy(td, env, phase="test", num_starts=num_starts, return_actions=True)
    elapsed = time.perf_counter() - started

    rewards = unbatchify(out["reward"], (1, num_starts)).squeeze(1)
    actions = unbatchify(out["actions"], (1, num_starts)).squeeze(1)
    best_idx = rewards[0].argmax()
    best_actions = actions[0, best_idx].detach().cpu().tolist()
    check = check_solomon_actions(case.instance, best_actions)
    feasible = check.feasible
    details = (
        f"num_starts={num_starts}; missing={check.missing_customers}; "
        f"tw_violations={check.time_window_violations}; "
        f"capacity_violations={check.capacity_violations}; "
        f"depot_return_violations={check.depot_return_violations}"
    )
    return make_row(
        method="POMO",
        case=case,
        objective=check.predicted_cost,
        feasible=feasible,
        runtime=elapsed,
        details=details,
        seed=seed,
        model_status=model_status,
    )


def make_row(
    method: str,
    case: ExperimentCase,
    objective: float,
    feasible: bool,
    runtime: float,
    details: str,
    seed: int,
    model_status: str,
) -> dict[str, object]:
    selected = (
        ",".join(str(num) for num in case.selected_cust_no)
        if case.client_count < 100
        else f"all customers 1-{case.client_count}"
    )
    return {
        "method": method,
        "clients": case.client_count,
        "instance": case.label,
        "source": case.source,
        "selected_cust_no": selected,
        "objective_value": round(objective, 3),
        "feasibility_status_under_added_constraints": (
            "feasible; E disabled; TW and capacity enforced"
            if feasible
            else "infeasible; E disabled; TW and capacity checked"
        ),
        "runtime_seconds": round(runtime, 3),
        "convergence_details": details,
        "seed": seed,
        "model_status": model_status,
    }


def write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    headers = [
        "method",
        "clients",
        "source",
        "selected_cust_no",
        "objective_value",
        "feasibility_status_under_added_constraints",
        "runtime_seconds",
        "convergence_details",
        "model_status",
    ]
    with path.open("w", encoding="utf-8") as file:
        file.write("# Method Comparison and Record\n\n")
        file.write(
            "Electric-vehicle constraints are disabled for both methods. "
            "Time windows and capacity are still enforced or checked.\n\n"
        )
        file.write("| " + " | ".join(headers) + " |\n")
        file.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for row in rows:
            values = [str(row[header]).replace("|", "\\|") for header in headers]
            file.write("| " + " | ".join(values) + " |\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate PYVRP/POMO comparison table.")
    parser.add_argument("--solomon", type=Path, default=DEFAULT_SOLOMON)
    parser.add_argument("--holmberger", type=Path, default=DEFAULT_HOLMBERGER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--pyvrp-runtime-seconds", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false.")

    torch.manual_seed(args.seed)
    cases = build_cases(args.solomon, args.holmberger, args.seed)
    model_status = "no saved Solomon/Holmberger POMO checkpoint; random initialized eval"
    max_clients = max(case.client_count for case in cases)
    max_time = max(case.instance.depot.due_time for case in cases)
    capacity = max(case.instance.capacity for case in cases)
    pomo_model = make_pomo_model(max_clients, max_time, capacity)
    pomo_model.eval()
    pomo_model.to(args.device)

    rows: list[dict[str, object]] = []
    for case in cases:
        rows.append(evaluate_pyvrp(case, args.pyvrp_runtime_seconds, args.seed))
        rows.append(evaluate_pomo(case, pomo_model, args.device, args.seed, model_status))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    instance_dir = args.output_dir / "instances"
    instance_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        write_case_instance(case, instance_dir)
    csv_path = args.output_dir / "method_comparison_table.csv"
    md_path = args.output_dir / "method_comparison_table.md"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(rows, md_path)

    print("method_comparison_ok: True")
    print(f"csv: {csv_path}")
    print(f"markdown: {md_path}")
    for row in rows:
        print(
            f"{row['method']} clients={row['clients']} "
            f"objective={row['objective_value']} runtime={row['runtime_seconds']} "
            f"{row['feasibility_status_under_added_constraints']}"
        )


if __name__ == "__main__":
    main()


