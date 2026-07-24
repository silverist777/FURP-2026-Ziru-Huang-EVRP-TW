"""Summarize the three-group Week 5 EVRP-TW stability benchmark.

The runner is expected to create one directory per manifest job::

    RAW/runs/<group>/<clients>/<instance>/<method>/seed-0001/

Each job directory contains ``result.json``, ``runner.json``, and
``checker.json``.  Solver-reported feasibility in ``result.json`` is never
used.  A run is counted as feasible only when the independent fresh checker
contract is valid and ``checker.json`` reports ``strict_feasible: true``.
"""

from __future__ import annotations

import argparse
import csv
from functools import lru_cache
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_SIZES = (5, 10, 15, 100)
EXPECTED_GROUPS = ("C", "R", "RC")
REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
SOURCE_HASH_PATHS = {
    "checker_sha256": EXPERIMENTS_ROOT / "checkers" / "feasibility_checker.py",
    "fleet_policy_sha256": EXPERIMENTS_ROOT / "core" / "evrptw_fleet_policy.py",
    "instance_loader_sha256": EXPERIMENTS_ROOT / "core" / "instance_loader.py",
    "converter_sha256": (
        EXPERIMENTS_ROOT
        / "methods"
        / "pyvrp"
        / "parse_schneider_instance.py"
    ),
    "validator_sha256": (
        EXPERIMENTS_ROOT / "tools" / "validate_stability_result.py"
    ),
}
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
RUNNER_REQUIRED_FIELDS = (
    "completed",
    "job_id",
    "group",
    "size",
    "instance",
    "method",
    "seed",
    "started_at",
    "ended_at",
    "wall_runtime_seconds",
    "exit_code",
    "timed_out",
    "command",
    "protocol_fingerprint",
    "result_path",
    "stdout_path",
    "stderr_path",
)
CHECKER_REQUIRED_FIELDS = (
    "schema_version",
    "fresh_recheck",
    "job_id",
    "group",
    "method",
    "instance",
    "clients",
    "stations",
    "max_vehicles",
    "seed",
    "strict_feasible",
    "contract_valid",
    "failure_class",
    "hashes",
)

RUN_FIELDS = [
    "expected_job_id",
    "runner_job_id",
    "group",
    "family",
    "size",
    "instance",
    "stations",
    "max_vehicles",
    "instance_path",
    "method",
    "method_label",
    "seed",
    "job_dir",
    "runner_path",
    "result_path",
    "checker_path",
    "job_dir_present",
    "runner_present",
    "result_present",
    "checker_present",
    "runner_valid",
    "result_valid",
    "checker_valid",
    "checker_fresh",
    "checker_contract_valid",
    "checker_strict_feasible",
    "strict_feasible",
    "run_status",
    "completed",
    "protocol_fingerprint",
    "exit_code",
    "timed_out",
    "wall_runtime_seconds",
    "distance",
    "distance_source",
    "result_status",
    "failure_class",
    "failure_stage",
    "failure_detail",
    "checker_failure_class",
    "metric_warning",
]

CELL_FIELDS = [
    "method",
    "method_label",
    "size",
    "expected_runs",
    "observed_runner_files",
    "strict_feasible_runs",
    "feasible_rate",
    "wilson95_low",
    "wilson95_high",
    "distance_n",
    "distance_mean",
    "distance_sample_sd",
    "runtime_n",
    "runtime_mean",
    "runtime_sample_sd",
]

FAILURE_FIELDS = [
    "expected_job_id",
    "group",
    "size",
    "instance",
    "method",
    "seed",
    "run_status",
    "failure_class",
    "failure_stage",
    "failure_detail",
    "checker_failure_class",
    "exit_code",
    "timed_out",
    "wall_runtime_seconds",
    "job_dir",
]


class ManifestError(ValueError):
    """Raised when the experiment manifest is not internally consistent."""


@dataclass(frozen=True)
class ExpectedJob:
    group: str
    family: str
    instance: str
    clients: int
    stations: int
    max_vehicles: int
    instance_path: Path
    method: str
    method_label: str
    seed: int
    job_dir: Path

    @property
    def expected_job_id(self) -> str:
        return (
            f"{self.group}-{self.instance}-{self.method}-"
            f"seed-{self.seed:04d}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize manifest-expected three-group EVRP-TW runs using only "
            "fresh checker.json records for strict feasibility."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Three-group experiment manifest JSON.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Raw experiment root containing runs/<group>/<size>/... job folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory that will receive runs.csv, cells.csv, failures.csv, summary.json, and summary.md.",
    )
    return parser.parse_args()


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return None, f"top-level JSON value is {type(value).__name__}, expected object"
    return value, None


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{field} must be an integer")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    data, error = read_json_object(path)
    if error is not None or data is None:
        raise ManifestError(f"cannot read manifest {path}: {error}")

    seed = _integer(data.get("seed"), "seed")
    if seed <= 0:
        raise ManifestError("seed must be positive")

    methods = data.get("methods")
    if not isinstance(methods, list) or len(methods) != 5:
        raise ManifestError("methods must contain exactly five method objects")
    method_ids: list[str] = []
    for index, method in enumerate(methods):
        if not isinstance(method, dict):
            raise ManifestError(f"methods[{index}] must be an object")
        method_id = method.get("id")
        if not isinstance(method_id, str) or not method_id.strip():
            raise ManifestError(f"methods[{index}].id must be a non-empty string")
        method_ids.append(method_id)
    if len(set(method_ids)) != len(method_ids):
        raise ManifestError("method IDs must be unique")

    groups = data.get("groups")
    if not isinstance(groups, list) or len(groups) != 3:
        raise ManifestError("groups must contain exactly three group objects")
    group_ids = [group.get("id") for group in groups if isinstance(group, dict)]
    if tuple(group_ids) != EXPECTED_GROUPS:
        raise ManifestError(
            f"groups must be ordered as {list(EXPECTED_GROUPS)}, got {group_ids}"
        )

    seen_instances: set[str] = set()
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ManifestError(f"groups[{group_index}] must be an object")
        group_id = group["id"]
        family = group.get("family")
        if not isinstance(family, str) or not family.strip():
            raise ManifestError(f"group {group_id} must have a non-empty family")
        cases = group.get("cases")
        if not isinstance(cases, list) or len(cases) != len(EXPECTED_SIZES):
            raise ManifestError(
                f"group {group_id} must contain exactly four cases"
            )
        sizes: list[int] = []
        for case_index, case in enumerate(cases):
            prefix = f"groups[{group_index}].cases[{case_index}]"
            if not isinstance(case, dict):
                raise ManifestError(f"{prefix} must be an object")
            instance = case.get("instance")
            if not isinstance(instance, str) or not instance.strip():
                raise ManifestError(f"{prefix}.instance must be a non-empty string")
            instance_path = case.get("path")
            if not isinstance(instance_path, str) or not instance_path.strip():
                raise ManifestError(f"{prefix}.path must be a non-empty string")
            if instance in seen_instances:
                raise ManifestError(f"instance {instance!r} appears more than once")
            seen_instances.add(instance)
            clients = _integer(case.get("clients"), f"{prefix}.clients")
            stations = _integer(case.get("stations"), f"{prefix}.stations")
            max_vehicles = _integer(
                case.get("max_vehicles"), f"{prefix}.max_vehicles"
            )
            expected_limit = max(1, math.ceil((clients + stations) / 4))
            if max_vehicles != expected_limit:
                raise ManifestError(
                    f"{prefix}.max_vehicles={max_vehicles}, expected {expected_limit} "
                    "from ceil((clients + stations) / 4)"
                )
            sizes.append(clients)
        if tuple(sizes) != EXPECTED_SIZES:
            raise ManifestError(
                f"group {group_id} cases must be ordered as {list(EXPECTED_SIZES)}, "
                f"got {sizes}"
            )

    declared_sizes = data.get("sizes")
    if declared_sizes is not None and tuple(declared_sizes) != EXPECTED_SIZES:
        raise ManifestError(
            f"sizes must be {list(EXPECTED_SIZES)}, got {declared_sizes}"
        )
    return data


def build_expected_jobs(
    manifest: dict[str, Any], raw_dir: Path
) -> list[ExpectedJob]:
    seed = manifest["seed"]
    jobs: list[ExpectedJob] = []
    for group in manifest["groups"]:
        for case in group["cases"]:
            instance_path = Path(case["path"])
            if not instance_path.is_absolute():
                instance_path = REPO_ROOT / instance_path
            instance_path = instance_path.resolve()
            for method in manifest["methods"]:
                method_id = method["id"]
                jobs.append(
                    ExpectedJob(
                        group=group["id"],
                        family=group["family"],
                        instance=case["instance"],
                        clients=case["clients"],
                        stations=case["stations"],
                        max_vehicles=case["max_vehicles"],
                        instance_path=instance_path,
                        method=method_id,
                        method_label=method.get("label", method_id),
                        seed=seed,
                        job_dir=(
                            raw_dir
                            / "runs"
                            / group["id"]
                            / str(case["clients"])
                            / case["instance"]
                            / method_id
                            / f"seed-{seed:04d}"
                        ),
                    )
                )
    return jobs


def finite_number(value: Any, *, nonnegative: bool = True) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if nonnegative and number < 0:
        return None
    return number


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def validate_runner(
    data: dict[str, Any], job: ExpectedJob
) -> tuple[
    list[str],
    float | None,
    int | None,
    bool | None,
    bool | None,
    str,
]:
    errors = [field for field in RUNNER_REQUIRED_FIELDS if field not in data]
    details = [f"missing fields: {', '.join(errors)}"] if errors else []

    expected_metadata = {
        "group": job.group,
        "size": job.clients,
        "instance": job.instance,
        "method": job.method,
        "seed": job.seed,
    }
    for field, expected in expected_metadata.items():
        actual = data.get(field)
        if field in {"size", "seed"}:
            if isinstance(actual, bool) or not isinstance(actual, int):
                details.append(f"{field}={actual!r} is not an integer")
                continue
        if actual != expected:
            details.append(f"{field}={actual!r}, expected {expected!r}")

    job_id = data.get("job_id")
    if job_id != job.expected_job_id:
        details.append(
            f"job_id={job_id!r}, expected {job.expected_job_id!r}"
        )

    completed = data.get("completed")
    if not isinstance(completed, bool):
        details.append("completed is not boolean")
        completed = None
    elif completed is not True:
        details.append("completed is not true")

    protocol_fingerprint = data.get("protocol_fingerprint")
    if not isinstance(protocol_fingerprint, str) or not SHA256_PATTERN.fullmatch(
        protocol_fingerprint
    ):
        details.append("protocol_fingerprint is not a 64-character hexadecimal digest")
        protocol_fingerprint = ""

    runtime = finite_number(data.get("wall_runtime_seconds"))
    if runtime is None:
        details.append("wall_runtime_seconds is not a finite non-negative number")

    timed_out = data.get("timed_out")
    if not isinstance(timed_out, bool):
        details.append("timed_out is not boolean")
        timed_out = None

    exit_code = data.get("exit_code")
    if exit_code is not None and (
        isinstance(exit_code, bool) or not isinstance(exit_code, int)
    ):
        details.append("exit_code is neither an integer nor null")
        exit_code = None
    if timed_out is False and exit_code is None:
        details.append("non-timeout runner record has null exit_code")

    return (
        details,
        runtime,
        exit_code,
        timed_out,
        completed,
        protocol_fingerprint,
    )


@lru_cache(maxsize=None)
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_checker(
    data: dict[str, Any], checker_path: Path, result_path: Path, job: ExpectedJob
) -> tuple[list[str], bool, bool | None, bool | None, str, dict[str, Any] | None]:
    errors: list[str] = []
    missing = [field for field in CHECKER_REQUIRED_FIELDS if field not in data]
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")

    schema_version = data.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        errors.append(f"schema_version={schema_version!r}, expected 1")

    if data.get("fresh_recheck") is not True:
        errors.append("fresh_recheck is not true")

    strict_feasible = data.get("strict_feasible")
    if not isinstance(strict_feasible, bool):
        errors.append("strict_feasible is not boolean")
        strict_feasible = None

    contract_valid = data.get("contract_valid")
    if not isinstance(contract_valid, bool):
        errors.append("contract_valid is not boolean")
        contract_valid = None

    failure_class = data.get("failure_class")
    if failure_class is not None and not isinstance(failure_class, str):
        errors.append("failure_class is neither a string nor null")
        failure_class = ""
    failure_class = failure_class or ""

    # The fresh validator originally emitted fresh_report and later revisions
    # may use report.  Prefer the explicitly fresh name when both are present.
    report_key = "fresh_report" if "fresh_report" in data else "report"
    report = data.get(report_key)
    if not isinstance(report, dict):
        errors.append(f"{report_key} is not an object")
        report = None

    checker_metadata = {
        "job_id": job.expected_job_id,
        "group": job.group,
        "method": job.method,
        "instance": job.instance,
        "clients": job.clients,
        "stations": job.stations,
        "max_vehicles": job.max_vehicles,
        "seed": job.seed,
    }
    for field, expected in checker_metadata.items():
        actual = data.get(field)
        type_mismatch = (
            isinstance(expected, int)
            and (isinstance(actual, bool) or not isinstance(actual, int))
        )
        if type_mismatch or actual != expected:
            errors.append(
                f"checker {field}={actual!r}, expected {expected!r}"
            )

    try:
        if checker_path.stat().st_mtime_ns < result_path.stat().st_mtime_ns:
            errors.append("checker.json is older than result.json")
    except OSError as exc:
        errors.append(f"cannot compare checker/result timestamps: {exc}")

    hashes = data.get("hashes")
    if not isinstance(hashes, dict):
        errors.append("hashes is not an object")
    else:
        required_hash_paths = {
            "result_sha256": result_path,
            "instance_sha256": job.instance_path,
            **SOURCE_HASH_PATHS,
        }
        for hash_name, bound_path in required_hash_paths.items():
            declared_hash = hashes.get(hash_name)
            if not isinstance(declared_hash, str) or not SHA256_PATTERN.fullmatch(
                declared_hash
            ):
                errors.append(
                    f"hashes.{hash_name} is missing or not a 64-character "
                    "hexadecimal digest"
                )
                continue
            try:
                actual_hash = sha256_file(bound_path)
            except OSError as exc:
                errors.append(f"cannot hash {bound_path}: {exc}")
                continue
            if declared_hash.lower() != actual_hash.lower():
                errors.append(
                    f"hashes.{hash_name} does not match {bound_path}"
                )

    fresh = not errors
    return errors, fresh, contract_valid, strict_feasible, failure_class, report


def distance_from_records(
    checker_data: dict[str, Any],
    result_data: dict[str, Any],
) -> tuple[float | None, str]:
    candidates = [
        (
            nested(checker_data, "fresh_report", "total_distance"),
            "checker.fresh_report.total_distance",
        ),
        (
            nested(checker_data, "fresh_report", "distance"),
            "checker.fresh_report.distance",
        ),
        (
            nested(checker_data, "fresh_report", "metrics", "total_distance"),
            "checker.fresh_report.metrics.total_distance",
        ),
        (nested(checker_data, "report", "total_distance"), "checker.report.total_distance"),
        (nested(checker_data, "report", "distance"), "checker.report.distance"),
        (
            nested(checker_data, "report", "metrics", "total_distance"),
            "checker.report.metrics.total_distance",
        ),
        (nested(checker_data, "metrics", "total_distance"), "checker.metrics.total_distance"),
        (nested(result_data, "metrics", "total_distance"), "result.metrics.total_distance"),
        (nested(result_data, "report", "total_distance"), "result.report.total_distance"),
        (
            nested(result_data, "experiment_record", "objective_value"),
            "result.experiment_record.objective_value",
        ),
        (result_data.get("total_distance"), "result.total_distance"),
        (result_data.get("distance"), "result.distance"),
    ]
    for value, source in candidates:
        number = finite_number(value)
        if number is not None:
            return number, source
    return None, ""


def normalized_checker_failure(value: str) -> str:
    lowered = value.strip().lower()
    if "timeout" in lowered:
        return "timeout"
    if "nonzero" in lowered or "exit" in lowered:
        return "nonzero"
    if "missing" in lowered or "not_found" in lowered or "not found" in lowered:
        return "missing"
    if any(
        token in lowered
        for token in ("invalid", "malformed", "contract", "schema", "stale", "parse")
    ):
        return "invalid"
    return "infeasible"


def collect_job(job: ExpectedJob) -> dict[str, Any]:
    runner_path = job.job_dir / "runner.json"
    result_path = job.job_dir / "result.json"
    checker_path = job.job_dir / "checker.json"

    row: dict[str, Any] = {
        "expected_job_id": job.expected_job_id,
        "runner_job_id": "",
        "group": job.group,
        "family": job.family,
        "size": job.clients,
        "instance": job.instance,
        "stations": job.stations,
        "max_vehicles": job.max_vehicles,
        "method": job.method,
        "method_label": job.method_label,
        "seed": job.seed,
        "job_dir": str(job.job_dir),
        "runner_path": str(runner_path),
        "result_path": str(result_path),
        "checker_path": str(checker_path),
        "job_dir_present": job.job_dir.is_dir(),
        "runner_present": runner_path.is_file(),
        "result_present": result_path.is_file(),
        "checker_present": checker_path.is_file(),
        "runner_valid": False,
        "result_valid": False,
        "checker_valid": False,
        "checker_fresh": False,
        "checker_contract_valid": "",
        "checker_strict_feasible": "",
        "strict_feasible": False,
        "run_status": "failed",
        "completed": "",
        "protocol_fingerprint": "",
        "exit_code": "",
        "timed_out": "",
        "wall_runtime_seconds": "",
        "distance": "",
        "distance_source": "",
        "result_status": "",
        "failure_class": "",
        "failure_stage": "",
        "failure_detail": "",
        "checker_failure_class": "",
        "metric_warning": "",
    }

    runner_data: dict[str, Any] | None = None
    runner_error: str | None = None
    runner_contract_errors: list[str] = []
    runtime: float | None = None
    exit_code: int | None = None
    timed_out: bool | None = None
    completed: bool | None = None
    protocol_fingerprint = ""
    if row["runner_present"]:
        runner_data, runner_error = read_json_object(runner_path)
        if runner_data is not None:
            row["runner_job_id"] = runner_data.get("job_id", "")
            (
                runner_contract_errors,
                runtime,
                exit_code,
                timed_out,
                completed,
                protocol_fingerprint,
            ) = validate_runner(runner_data, job)
            row["runner_valid"] = not runner_contract_errors
            row["exit_code"] = "" if exit_code is None else exit_code
            row["timed_out"] = "" if timed_out is None else timed_out
            row["completed"] = "" if completed is None else completed
            row["protocol_fingerprint"] = protocol_fingerprint
            if row["runner_valid"] and runtime is not None:
                row["wall_runtime_seconds"] = runtime

    result_data: dict[str, Any] | None = None
    result_error: str | None = None
    if row["result_present"]:
        result_data, result_error = read_json_object(result_path)
        if result_data is not None and result_data:
            row["result_valid"] = True
            status = result_data.get("status")
            if status is not None:
                row["result_status"] = str(status)

    checker_data: dict[str, Any] | None = None
    checker_error: str | None = None
    checker_contract_errors: list[str] = []
    checker_contract_valid: bool | None = None
    checker_strict_feasible: bool | None = None
    checker_failure_class = ""
    checker_report: dict[str, Any] | None = None
    if row["checker_present"]:
        checker_data, checker_error = read_json_object(checker_path)
        if checker_data is not None and row["result_present"]:
            (
                checker_contract_errors,
                checker_fresh,
                checker_contract_valid,
                checker_strict_feasible,
                checker_failure_class,
                checker_report,
            ) = validate_checker(checker_data, checker_path, result_path, job)
            row["checker_fresh"] = checker_fresh
            row["checker_valid"] = not checker_contract_errors
            row["checker_contract_valid"] = (
                "" if checker_contract_valid is None else checker_contract_valid
            )
            row["checker_strict_feasible"] = (
                "" if checker_strict_feasible is None else checker_strict_feasible
            )
            row["checker_failure_class"] = checker_failure_class

    failure: tuple[str, str, str] | None = None
    if not row["job_dir_present"]:
        failure = ("missing", "job", "expected job directory is missing")
    elif not row["runner_present"]:
        failure = ("missing", "runner", "runner.json is missing")
    elif runner_error is not None:
        failure = ("invalid", "runner", runner_error)
    elif runner_contract_errors:
        failure = ("invalid", "runner", "; ".join(runner_contract_errors))
    elif timed_out is True:
        failure = ("timeout", "runner", "runner reported timed_out=true")
    elif exit_code != 0:
        failure = ("nonzero", "runner", f"runner exit_code={exit_code}")
    elif not row["result_present"]:
        failure = ("missing", "result", "result.json is missing")
    elif result_error is not None:
        failure = ("invalid", "result", result_error)
    elif not row["result_valid"]:
        failure = ("invalid", "result", "result.json is an empty object")
    elif not row["checker_present"]:
        failure = ("missing", "checker", "checker.json is missing")
    elif checker_error is not None:
        failure = ("invalid", "checker", checker_error)
    elif checker_contract_errors:
        failure = ("invalid", "checker", "; ".join(checker_contract_errors))
    elif not row["checker_fresh"]:
        failure = ("invalid", "checker", "checker record is not fresh")
    elif checker_contract_valid is not True:
        detail = checker_failure_class or "checker contract_valid is not true"
        failure = ("invalid", "checker_contract", detail)
    elif checker_strict_feasible is not True:
        failure = (
            normalized_checker_failure(checker_failure_class),
            "checker",
            checker_failure_class or "strict checker rejected the solution",
        )

    if failure is None:
        row["strict_feasible"] = True
        row["run_status"] = "feasible"
        assert checker_data is not None
        assert result_data is not None
        distance, source = distance_from_records(checker_data, result_data)
        if distance is None:
            row["metric_warning"] = "strict-feasible run has no numeric distance"
        else:
            row["distance"] = distance
            row["distance_source"] = source
    else:
        row["failure_class"], row["failure_stage"], row["failure_detail"] = failure

    # This local variable documents that the checker report is deliberately not
    # reinterpreted here: strict_feasible is the canonical fresh-validator bit.
    _ = checker_report
    return row


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def metric_stats(values: Iterable[float]) -> tuple[int, float | None, float | None]:
    collected = list(values)
    if not collected:
        return 0, None, None
    mean = statistics.fmean(collected)
    sample_sd = statistics.stdev(collected) if len(collected) >= 2 else None
    return len(collected), mean, sample_sd


def rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def build_cells(
    rows: list[dict[str, Any]], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for method in manifest["methods"]:
        method_id = method["id"]
        for size in EXPECTED_SIZES:
            selected = [
                row
                for row in rows
                if row["method"] == method_id and row["size"] == size
            ]
            feasible = sum(bool(row["strict_feasible"]) for row in selected)
            total = len(selected)
            wilson_low, wilson_high = wilson_interval(feasible, total)
            distance_n, distance_mean, distance_sd = metric_stats(
                float(row["distance"])
                for row in selected
                if row["strict_feasible"] and row["distance"] != ""
            )
            runtime_n, runtime_mean, runtime_sd = metric_stats(
                float(row["wall_runtime_seconds"])
                for row in selected
                if row["wall_runtime_seconds"] != ""
            )
            cells.append(
                {
                    "method": method_id,
                    "method_label": method.get("label", method_id),
                    "size": size,
                    "expected_runs": total,
                    "observed_runner_files": sum(
                        bool(row["runner_present"]) for row in selected
                    ),
                    "strict_feasible_runs": feasible,
                    "feasible_rate": rounded(feasible / total if total else 0.0),
                    "wilson95_low": rounded(wilson_low),
                    "wilson95_high": rounded(wilson_high),
                    "distance_n": distance_n,
                    "distance_mean": rounded(distance_mean),
                    "distance_sample_sd": rounded(distance_sd),
                    "runtime_n": runtime_n,
                    "runtime_mean": rounded(runtime_mean),
                    "runtime_sample_sd": rounded(runtime_sd),
                }
            )
    return cells


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fields})


def json_ready_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items()}


def discover_unexpected_job_dirs(raw_dir: Path, expected: set[Path]) -> list[str]:
    discovered: set[Path] = set()
    runs_dir = raw_dir / "runs"
    if runs_dir.is_dir():
        for artifact in ("runner.json", "result.json", "checker.json"):
            discovered.update(path.parent.resolve() for path in runs_dir.rglob(artifact))
    return sorted(str(path) for path in discovered - expected)


def markdown_escape(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def mean_sd(mean: float | None, sample_sd: float | None) -> str:
    if mean is None:
        return "—"
    if sample_sd is None:
        return f"{mean:.3f} / SD —"
    return f"{mean:.3f} ± {sample_sd:.3f}"


def write_markdown(
    path: Path,
    summary: dict[str, Any],
    failures: list[dict[str, Any]],
) -> None:
    lines = [
        f"# {summary['title']}",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "## Coverage",
        "",
        f"- Expected jobs: **{summary['expected_jobs']}**",
        f"- Strict-feasible jobs: **{summary['strict_feasible_jobs']}**",
        f"- Failed or incomplete jobs: **{summary['failed_jobs']}**",
        f"- Unexpected job directories excluded from statistics: **{len(summary['unexpected_job_dirs'])}**",
        "",
        "Feasibility is accepted only from a fresh, contract-valid `checker.json` "
        "with `strict_feasible=true`; solver self-reports are ignored. Distance "
        "uses only those strict-feasible runs. Runner wall time includes every "
        "valid runner record, including failed attempts. Sample SD is undefined "
        "when fewer than two values are available.",
        "",
        "Raw distance is never aggregated across different client sizes.",
        "",
        "## Method × size cells",
        "",
        "| method | clients | feasible | rate | Wilson 95% | distance n | distance mean ± sample SD | runtime n | wall runtime mean ± sample SD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in summary["cells"]:
        interval = (
            f"{percent(cell['wilson95_low'])}–{percent(cell['wilson95_high'])}"
        )
        lines.append(
            "| {method} | {size} | {feasible}/{expected} | {rate} | {interval} | "
            "{distance_n} | {distance_stats} | {runtime_n} | {runtime_stats} |".format(
                method=markdown_escape(cell["method"]),
                size=cell["size"],
                feasible=cell["strict_feasible_runs"],
                expected=cell["expected_runs"],
                rate=percent(cell["feasible_rate"]),
                interval=interval,
                distance_n=cell["distance_n"],
                distance_stats=mean_sd(
                    cell["distance_mean"], cell["distance_sample_sd"]
                ),
                runtime_n=cell["runtime_n"],
                runtime_stats=mean_sd(
                    cell["runtime_mean"], cell["runtime_sample_sd"]
                ),
            )
        )

    lines.extend(
        [
            "",
            "## Failure classes",
            "",
            "| class | count |",
            "|---|---:|",
        ]
    )
    if summary["failure_counts"]:
        for failure_class, count in summary["failure_counts"].items():
            lines.append(f"| {markdown_escape(failure_class)} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Failed or incomplete jobs",
            "",
        ]
    )
    if not failures:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| group | clients | instance | method | class | stage | detail |",
                "|---|---:|---|---|---|---|---|",
            ]
        )
        for row in failures:
            lines.append(
                "| {group} | {size} | {instance} | {method} | {failure_class} | "
                "{failure_stage} | {failure_detail} |".format(
                    **{key: markdown_escape(value) for key, value in row.items()}
                )
            )

    if summary["unexpected_job_dirs"]:
        lines.extend(["", "## Unexpected job directories", ""])
        lines.extend(f"- `{path_value}`" for path_value in summary["unexpected_job_dirs"])

    lines.extend(
        [
            "",
            "Machine-readable details: `runs.csv`, `cells.csv`, `failures.csv`, and `summary.json`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    raw_dir = args.raw_dir.resolve()
    output_dir = args.output_dir.resolve()

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        raise SystemExit(f"manifest error: {exc}") from exc

    if not raw_dir.is_dir():
        raise SystemExit(f"raw directory does not exist: {raw_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs = build_expected_jobs(manifest, raw_dir)
    rows = [collect_job(job) for job in jobs]
    cells = build_cells(rows, manifest)
    failures = [row for row in rows if not row["strict_feasible"]]
    expected_dirs = {job.job_dir.resolve() for job in jobs}
    unexpected_dirs = discover_unexpected_job_dirs(raw_dir, expected_dirs)

    failure_counts = Counter(row["failure_class"] for row in failures)
    summary = {
        "schema_version": 1,
        "experiment_id": manifest.get("experiment_id", ""),
        "title": manifest.get(
            "title", "Week 5 three-group EVRP-TW stability benchmark"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "raw_dir": str(raw_dir),
        "output_dir": str(output_dir),
        "seed": manifest["seed"],
        "groups": [group["id"] for group in manifest["groups"]],
        "sizes": list(EXPECTED_SIZES),
        "methods": [method["id"] for method in manifest["methods"]],
        "policy": {
            "strict_feasibility_source": "fresh checker.json strict_feasible with contract_valid=true",
            "solver_self_reported_feasibility_used": False,
            "distance_population": "strict-feasible runs only, separately by method and client size",
            "runtime_population": "all valid runner.json wall_runtime_seconds values in each method-size cell",
            "dispersion": "sample standard deviation (n-1 denominator)",
            "confidence_interval": "two-sided Wilson score interval, 95%",
            "cross_size_raw_distance_aggregation": False,
        },
        "expected_jobs": len(rows),
        "strict_feasible_jobs": sum(bool(row["strict_feasible"]) for row in rows),
        "failed_jobs": len(failures),
        "artifact_coverage": {
            "runner_files": sum(bool(row["runner_present"]) for row in rows),
            "result_files": sum(bool(row["result_present"]) for row in rows),
            "checker_files": sum(bool(row["checker_present"]) for row in rows),
            "fresh_checker_files": sum(bool(row["checker_fresh"]) for row in rows),
        },
        "failure_counts": dict(sorted(failure_counts.items())),
        "metric_warning_count": sum(bool(row["metric_warning"]) for row in rows),
        "unexpected_job_dirs": unexpected_dirs,
        "cells": [json_ready_row(cell) for cell in cells],
    }

    write_csv(output_dir / "runs.csv", rows, RUN_FIELDS)
    write_csv(output_dir / "cells.csv", cells, CELL_FIELDS)
    write_csv(output_dir / "failures.csv", failures, FAILURE_FIELDS)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_markdown(output_dir / "summary.md", summary, failures)

    print(f"expected jobs: {len(rows)}")
    print(f"strict feasible: {summary['strict_feasible_jobs']}")
    print(f"failed or incomplete: {len(failures)}")
    print(f"output directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
