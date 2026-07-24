"""Fresh shared-checker validation for one stability-study result JSON."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback


EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = EXPERIMENTS_ROOT.parent
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(EXPERIMENTS_ROOT))

from checkers.feasibility_checker import check_explicit_routes  # noqa: E402
from core.instance_loader import load_instance_data  # noqa: E402
from methods.pyvrp.parse_schneider_instance import (  # noqa: E402
    convert_schneider_instance,
)


CHECKER_PATH = EXPERIMENTS_ROOT / "checkers" / "feasibility_checker.py"
FLEET_POLICY_PATH = EXPERIMENTS_ROOT / "core" / "evrptw_fleet_policy.py"
INSTANCE_LOADER_PATH = EXPERIMENTS_ROOT / "core" / "instance_loader.py"
VALIDATOR_PATH = Path(__file__).resolve()
CONVERTER_PATH = (
    EXPERIMENTS_ROOT / "methods" / "pyvrp" / "parse_schneider_instance.py"
)

EXPECTED_METHOD_NAMES = {
    "pyvrp_repair": ("PyVRP VRPTW + EVRP-TW station repair",),
    "pomo_repair": ("yd-kwon/POMO CVRP + EVRP-TW repair",),
    "vns_ts": ("Schneider-2014 hybrid VNS/TS E-VRPTW",),
    "pyga_checked": ("py-ga-VRPTW custom + shared checker",),
    "routefinder_repair": (
        "RouteFinder RF-Transformer + fleet compaction + EVRP-TW repair",
        "RouteFinder RF-Transformer + EVRP-TW repair",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recheck one solver result against the original EVRP-TW instance."
    )
    parser.add_argument("--schneider", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-instance", required=True)
    parser.add_argument("--expected-clients", type=int, required=True)
    parser.add_argument("--expected-stations", type=int, required=True)
    parser.add_argument("--expected-vehicles", type=int, required=True)
    parser.add_argument("--expected-seed", type=int, required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--job-id", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize_routes(data: dict) -> tuple[list[list[str]], list[list[dict]] | None]:
    entries = data.get("routes")
    if not isinstance(entries, list):
        raise ValueError("result.routes must be a list")

    routes: list[list[str]] = []
    charging_plans: list[list[dict]] = []
    has_explicit_charging_plan = False
    for index, entry in enumerate(entries, start=1):
        if isinstance(entry, list):
            visits = entry
            charging_plan = None
        elif isinstance(entry, dict):
            visits = entry.get("visits")
            charging_plan = entry.get("charging_plan")
        else:
            raise ValueError(f"routes[{index}] must be a list or object")
        if not isinstance(visits, list) or not all(
            isinstance(name, str) for name in visits
        ):
            raise ValueError(f"routes[{index}].visits must be a list of strings")
        routes.append(list(visits))
        if charging_plan is not None:
            if not isinstance(charging_plan, list):
                raise ValueError(
                    f"routes[{index}].charging_plan must be a list when present"
                )
            has_explicit_charging_plan = True
            charging_plans.append(charging_plan)
        else:
            charging_plans.append([])

    return routes, charging_plans if has_explicit_charging_plan else None


def value_at(mapping: dict, *keys, default=None):
    current = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def values_equal(saved, fresh) -> bool:
    """Compare persisted checker values without rejecting harmless float noise."""
    if isinstance(saved, bool) or isinstance(fresh, bool):
        return saved == fresh
    if isinstance(saved, (int, float)) and isinstance(fresh, (int, float)):
        return math.isclose(float(saved), float(fresh), rel_tol=1e-9, abs_tol=1e-6)
    return saved == fresh


def is_json_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def classify_failure(report, contract_errors: list[str], data: dict) -> str:
    if contract_errors:
        return "contract_mismatch"
    if report.feasible and data.get("status") != "solved":
        return "solver_unsolved_checker_feasible"
    if report.feasible:
        return "success"
    if report.missing_customers:
        return "checker_infeasible:coverage_missing"
    if report.duplicate_customers:
        return "checker_infeasible:duplicate"
    if report.vehicle_limit_violations:
        return "checker_infeasible:fleet"
    if report.energy_violations:
        return "checker_infeasible:energy_or_charging"
    if report.time_window_violations:
        return "checker_infeasible:time_window"
    if report.capacity_violations:
        return "checker_infeasible:capacity"
    if report.synchronization_violations:
        return "checker_infeasible:synchronization"
    return "checker_infeasible:route_structure_or_other"


def validate(args: argparse.Namespace) -> dict:
    if args.method not in EXPECTED_METHOD_NAMES:
        raise ValueError(f"unsupported method identity: {args.method}")
    instance_data = convert_schneider_instance(
        input_path=args.schneider,
        num_vehicles=args.expected_vehicles,
        solver_runtime_seconds=0,
        solver_seed=args.expected_seed,
        solver_display=False,
    )
    instance = load_instance_data(instance_data, default_name=args.expected_instance)
    data = json.loads(args.result.read_text(encoding="utf-8"))
    routes, charging_plans = normalize_routes(data)
    report = check_explicit_routes(
        routes=routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
        charging_plans=charging_plans,
    )

    errors: list[str] = []
    if instance.name != args.expected_instance:
        errors.append(f"loaded_instance={instance.name}")
    if len(instance.clients) != args.expected_clients:
        errors.append(f"loaded_clients={len(instance.clients)}")
    if len(instance.charging_stations) != args.expected_stations:
        errors.append(f"loaded_stations={len(instance.charging_stations)}")
    if instance.num_vehicles != args.expected_vehicles:
        errors.append(f"loaded_max_vehicles={instance.num_vehicles}")
    if value_at(data, "source", "instance") != args.expected_instance:
        errors.append(
            f"result_instance={value_at(data, 'source', 'instance', default='missing')}"
        )
    record_clients = value_at(data, "experiment_record", "instance_size")
    if not is_json_int(record_clients) or record_clients != args.expected_clients:
        errors.append(f"result_clients={record_clients}")
    result_seed = value_at(data, "solver", "seed")
    if result_seed is None:
        result_seed = value_at(data, "experiment_record", "random_seed")
    if not is_json_int(result_seed) or result_seed != args.expected_seed:
        errors.append(f"result_seed={result_seed}")
    expected_method_names = EXPECTED_METHOD_NAMES[args.method]
    result_method_name = value_at(data, "experiment_record", "method_name")
    if result_method_name not in expected_method_names:
        errors.append(
            f"result_method_name={result_method_name!r},"
            f"expected_one_of={expected_method_names!r}"
        )

    metrics_value = data.get("metrics")
    saved_report_value = data.get("report")
    metrics = metrics_value if isinstance(metrics_value, dict) else {}
    saved_report = saved_report_value if isinstance(saved_report_value, dict) else {}
    if not isinstance(metrics_value, dict):
        errors.append("result.metrics must be an object")
    if not isinstance(saved_report_value, dict):
        errors.append("result.report must be an object")
    common_metric_fields = {
        "feasible",
        "vehicle_count",
        "total_distance",
        "total_duration",
        "makespan",
        "served_customers",
        "missing_customers",
        "duplicate_customers",
        "time_window_violations",
        "capacity_violations",
        "energy_violations",
        "charging_count",
        "charging_time",
    }
    missing_metric_fields = sorted(common_metric_fields - metrics.keys())
    if missing_metric_fields:
        errors.append(
            "metrics missing fields: " + ", ".join(missing_metric_fields)
        )
    common_report_fields = {
        "feasible",
        "total_distance",
        "total_duration",
        "makespan",
        "served_customers",
        "missing_customers",
        "duplicate_customers",
        "time_window_violations",
        "capacity_violations",
        "energy_violations",
        "charging_count",
        "charging_time",
        "synchronization_violations",
        "route_metrics",
        "violations",
    }
    missing_report_fields = sorted(common_report_fields - saved_report.keys())
    if missing_report_fields:
        errors.append(
            "report missing fields: " + ", ".join(missing_report_fields)
        )
    if not isinstance(metrics.get("feasible"), bool):
        errors.append("metrics.feasible must be a JSON boolean")
    if not isinstance(saved_report.get("feasible"), bool):
        errors.append("report.feasible must be a JSON boolean")
    metric_comparisons = {
        "served_customers": report.served_customers,
        "missing_customers": len(report.missing_customers),
        "duplicate_customers": len(report.duplicate_customers),
        "time_window_violations": report.time_window_violations,
        "capacity_violations": report.capacity_violations,
        "energy_violations": report.energy_violations,
        "vehicle_limit_violations": report.vehicle_limit_violations,
        "total_distance": report.total_distance,
        "total_duration": report.total_duration,
        "makespan": report.makespan,
        "charging_count": report.charging_count,
        "charging_time": report.charging_time,
    }
    for field, fresh_value in metric_comparisons.items():
        saved_value = metrics.get(field)
        if saved_value is not None and not values_equal(saved_value, fresh_value):
            errors.append(f"metrics.{field}={saved_value},fresh={fresh_value}")

    report_comparisons = {
        "served_customers": report.served_customers,
        "missing_customers": report.missing_customers,
        "duplicate_customers": report.duplicate_customers,
        "time_window_violations": report.time_window_violations,
        "capacity_violations": report.capacity_violations,
        "energy_violations": report.energy_violations,
        "vehicle_limit_violations": report.vehicle_limit_violations,
        "total_distance": report.total_distance,
        "total_duration": report.total_duration,
        "makespan": report.makespan,
        "charging_count": report.charging_count,
        "charging_time": report.charging_time,
        "synchronization_violations": report.synchronization_violations,
    }
    for field, fresh_value in report_comparisons.items():
        saved_report_value = saved_report.get(field)
        if saved_report_value is not None and not values_equal(
            saved_report_value, fresh_value
        ):
            errors.append(
                f"report.{field}={saved_report_value},fresh={fresh_value}"
            )
    if metrics.get("vehicle_count") is not None and metrics.get(
        "vehicle_count"
    ) != len(routes):
        errors.append(
            f"metrics.vehicle_count={metrics.get('vehicle_count')},routes={len(routes)}"
        )
    saved_feasible = (
        metrics["feasible"] if isinstance(metrics.get("feasible"), bool) else False
    )
    if saved_feasible != bool(report.feasible):
        errors.append(
            f"metrics.feasible={saved_feasible},fresh={bool(report.feasible)}"
        )
    if saved_report and bool(saved_report.get("feasible")) != bool(report.feasible):
        errors.append(
            "saved report feasible does not match fresh checker feasible"
        )

    repair = data.get("repair")
    if (
        isinstance(repair, dict)
        and "feasible" in repair
        and not isinstance(repair["feasible"], bool)
    ):
        errors.append("repair.feasible must be a JSON boolean")
    repair_consistent = (
        not isinstance(repair, dict)
        or "feasible" not in repair
        or (
            isinstance(repair["feasible"], bool)
            and repair["feasible"] == bool(report.feasible)
        )
    )
    if not repair_consistent:
        errors.append("repair.feasible does not match fresh checker feasible")

    strict_feasible = bool(
        not errors
        and data.get("status") == "solved"
        and saved_feasible
        and report.feasible
        and report.served_customers == args.expected_clients
        and len(routes) <= args.expected_vehicles
    )
    return {
        "schema_version": 1,
        "fresh_recheck": True,
        "job_id": args.job_id,
        "group": args.group,
        "method": args.method,
        "instance": args.expected_instance,
        "clients": args.expected_clients,
        "stations": args.expected_stations,
        "max_vehicles": args.expected_vehicles,
        "seed": args.expected_seed,
        "validation_status": "valid" if not errors else "invalid",
        "contract_valid": not errors,
        "strict_feasible": strict_feasible,
        "failure_class": classify_failure(report, errors, data),
        "contract_errors": errors,
        "report": asdict(report),
        "route_count": len(routes),
        "result_status": data.get("status"),
        "result_method_name": result_method_name,
        "expected_method_names": list(expected_method_names),
        "result_metrics_feasible": saved_feasible,
        "hashes": {
            "instance_sha256": sha256(args.schneider),
            "result_sha256": sha256(args.result),
            "checker_sha256": sha256(CHECKER_PATH),
            "fleet_policy_sha256": sha256(FLEET_POLICY_PATH),
            "instance_loader_sha256": sha256(INSTANCE_LOADER_PATH),
            "converter_sha256": sha256(CONVERTER_PATH),
            "validator_sha256": sha256(VALIDATOR_PATH),
        },
    }


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = validate(args)
    except Exception as error:  # The batch must preserve validator failures.
        payload = {
            "schema_version": 1,
            "fresh_recheck": True,
            "job_id": args.job_id,
            "group": args.group,
            "method": args.method,
            "instance": args.expected_instance,
            "clients": args.expected_clients,
            "stations": args.expected_stations,
            "max_vehicles": args.expected_vehicles,
            "seed": args.expected_seed,
            "validation_status": "error",
            "contract_valid": False,
            "strict_feasible": False,
            "failure_class": (
                "missing_output"
                if not args.result.exists()
                else "invalid_json_or_validator_error"
            ),
            "contract_errors": [f"{type(error).__name__}: {error}"],
            "traceback": traceback.format_exc(),
        }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"{args.job_id}: validation={payload['validation_status']} "
        f"strict_feasible={payload['strict_feasible']} "
        f"failure={payload['failure_class']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
