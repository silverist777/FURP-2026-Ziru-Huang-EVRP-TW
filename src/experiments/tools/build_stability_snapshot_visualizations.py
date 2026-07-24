"""Build portable visualizations from a paused stability snapshot.

The snapshot is treated as immutable.  Job paths are reconstructed from the
snapshotted protocol manifest and ``raw/batch_index.json``; live absolute paths
stored in runner metadata and ``results/runs.csv`` are deliberately ignored.

Outputs:

* ``overview.png``
* ``best-route-petals.png``
* ``best-route-selection.csv``
* ``visualization-metadata.json``
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np


SCRIPT_VERSION = "1.0"
MANIFEST_RELATIVE_PATH = Path("protocol") / "week5_three_group_stability.json"
BATCH_INDEX_RELATIVE_PATH = Path("raw") / "batch_index.json"
HASH_MANIFEST_RELATIVE_PATH = Path("sha256sums.csv")

GROUP_ORDER = ("C", "R", "RC")
SIZE_ORDER = (5, 10, 15)

METHOD_COLORS = {
    "pyvrp_repair": "#3366CC",
    "vns_ts": "#109618",
    "pomo_repair": "#DC3912",
    "pyga_checked": "#FF9900",
    "routefinder_repair": "#990099",
}
METHOD_SHORT_LABELS = {
    "pyvrp_repair": "PyVRP",
    "vns_ts": "VNS/TS",
    "pomo_repair": "POMO",
    "pyga_checked": "py-ga",
    "routefinder_repair": "RouteFinder",
}
ROUTE_COLORS = list(plt.get_cmap("tab20").colors)
ROUTE_LINESTYLES = ("-", "--", "-.", ":")


@dataclass(frozen=True)
class Location:
    name: str
    kind: str
    x: float
    y: float


@dataclass(frozen=True)
class ExpectedJob:
    group: str
    family: str
    size: int
    instance: str
    max_vehicles: int
    method: str
    method_label: str
    method_order: int
    seed: int

    @property
    def job_id(self) -> str:
        return f"{self.group}-{self.instance}-{self.method}-seed-{self.seed:04d}"

    def directory(self, snapshot_dir: Path) -> Path:
        return (
            snapshot_dir
            / "raw"
            / "runs"
            / self.group
            / str(self.size)
            / self.instance
            / self.method
            / f"seed-{self.seed:04d}"
        )


@dataclass
class JobRecord:
    expected: ExpectedJob
    directory: Path
    runner_path: Path
    result_path: Path
    checker_path: Path
    runner: dict[str, Any] | None
    result: dict[str, Any] | None
    checker: dict[str, Any] | None
    completed: bool
    strict_feasible: bool
    wall_runtime_seconds: float | None
    distance: float | None
    vehicle_count: int | None
    timed_out: bool
    issues: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the 5/10/15-client overview and best-route petals from an "
            "immutable three-group stability snapshot."
        )
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        required=True,
        help="Paused snapshot containing protocol/, raw/, results/, and sha256sums.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="A separate directory for the four generated artifacts.",
    )
    return parser.parse_args()


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#555555",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.7,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
        }
    )


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        return read_json(path), None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, f"{path.name}: {type(exc).__name__}: {exc}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def require_snapshot_layout(snapshot_dir: Path, output_dir: Path) -> None:
    if not snapshot_dir.is_dir():
        raise FileNotFoundError(f"Snapshot directory does not exist: {snapshot_dir}")
    required = (
        snapshot_dir / MANIFEST_RELATIVE_PATH,
        snapshot_dir / BATCH_INDEX_RELATIVE_PATH,
        snapshot_dir / HASH_MANIFEST_RELATIVE_PATH,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Snapshot is missing required files: " + ", ".join(missing))

    snapshot_resolved = snapshot_dir.resolve()
    output_resolved = output_dir.resolve()
    if output_resolved == snapshot_resolved or is_relative_to(output_resolved, snapshot_resolved):
        raise ValueError(
            "--output-dir must be outside --snapshot-dir; the paused snapshot is immutable"
        )


def selected_values(batch: dict[str, Any], key: str) -> list[Any]:
    selections = batch.get("selections")
    if not isinstance(selections, dict) or not isinstance(selections.get(key), list):
        raise ValueError(f"batch_index.json is missing selections.{key}")
    return list(selections[key])


def build_expected_jobs(
    manifest: dict[str, Any], batch: dict[str, Any]
) -> tuple[list[ExpectedJob], dict[str, Any]]:
    selected_groups = [str(value) for value in selected_values(batch, "groups")]
    selected_sizes = [int(value) for value in selected_values(batch, "sizes")]
    selected_methods = [str(value) for value in selected_values(batch, "methods")]
    seed = int(batch.get("seed", manifest.get("seed", 1)))

    manifest_methods = manifest.get("methods")
    manifest_groups = manifest.get("groups")
    if not isinstance(manifest_methods, list) or not isinstance(manifest_groups, list):
        raise ValueError("Protocol manifest must contain methods[] and groups[]")

    methods: dict[str, tuple[str, int]] = {}
    for method_order, raw_method in enumerate(manifest_methods):
        if not isinstance(raw_method, dict) or "id" not in raw_method:
            raise ValueError("Invalid method entry in protocol manifest")
        method_id = str(raw_method["id"])
        methods[method_id] = (str(raw_method.get("label", method_id)), method_order)

    unknown_methods = sorted(set(selected_methods) - set(methods))
    if unknown_methods:
        raise ValueError(f"Batch selects methods absent from manifest: {unknown_methods}")

    groups_by_id = {
        str(group.get("id")): group
        for group in manifest_groups
        if isinstance(group, dict) and group.get("id") is not None
    }
    unknown_groups = sorted(set(selected_groups) - set(groups_by_id))
    if unknown_groups:
        raise ValueError(f"Batch selects groups absent from manifest: {unknown_groups}")

    jobs: list[ExpectedJob] = []
    case_index: dict[tuple[str, int], dict[str, Any]] = {}
    for group_id in selected_groups:
        group = groups_by_id[group_id]
        family = str(group.get("family", ""))
        cases = group.get("cases")
        if not isinstance(cases, list):
            raise ValueError(f"Manifest group {group_id} has no cases[]")
        for raw_case in cases:
            if not isinstance(raw_case, dict):
                continue
            size = int(raw_case.get("clients", -1))
            if size not in selected_sizes:
                continue
            key = (group_id, size)
            if key in case_index:
                raise ValueError(f"Multiple manifest cases selected for {group_id}/{size}")
            case_index[key] = raw_case

    for group_id in selected_groups:
        for size in selected_sizes:
            raw_case = case_index.get((group_id, size))
            if raw_case is None:
                raise ValueError(f"No manifest case selected for {group_id}/{size}")
            for method_id in selected_methods:
                method_label, method_order = methods[method_id]
                jobs.append(
                    ExpectedJob(
                        group=group_id,
                        family=str(groups_by_id[group_id].get("family", "")),
                        size=size,
                        instance=str(raw_case["instance"]),
                        max_vehicles=int(raw_case["max_vehicles"]),
                        method=method_id,
                        method_label=method_label,
                        method_order=method_order,
                        seed=seed,
                    )
                )

    batch_job_ids = {
        str(item.get("job_id"))
        for item in batch.get("jobs", [])
        if isinstance(item, dict) and item.get("job_id") is not None
    }
    expected_job_ids = {job.job_id for job in jobs}
    diagnostics = {
        "selected_groups": selected_groups,
        "selected_sizes": selected_sizes,
        "selected_methods": selected_methods,
        "seed": seed,
        "expected_job_count": len(jobs),
        "batch_job_count": len(batch_job_ids),
        "job_id_sets_match": expected_job_ids == batch_job_ids,
        "missing_from_batch_index": sorted(expected_job_ids - batch_job_ids),
        "unexpected_in_batch_index": sorted(batch_job_ids - expected_job_ids),
    }
    return jobs, diagnostics


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def as_int(value: Any) -> int | None:
    number = as_float(value)
    if number is None:
        return None
    return int(number)


def load_job(snapshot_dir: Path, expected: ExpectedJob) -> JobRecord:
    directory = expected.directory(snapshot_dir)
    runner_path = directory / "runner.json"
    result_path = directory / "result.json"
    checker_path = directory / "checker.json"
    runner, runner_issue = safe_read_json(runner_path)
    result, result_issue = safe_read_json(result_path)
    checker, checker_issue = safe_read_json(checker_path)
    issues = [issue for issue in (runner_issue, result_issue, checker_issue) if issue]

    completed = bool(
        runner is not None
        and result is not None
        and checker is not None
        and runner.get("completed") is True
    )
    if completed and str(runner.get("job_id")) != expected.job_id:
        issues.append(f"runner job_id mismatch: {runner.get('job_id')!r}")
        completed = False
    if completed and str(checker.get("job_id")) != expected.job_id:
        issues.append(f"checker job_id mismatch: {checker.get('job_id')!r}")
        completed = False

    strict_feasible = bool(
        completed
        and checker is not None
        and checker.get("fresh_recheck") is True
        and checker.get("validation_status") == "valid"
        and checker.get("contract_valid") is True
        and checker.get("strict_feasible") is True
    )
    report = checker.get("report") if isinstance(checker, dict) else None
    if not isinstance(report, dict):
        report = {}
    distance = as_float(report.get("total_distance")) if strict_feasible else None
    vehicle_count = as_int(checker.get("route_count")) if strict_feasible and checker else None
    wall_runtime = as_float(runner.get("wall_runtime_seconds")) if completed and runner else None
    if completed and wall_runtime is None:
        issues.append("completed runner has no finite wall_runtime_seconds")
    if strict_feasible and distance is None:
        issues.append("strict-feasible checker has no finite report.total_distance")
    if strict_feasible and vehicle_count is None:
        issues.append("strict-feasible checker has no route_count")

    return JobRecord(
        expected=expected,
        directory=directory,
        runner_path=runner_path,
        result_path=result_path,
        checker_path=checker_path,
        runner=runner,
        result=result,
        checker=checker,
        completed=completed,
        strict_feasible=strict_feasible,
        wall_runtime_seconds=wall_runtime,
        distance=distance,
        vehicle_count=vehicle_count,
        timed_out=bool(runner.get("timed_out", False)) if completed and runner else False,
        issues=issues,
    )


def method_label(method_id: str) -> str:
    return METHOD_SHORT_LABELS.get(method_id, method_id)


def records_by_key(records: Iterable[JobRecord]) -> dict[tuple[str, int, str], JobRecord]:
    return {
        (record.expected.group, record.expected.size, record.expected.method): record
        for record in records
    }


def metric_value(record: JobRecord, metric: str) -> float | None:
    if metric == "distance":
        return record.distance
    if metric == "runtime":
        return record.wall_runtime_seconds if record.completed else None
    if metric == "vehicles":
        return float(record.vehicle_count) if record.vehicle_count is not None else None
    raise ValueError(f"Unknown metric: {metric}")


def draw_overview(
    records: list[JobRecord],
    jobs: list[ExpectedJob],
    output_path: Path,
    completed_count: int,
    strict_count: int,
) -> None:
    lookup = records_by_key(records)
    group_ids = [group for group in GROUP_ORDER if any(job.group == group for job in jobs)]
    sizes = [size for size in SIZE_ORDER if any(job.size == size for job in jobs)]
    methods = sorted(
        {job.method for job in jobs},
        key=lambda method: min(job.method_order for job in jobs if job.method == method),
    )
    family_by_group = {
        job.group: job.family for job in jobs if job.group in group_ids
    }
    instance_by_group_size = {
        (job.group, job.size): job.instance for job in jobs
    }
    cap_by_group_size = {
        (job.group, job.size): job.max_vehicles for job in jobs
    }

    fig, axes = plt.subplots(
        len(group_ids), 3, figsize=(18, 12), squeeze=False, sharex=False
    )
    metrics = (
        ("distance", "Fresh-checker distance", False),
        ("runtime", "Runner wall runtime (s)", True),
        ("vehicles", "Vehicles used", False),
    )
    width = 0.82 / max(1, len(methods))
    bases = np.arange(len(sizes), dtype=float)

    for row_index, group_id in enumerate(group_ids):
        for column_index, (metric, title, runtime_metric) in enumerate(metrics):
            ax = axes[row_index, column_index]
            relevant = [
                lookup[(group_id, size, method)]
                for size in sizes
                for method in methods
            ]
            finite_values = [
                value
                for record in relevant
                if (value := metric_value(record, metric)) is not None and value > 0
            ]
            max_value = max(finite_values, default=1.0)
            min_value = min(finite_values, default=1.0)
            if metric == "vehicles":
                # Keep every per-instance fleet-cap guide inside the panel even
                # when all feasible solutions use fewer routes than the cap.
                max_value = max(
                    [max_value]
                    + [float(cap_by_group_size[(group_id, size)]) for size in sizes]
                )
            use_log = runtime_metric and max_value / max(min_value, 1e-12) >= 20
            runtime_floor = max(min_value / 2.5, 1e-3) if use_log else 0.0

            for method_index, method in enumerate(methods):
                color = METHOD_COLORS.get(method, "#777777")
                for size_index, size in enumerate(sizes):
                    record = lookup[(group_id, size, method)]
                    x_position = bases[size_index] - 0.41 + width / 2 + method_index * width
                    value = metric_value(record, metric)
                    if value is None:
                        continue
                    if runtime_metric:
                        bottom = runtime_floor if use_log else 0.0
                        height = max(value - bottom, runtime_floor * 0.04) if use_log else value
                        bar = ax.bar(
                            x_position,
                            height,
                            width=width * 0.92,
                            bottom=bottom,
                            color=color,
                            alpha=0.9 if record.strict_feasible else 0.32,
                            edgecolor=color if record.strict_feasible else "#4D4D4D",
                            linewidth=0.7,
                            zorder=3,
                        )[0]
                        if not record.strict_feasible:
                            bar.set_hatch("////")
                    elif record.strict_feasible:
                        ax.bar(
                            x_position,
                            value,
                            width=width * 0.92,
                            color=color,
                            alpha=0.9,
                            edgecolor=color,
                            linewidth=0.7,
                            zorder=3,
                        )

            if use_log:
                ax.set_yscale("log")
                ax.set_ylim(runtime_floor, max_value * 1.7)
                pending_y = runtime_floor * 1.18
            else:
                top = max_value * (1.18 if runtime_metric else 1.15)
                ax.set_ylim(0, max(top, 1.0))
                pending_y = max(top * 0.035, 0.035)

            if not runtime_metric:
                top = ax.get_ylim()[1]
                failure_height = top * 0.045
                for method_index, method in enumerate(methods):
                    color = METHOD_COLORS.get(method, "#777777")
                    for size_index, size in enumerate(sizes):
                        record = lookup[(group_id, size, method)]
                        x_position = bases[size_index] - 0.41 + width / 2 + method_index * width
                        if record.completed and not record.strict_feasible:
                            bar = ax.bar(
                                x_position,
                                failure_height,
                                width=width * 0.92,
                                facecolor="white",
                                edgecolor=color,
                                linewidth=1.0,
                                zorder=4,
                            )[0]
                            bar.set_hatch("////")
                            ax.text(
                                x_position,
                                failure_height * 0.5,
                                "!",
                                ha="center",
                                va="center",
                                color="#8B0000",
                                fontsize=7,
                                fontweight="bold",
                                zorder=5,
                            )
                        elif not record.completed:
                            ax.scatter(
                                [x_position],
                                [pending_y],
                                marker="x",
                                s=25,
                                linewidths=1.2,
                                color="#8C8C8C",
                                zorder=5,
                            )
            else:
                for method_index, method in enumerate(methods):
                    for size_index, size in enumerate(sizes):
                        record = lookup[(group_id, size, method)]
                        if record.completed:
                            continue
                        x_position = bases[size_index] - 0.41 + width / 2 + method_index * width
                        ax.scatter(
                            [x_position],
                            [pending_y],
                            marker="x",
                            s=25,
                            linewidths=1.2,
                            color="#8C8C8C",
                            zorder=5,
                        )

            if metric == "vehicles":
                for size_index, size in enumerate(sizes):
                    cap = cap_by_group_size[(group_id, size)]
                    ax.hlines(
                        cap,
                        bases[size_index] - 0.45,
                        bases[size_index] + 0.45,
                        colors="#222222",
                        linestyles="--",
                        linewidth=1.1,
                        zorder=6,
                    )
                    ax.annotate(
                        f"K={cap}",
                        (bases[size_index] + 0.43, cap),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="right",
                        va="bottom",
                        fontsize=7,
                        color="#222222",
                    )

            labels = [
                f"{size}\n{instance_by_group_size[(group_id, size)]}" for size in sizes
            ]
            ax.set_xticks(bases, labels)
            ax.set_xlim(-0.58, len(sizes) - 0.42)
            if row_index == 0:
                ax.set_title(title, fontweight="bold")
            if column_index == 0:
                ax.set_ylabel(f"{group_id} · {family_by_group[group_id]}\n{title}")
            elif runtime_metric:
                ax.set_ylabel("seconds")
            elif metric == "vehicles":
                ax.set_ylabel("route count")
            else:
                ax.set_ylabel("distance")

    method_handles = [
        Patch(
            facecolor=METHOD_COLORS.get(method, "#777777"),
            edgecolor=METHOD_COLORS.get(method, "#777777"),
            label=method_label(method),
        )
        for method in methods
    ]
    status_handles = [
        Patch(
            facecolor="white",
            edgecolor="#555555",
            hatch="////",
            label="completed, not strict-feasible",
        ),
        Line2D(
            [0],
            [0],
            marker="x",
            linestyle="none",
            color="#8C8C8C",
            label="pending",
        ),
        Line2D(
            [0],
            [0],
            linestyle="--",
            color="#222222",
            label="fleet cap K",
        ),
    ]
    fig.legend(
        handles=method_handles + status_handles,
        loc="lower center",
        ncol=8,
        frameon=False,
        bbox_to_anchor=(0.5, 0.015),
    )
    fig.suptitle(
        "Three-group EVRP-TW stability snapshot · 5/10/15 clients\n"
        f"{completed_count}/{len(jobs)} jobs complete · "
        f"{strict_count} fresh-checker strict-feasible",
        fontsize=15,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.048,
        "Distance and vehicles are shown only for strict-feasible results; runtime is shown for every completed job.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#555555",
    )
    fig.subplots_adjust(top=0.925, bottom=0.12, hspace=0.38, wspace=0.24)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def route_visits(route: object, depot_name: str) -> list[str]:
    """Normalize route formats and add missing depot endpoints (notably VNS/TS)."""
    if isinstance(route, dict):
        visits = route.get("visits") or route.get("route") or route.get("nodes") or []
    elif isinstance(route, list):
        visits = route
    else:
        visits = []
    normalized = [str(value) for value in visits]
    if not normalized or normalized[0] != depot_name:
        normalized.insert(0, depot_name)
    if normalized[-1] != depot_name:
        normalized.append(depot_name)
    return normalized


def locations_from_result(result: dict[str, Any]) -> tuple[dict[str, Location], Location]:
    instance = result.get("instance")
    if not isinstance(instance, dict):
        raise ValueError("result.json has no embedded instance object")
    depot_data = instance.get("depot")
    if not isinstance(depot_data, dict):
        raise ValueError("result.json embedded instance has no depot")
    depot = Location(
        name=str(depot_data["name"]),
        kind="d",
        x=float(depot_data["x"]),
        y=float(depot_data["y"]),
    )
    locations = {depot.name: depot}
    for field_name, kind in (("charging_stations", "f"), ("clients", "c")):
        entries = instance.get(field_name)
        if not isinstance(entries, list):
            raise ValueError(f"result.json embedded instance has no {field_name}[]")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            location = Location(
                name=str(entry["name"]),
                kind=kind,
                x=float(entry["x"]),
                y=float(entry["y"]),
            )
            locations[location.name] = location
    return locations, depot


def scatter_locations(ax: plt.Axes, locations: dict[str, Location], depot: Location) -> None:
    customers = [location for location in locations.values() if location.kind == "c"]
    stations = [location for location in locations.values() if location.kind == "f"]
    ax.scatter(
        [location.x for location in customers],
        [location.y for location in customers],
        s=27,
        marker="o",
        facecolor="white",
        edgecolor="#222222",
        linewidth=0.7,
        zorder=3,
        label="Customer",
    )
    ax.scatter(
        [location.x for location in stations],
        [location.y for location in stations],
        s=41,
        marker="s",
        facecolor="#FFD966",
        edgecolor="#7F6000",
        linewidth=0.8,
        zorder=4,
        label="Charging station",
    )
    ax.scatter(
        [depot.x],
        [depot.y],
        s=94,
        marker="D",
        facecolor="#CC0000",
        edgecolor="white",
        linewidth=1.0,
        zorder=5,
        label="Depot",
    )
    if len(customers) <= 15:
        for location in customers + stations:
            ax.annotate(
                location.name,
                (location.x, location.y),
                xytext=(4, 3),
                textcoords="offset points",
                fontsize=6.5,
            )


def plot_routes(
    ax: plt.Axes,
    result: dict[str, Any],
    locations: dict[str, Location],
    depot: Location,
) -> None:
    routes = result.get("routes") or []
    if not isinstance(routes, list):
        raise ValueError("result.json routes is not a list")
    for route_index, route in enumerate(routes):
        visits = route_visits(route, depot.name)
        unknown = [name for name in visits if name not in locations]
        if unknown:
            raise ValueError(f"Unknown locations in selected route: {unknown}")
        xs = [locations[name].x for name in visits]
        ys = [locations[name].y for name in visits]
        color = ROUTE_COLORS[route_index % len(ROUTE_COLORS)]
        linestyle = ROUTE_LINESTYLES[
            (route_index // len(ROUTE_COLORS)) % len(ROUTE_LINESTYLES)
        ]
        ax.plot(
            xs,
            ys,
            color=color,
            linestyle=linestyle,
            linewidth=1.55,
            alpha=0.84,
            zorder=1,
        )


def select_best_routes(
    records: list[JobRecord], jobs: list[ExpectedJob], snapshot_dir: Path
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], JobRecord | None]]:
    lookup = records_by_key(records)
    method_ids = sorted(
        {job.method for job in jobs},
        key=lambda method: min(job.method_order for job in jobs if job.method == method),
    )
    selected: dict[tuple[str, int], JobRecord | None] = {}
    rows: list[dict[str, Any]] = []

    for group_id in GROUP_ORDER:
        for size in SIZE_ORDER:
            case_jobs = [job for job in jobs if job.group == group_id and job.size == size]
            if not case_jobs:
                continue
            case_records = [lookup[(group_id, size, method)] for method in method_ids]
            completed_records = [record for record in case_records if record.completed]
            feasible_records = [
                record
                for record in completed_records
                if record.strict_feasible and record.distance is not None
            ]
            feasible_records.sort(
                key=lambda record: (record.distance, record.expected.method_order)
            )
            best = feasible_records[0] if feasible_records else None
            selected[(group_id, size)] = best
            completed = len(completed_records)
            strict = len(feasible_records)
            total = len(method_ids)
            if best is None:
                status = "no_strict_feasible"
                note = "No strict-feasible solution"
            elif completed < total:
                status = "provisional_best"
                note = f"Provisional best among {completed}/{total} completed methods"
            else:
                status = "strict_best"
                note = f"Best among {strict} strict-feasible methods"

            exemplar = best or next(
                (record for record in case_records if record.result is not None), None
            )
            row = {
                "group": group_id,
                "family": case_jobs[0].family,
                "clients": size,
                "instance": case_jobs[0].instance,
                "max_vehicles": case_jobs[0].max_vehicles,
                "status": status,
                "completed_methods": completed,
                "total_methods": total,
                "strict_feasible_methods": strict,
                "best_method": best.expected.method if best else "",
                "best_method_label": method_label(best.expected.method) if best else "",
                "fresh_checker_distance": best.distance if best else "",
                "vehicle_count": best.vehicle_count if best else "",
                "wall_runtime_seconds": best.wall_runtime_seconds if best else "",
                "job_id": best.expected.job_id if best else "",
                "result_relative_path": (
                    relative_posix(best.result_path, snapshot_dir) if best else ""
                ),
                "checker_relative_path": (
                    relative_posix(best.checker_path, snapshot_dir) if best else ""
                ),
                "location_source_relative_path": (
                    relative_posix(exemplar.result_path, snapshot_dir) if exemplar else ""
                ),
                "note": note,
            }
            rows.append(row)
    return rows, selected


def draw_best_route_petals(
    records: list[JobRecord],
    jobs: list[ExpectedJob],
    selection_rows: list[dict[str, Any]],
    selected: dict[tuple[str, int], JobRecord | None],
    output_path: Path,
) -> None:
    lookup = records_by_key(records)
    row_lookup = {
        (str(row["group"]), int(row["clients"])): row for row in selection_rows
    }
    method_ids = sorted(
        {job.method for job in jobs},
        key=lambda method: min(job.method_order for job in jobs if job.method == method),
    )
    fig, axes = plt.subplots(3, 3, figsize=(15.5, 14.5), squeeze=False)

    first_legend_ax: plt.Axes | None = None
    for row_index, group_id in enumerate(GROUP_ORDER):
        for column_index, size in enumerate(SIZE_ORDER):
            ax = axes[row_index, column_index]
            selection = row_lookup[(group_id, size)]
            best = selected[(group_id, size)]
            case_records = [lookup[(group_id, size, method)] for method in method_ids]
            exemplar = best or next(
                (record for record in case_records if record.result is not None), None
            )
            if exemplar is None or exemplar.result is None:
                ax.set_axis_off()
                ax.text(
                    0.5,
                    0.5,
                    "No snapshotted result\nfor location data",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    color="#8C8C8C",
                )
                continue

            locations, depot = locations_from_result(exemplar.result)
            if best is not None and best.result is not None:
                plot_routes(ax, best.result, locations, depot)
            scatter_locations(ax, locations, depot)
            first_legend_ax = first_legend_ax or ax

            base_title = f"{group_id} · {size} clients · {selection['instance']}"
            if best is None:
                max_vehicles = int(selection["max_vehicles"])
                ax.set_facecolor("#FAFAFA")
                ax.set_title(
                    base_title
                    + f"\nNo strict-feasible result (K={max_vehicles})",
                    color="#8B0000",
                )
                ax.text(
                    0.5,
                    0.52,
                    f"No strict-feasible\nresult (K={max_vehicles})",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=12,
                    fontweight="bold",
                    color="#8B0000",
                    bbox={
                        "boxstyle": "round,pad=0.45",
                        "facecolor": "white",
                        "edgecolor": "#C0504D",
                        "alpha": 0.92,
                    },
                    zorder=7,
                )
            else:
                details = (
                    f"{method_label(best.expected.method)} · distance={best.distance:,.0f} · "
                    f"routes={best.vehicle_count}/{best.expected.max_vehicles}"
                )
                if selection["status"] == "provisional_best":
                    completed = int(selection["completed_methods"])
                    total = int(selection["total_methods"])
                    ax.set_facecolor("#FFF8E7")
                    ax.set_title(base_title + "\n" + details)
                    ax.text(
                        0.02,
                        0.98,
                        f"Provisional best among {completed}/{total}",
                        transform=ax.transAxes,
                        ha="left",
                        va="top",
                        fontsize=8,
                        fontweight="bold",
                        color="#8A5200",
                        bbox={
                            "boxstyle": "round,pad=0.25",
                            "facecolor": "#FFE5A1",
                            "edgecolor": "#C78500",
                            "alpha": 0.94,
                        },
                        zorder=8,
                    )
                else:
                    ax.set_title(base_title + "\n" + details)

            ax.set_xlabel("x coordinate")
            ax.set_ylabel("y coordinate")
            ax.set_aspect("equal", adjustable="datalim")
            ax.margins(0.09)

    if first_legend_ax is not None:
        handles, labels = first_legend_ax.get_legend_handles_labels()
        fig.legend(
            handles,
            labels,
            loc="lower center",
            ncol=3,
            frameon=False,
            bbox_to_anchor=(0.5, 0.012),
        )
    fig.suptitle(
        "Best route petals by distribution and size\n"
        "minimum fresh-checker distance; manifest method order breaks ties",
        fontsize=15,
        fontweight="bold",
        y=0.995,
    )
    fig.subplots_adjust(top=0.925, bottom=0.07, hspace=0.32, wspace=0.20)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_selection_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("No best-route selection rows")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify_snapshot_integrity(snapshot_dir: Path) -> dict[str, Any]:
    hash_manifest_path = snapshot_dir / HASH_MANIFEST_RELATIVE_PATH
    with hash_manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    listed_paths: set[str] = set()
    matches = 0
    mismatches: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for row in rows:
        relative = str(row["relative_path"]).replace("\\", "/")
        listed_paths.add(relative)
        path = snapshot_dir / Path(relative)
        if not path.is_file():
            missing.append(
                {
                    "relative_path": relative,
                    "expected_bytes": int(row["bytes"]),
                    "expected_sha256": str(row["sha256"]).upper(),
                }
            )
            continue
        actual_bytes = path.stat().st_size
        actual_hash = sha256_file(path)
        expected_bytes = int(row["bytes"])
        expected_hash = str(row["sha256"]).upper()
        if actual_bytes == expected_bytes and actual_hash == expected_hash:
            matches += 1
        else:
            mismatches.append(
                {
                    "relative_path": relative,
                    "expected_bytes": expected_bytes,
                    "actual_bytes": actual_bytes,
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                }
            )

    actual_paths = {
        path.relative_to(snapshot_dir).as_posix()
        for path in snapshot_dir.rglob("*")
        if path.is_file() and path != hash_manifest_path
    }
    unexpected = sorted(actual_paths - listed_paths)
    trusted_prefixes = ("raw/", "protocol/")
    trusted_issues = [
        issue
        for issue in mismatches + missing
        if str(issue["relative_path"]).startswith(trusted_prefixes)
    ]
    trusted_unexpected = [
        relative for relative in unexpected if relative.startswith(trusted_prefixes)
    ]
    summary_mismatch = next(
        (
            issue
            for issue in mismatches
            if issue["relative_path"] == "results/summary.md"
        ),
        None,
    )
    return {
        "hash_manifest": HASH_MANIFEST_RELATIVE_PATH.as_posix(),
        "hash_manifest_sha256": sha256_file(hash_manifest_path),
        "listed_files": len(rows),
        "matching_files": matches,
        "mismatch_count": len(mismatches),
        "missing_count": len(missing),
        "unexpected_count": len(unexpected),
        "all_listed_files_ok": not mismatches and not missing and not unexpected,
        "trusted_raw_and_protocol_ok": not trusted_issues and not trusted_unexpected,
        "mismatches": mismatches,
        "missing": missing,
        "unexpected": unexpected,
        "trusted_scope_issues": trusted_issues + [
            {"relative_path": relative, "status": "unexpected"}
            for relative in trusted_unexpected
        ],
        "summary_md_hash_mismatch": summary_mismatch,
        "summary_md_used_as_input": False,
    }


def consumed_input_hashes(
    snapshot_dir: Path, records: list[JobRecord]
) -> dict[str, Any]:
    paths = {
        snapshot_dir / MANIFEST_RELATIVE_PATH,
        snapshot_dir / BATCH_INDEX_RELATIVE_PATH,
    }
    for record in records:
        for path in (record.runner_path, record.result_path, record.checker_path):
            if path.is_file():
                paths.add(path)
    entries = [
        {
            "relative_path": relative_posix(path, snapshot_dir),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths, key=lambda item: relative_posix(item, snapshot_dir))
    ]
    tree_material = "".join(
        f"{entry['relative_path']}\0{entry['bytes']}\0{entry['sha256']}\n"
        for entry in entries
    ).encode("utf-8")
    return {
        "file_count": len(entries),
        "tree_sha256": hashlib.sha256(tree_material).hexdigest().upper(),
        "files": entries,
    }


def declared_counts(batch: dict[str, Any]) -> dict[str, int | None]:
    counts = batch.get("counts")
    if not isinstance(counts, dict):
        return {
            "requested": None,
            "completed": None,
            "pending": None,
            "strict_feasible": None,
            "timed_out": None,
        }
    return {
        key: as_int(counts.get(key))
        for key in ("requested", "completed", "pending", "strict_feasible", "timed_out")
    }


def main() -> None:
    args = parse_args()
    snapshot_dir = args.snapshot_dir.resolve()
    output_dir = args.output_dir.resolve()
    require_snapshot_layout(snapshot_dir, output_dir)

    manifest_path = snapshot_dir / MANIFEST_RELATIVE_PATH
    batch_index_path = snapshot_dir / BATCH_INDEX_RELATIVE_PATH
    manifest = read_json(manifest_path)
    batch = read_json(batch_index_path)
    jobs, job_diagnostics = build_expected_jobs(manifest, batch)

    selected_sizes = set(int(value) for value in selected_values(batch, "sizes"))
    if selected_sizes != set(SIZE_ORDER):
        raise ValueError(
            "This snapshot visualization requires batch selections.sizes to be exactly 5,10,15"
        )
    if len(jobs) != 45:
        raise ValueError(f"Expected 45 selected jobs, reconstructed {len(jobs)}")

    records = [load_job(snapshot_dir, job) for job in jobs]
    completed_count = sum(record.completed for record in records)
    strict_count = sum(record.strict_feasible for record in records)
    timed_out_count = sum(record.timed_out for record in records)
    pending_count = len(records) - completed_count
    nonstrict_completed_count = completed_count - strict_count

    output_dir.mkdir(parents=True, exist_ok=True)
    overview_path = output_dir / "overview.png"
    petals_path = output_dir / "best-route-petals.png"
    selection_path = output_dir / "best-route-selection.csv"
    metadata_path = output_dir / "visualization-metadata.json"

    configure_style()
    draw_overview(
        records,
        jobs,
        overview_path,
        completed_count=completed_count,
        strict_count=strict_count,
    )
    selection_rows, selected = select_best_routes(records, jobs, snapshot_dir)
    draw_best_route_petals(
        records,
        jobs,
        selection_rows,
        selected,
        petals_path,
    )
    write_selection_csv(selection_path, selection_rows)

    integrity = verify_snapshot_integrity(snapshot_dir)
    consumed_hashes = consumed_input_hashes(snapshot_dir, records)
    computed_counts = {
        "requested": len(records),
        "completed": completed_count,
        "pending": pending_count,
        "strict_feasible": strict_count,
        "completed_not_strict_feasible": nonstrict_completed_count,
        "timed_out": timed_out_count,
    }
    declared = declared_counts(batch)
    count_comparison = {
        key: {
            "declared": declared.get(key),
            "computed": computed_counts.get(key),
            "matches": declared.get(key) == computed_counts.get(key),
        }
        for key in ("requested", "completed", "pending", "strict_feasible", "timed_out")
    }
    record_issues = [
        {"job_id": record.expected.job_id, "issues": record.issues}
        for record in records
        if record.issues
    ]
    pending_jobs = [
        {
            "job_id": record.expected.job_id,
            "existing_files": [
                path.name
                for path in (record.runner_path, record.result_path, record.checker_path)
                if path.is_file()
            ],
        }
        for record in records
        if not record.completed
    ]
    generated_artifacts = {
        path.name: {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in (overview_path, petals_path, selection_path)
    }
    metadata = {
        "schema_version": 1,
        "script_version": SCRIPT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_name": snapshot_dir.name,
        "experiment_id": manifest.get("experiment_id"),
        "batch_id": batch.get("batch_id"),
        "scope": {
            "groups": selected_values(batch, "groups"),
            "sizes": selected_values(batch, "sizes"),
            "methods": selected_values(batch, "methods"),
            "seed": int(batch.get("seed", manifest.get("seed", 1))),
        },
        "counts": computed_counts,
        "strict_feasible_definition": {
            "fresh_recheck": True,
            "validation_status": "valid",
            "contract_valid": True,
            "strict_feasible": True,
            "distance_source": "checker.json report.total_distance",
            "vehicle_count_source": "checker.json route_count",
            "runtime_source": "runner.json wall_runtime_seconds",
        },
        "path_resolution_policy": {
            "expected_jobs_built_from": [
                MANIFEST_RELATIVE_PATH.as_posix(),
                BATCH_INDEX_RELATIVE_PATH.as_posix(),
            ],
            "job_directory_template": (
                "raw/runs/{group}/{clients}/{instance}/{method}/seed-{seed:04d}"
            ),
            "runs_csv_used": False,
            "live_absolute_paths_used": False,
            "ignored_absolute_fields": [
                "batch_index.manifest",
                "batch_index.raw_dir",
                "batch_index.result_dir",
                "batch_index.jobs[*].runner_path",
                "batch_index.jobs[*].checker_path",
                "runner.result_path",
                "runner.stdout_path",
                "runner.stderr_path",
                "runner.checker_path",
            ],
            "route_location_source": "embedded result.json instance object",
        },
        "job_construction_checks": job_diagnostics,
        "completeness_checks": {
            "declared_vs_computed_counts": count_comparison,
            "all_declared_counts_match": all(
                comparison["matches"] for comparison in count_comparison.values()
            ),
            "record_parse_or_identity_issues": record_issues,
            "pending_jobs": pending_jobs,
        },
        "snapshot_integrity": integrity,
        "input_hashes": consumed_hashes,
        "best_route_selection": selection_rows,
        "generated_artifacts": generated_artifacts,
        "interpretation_notes": [
            "The overview contains only the 45 jobs selected by the snapshotted 5/10/15-client batch.",
            "Distance and vehicle bars require all four fresh-checker strict-feasibility fields.",
            "Completed non-strict results are status placeholders for distance/vehicles and hatched runtime bars.",
            "RC/10 is intentionally shown as No strict-feasible solution.",
            "RC/15 is provisional because only 1/5 methods had completed when the snapshot was taken.",
            "results/summary.md is not an input; its known hash mismatch is reported by snapshot_integrity.",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    for path in (overview_path, petals_path, selection_path, metadata_path):
        print(path)


if __name__ == "__main__":
    main()
