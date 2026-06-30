"""Shared schema helpers for experiment run records.

The fields mirror the week03 reporting checklist: instance, method, objective,
runtime, feasibility, vehicles, violations, seed, best solution, gap, progress,
and search effort.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


RECORD_SCHEMA = "week03_experiment_record_v1"

CORE_RECORD_FIELDS = [
    "record_schema",
    "instance_name",
    "instance_size",
    "method_name",
    "objective_value",
    "runtime_seconds",
    "feasibility_status",
    "vehicles_used",
    "constraint_violations",
    "random_seed",
    "best_solution_found",
    "reference_value",
    "gap_to_reference_pct",
    "convergence_curve",
    "improvement_over_time",
    "iterations",
    "generations",
    "search_steps",
]


def gap_to_reference_pct(objective: float | None, reference: float | None) -> float | None:
    if objective is None or reference in (None, 0):
        return None
    return round((float(objective) - float(reference)) / float(reference) * 100.0, 3)


def format_constraint_violations(violations: Mapping[str, Any]) -> str:
    parts = []
    for name, value in violations.items():
        if _is_zeroish(value):
            continue
        parts.append(f"{name}={record_value(value)}")
    return "none" if not parts else "; ".join(parts)


def build_experiment_record(
    *,
    instance_name: str,
    instance_size: int,
    method_name: str,
    objective_value: float | None,
    runtime_seconds: float | None,
    feasibility_status: str,
    vehicles_used: int | None,
    constraint_violations: str,
    random_seed: int | None,
    best_solution_found: Any = None,
    reference_value: float | None = None,
    convergence_curve: Any = None,
    improvement_over_time: Any = None,
    iterations: int | None = None,
    generations: int | None = None,
    search_steps: int | None = None,
) -> dict[str, Any]:
    return {
        "record_schema": RECORD_SCHEMA,
        "instance_name": instance_name,
        "instance_size": instance_size,
        "method_name": method_name,
        "objective_value": _round_float(objective_value),
        "runtime_seconds": _round_float(runtime_seconds),
        "feasibility_status": feasibility_status,
        "vehicles_used": vehicles_used,
        "constraint_violations": constraint_violations,
        "random_seed": random_seed,
        "best_solution_found": record_value(best_solution_found),
        "reference_value": _round_float(reference_value),
        "gap_to_reference_pct": gap_to_reference_pct(objective_value, reference_value),
        "convergence_curve": record_value(convergence_curve),
        "improvement_over_time": record_value(improvement_over_time),
        "iterations": iterations,
        "generations": generations,
        "search_steps": search_steps,
    }


def record_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return _round_float(value)
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return json.dumps(value, ensure_ascii=False)
    return value


def _round_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def _is_zeroish(value: Any) -> bool:
    if value in (None, "", 0, 0.0, False):
        return True
    if isinstance(value, Mapping):
        return all(_is_zeroish(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return all(_is_zeroish(item) for item in value)
    return False
