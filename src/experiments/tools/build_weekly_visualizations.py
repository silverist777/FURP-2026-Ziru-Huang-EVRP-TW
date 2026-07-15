"""Build the curated weekly result figures from raw experiment logs.

Raw solver outputs live under ``src/log/weekN``.  This script writes only
derived PNG figures under ``src/results/weekN`` and never edits raw data.
Run it from any working directory with the repository virtual environment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / "src" / "log"
RESULTS = ROOT / "src" / "results"

COLORS = {
    "PyVRP": "#3366CC",
    "POMO": "#DC3912",
    "VNS/TS": "#109618",
    "py-ga": "#FF9900",
    "GA": "#FF9900",
}

ROUTE_COLORS = list(plt.get_cmap("tab20").colors)
ROUTE_LINESTYLES = ["-", "--", "-.", ":"]


@dataclass(frozen=True)
class Location:
    name: str
    kind: str
    x: float
    y: float


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#555555",
            "axes.grid": True,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.7,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
        }
    )


def save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(path.relative_to(ROOT))


def short_method(value: str) -> str:
    text = str(value).lower()
    if "pyvrp" in text:
        return "PyVRP"
    if "pomo" in text:
        return "POMO"
    if "vns" in text or "tabu" in text:
        return "VNS/TS"
    if "py-ga" in text or text == "ga":
        return "py-ga"
    return str(value)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_evrptw_locations(path: Path) -> dict[str, Location]:
    """Read the location table at the start of a Schneider EVRP-TW file."""
    locations: dict[str, Location] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            if locations:
                break
            continue
        fields = line.split()
        if fields[0].lower() == "stringid":
            continue
        if len(fields) < 4 or fields[1].lower() not in {"d", "f", "c"}:
            if locations:
                break
            continue
        locations[fields[0]] = Location(fields[0], fields[1].lower(), float(fields[2]), float(fields[3]))
    if not locations:
        raise ValueError(f"No EVRP-TW locations found in {path}")
    return locations


def route_visits(route: object, depot_name: str) -> list[str]:
    """Normalize the route formats used by the four method wrappers."""
    if isinstance(route, dict):
        visits = route.get("visits") or route.get("route") or route.get("nodes") or []
    else:
        visits = route
    normalized = [str(value) for value in visits]
    if not normalized or normalized[0] != depot_name:
        normalized.insert(0, depot_name)
    if normalized[-1] != depot_name:
        normalized.append(depot_name)
    return normalized


def best_feasible_records(summary_path: Path) -> pd.DataFrame:
    """Select one minimum-distance checker-feasible result per instance."""
    frame = pd.read_csv(summary_path)
    frame["feasible_bool"] = frame["feasible"].astype(str).str.lower().eq("true")
    frame = frame[frame["feasible_bool"] & frame["total_distance"].notna()].copy()
    if frame.empty:
        raise ValueError(f"No feasible results in {summary_path}")
    # Stable sorting makes ties reproducible and preserves the summary's method order.
    frame["_row_order"] = np.arange(len(frame))
    frame = frame.sort_values(["instance", "total_distance", "_row_order"], kind="stable")
    return frame.drop_duplicates("instance", keep="first")


def plot_best_route_petals(summary_path: Path, output: Path, title: str) -> None:
    """Plot the best feasible route set for every instance as depot-centred petals."""
    selected = best_feasible_records(summary_path)
    instance_order = ["c101C5", "c101C10", "c103C15", "c101_21"]
    selected["_instance_order"] = selected["instance"].map(
        {name: index for index, name in enumerate(instance_order)}
    ).fillna(len(instance_order))
    selected = selected.sort_values(["_instance_order", "instance"], kind="stable")

    columns = 2
    rows = int(np.ceil(len(selected) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=(14, 6.2 * rows), squeeze=False)
    for ax, (_, record) in zip(axes.flat, selected.iterrows()):
        instance_name = str(record["instance"])
        source_path = ROOT / Path(str(record["source_file"]))
        data = read_json(source_path)
        instance_path = ROOT / "src" / "data" / "evrptw_instances" / f"{instance_name}.txt"
        locations = read_evrptw_locations(instance_path)
        depots = [location for location in locations.values() if location.kind == "d"]
        if not depots:
            raise ValueError(f"No depot in {instance_path}")
        depot = depots[0]
        routes = data.get("routes") or []

        for route_index, route in enumerate(routes):
            visits = route_visits(route, depot.name)
            unknown = [name for name in visits if name not in locations]
            if unknown:
                raise ValueError(f"Unknown locations in {source_path}: {unknown}")
            xs = [locations[name].x for name in visits]
            ys = [locations[name].y for name in visits]
            color = ROUTE_COLORS[route_index % len(ROUTE_COLORS)]
            linestyle = ROUTE_LINESTYLES[(route_index // len(ROUTE_COLORS)) % len(ROUTE_LINESTYLES)]
            ax.plot(xs, ys, color=color, linestyle=linestyle, linewidth=1.5, alpha=0.82, zorder=1)

        customers = [location for location in locations.values() if location.kind == "c"]
        stations = [location for location in locations.values() if location.kind == "f"]
        ax.scatter(
            [location.x for location in customers],
            [location.y for location in customers],
            s=25,
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
            s=38,
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
            s=90,
            marker="D",
            facecolor="#CC0000",
            edgecolor="white",
            linewidth=1.0,
            zorder=5,
            label="Depot",
        )
        if len(customers) <= 15:
            for location in customers:
                ax.annotate(location.name, (location.x, location.y), xytext=(4, 3), textcoords="offset points", fontsize=7)
            for location in stations:
                ax.annotate(location.name, (location.x, location.y), xytext=(4, 3), textcoords="offset points", fontsize=7)

        method = short_method(str(record["method"]))
        ax.set_title(
            f"{instance_name} · {method}\n"
            f"distance={float(record['total_distance']):,.0f} · routes={int(record['vehicle_count'])}"
        )
        ax.set_xlabel("x coordinate")
        ax.set_ylabel("y coordinate")
        ax.set_aspect("equal", adjustable="datalim")
        ax.margins(0.08)

    for ax in axes.flat[len(selected):]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(title + "\nminimum distance among checker-feasible solutions", fontsize=14)
    fig.subplots_adjust(bottom=0.07, top=0.91, hspace=0.28, wspace=0.18)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(output.relative_to(ROOT))


def metric_record(path: Path) -> dict | None:
    data = read_json(path)
    metrics = data.get("metrics") or {}
    if not metrics:
        return None
    record = data.get("experiment_record") or {}
    instance = data.get("instance") or {}
    solver = data.get("solver") or {}
    return {
        "instance": record.get("instance_name") or instance.get("name") or path.stem,
        "method": short_method(record.get("method_name") or solver.get("name") or path.stem),
        "distance": float(metrics.get("total_distance") or 0),
        "runtime": float(record.get("runtime_seconds") or solver.get("elapsed_seconds") or 0),
        "vehicles": float(metrics.get("vehicle_count") or 0),
        "feasible": bool(metrics.get("feasible", False)),
        "missing": float(metrics.get("missing_customers") or 0),
        "energy": float(metrics.get("energy_violations") or 0),
    }


def plot_gap_files(files: list[Path], output: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    labels = {
        "pomo_a_eval_results.csv": "base checkpoint",
        "pomo_a_eval_results_short_train.csv": "short train",
        "pomo_a_eval_results_100epoch.csv": "100 epochs",
        "pomo_solomon_eval_results.csv": "base checkpoint",
        "pomo_solomon_eval_results_train_smoke.csv": "train smoke",
        "pomo_solomon_eval_results_1000epoch.csv": "1000 epochs",
    }
    for path in files:
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        x = np.arange(len(frame))
        ax.plot(x, frame["gap_pct"], marker="o", markersize=3, linewidth=1.4, label=labels.get(path.name, path.stem))
        if len(frame) <= 16:
            ax.set_xticks(x, frame["instance"], rotation=45, ha="right")
        else:
            step = max(1, len(frame) // 12)
            ticks = x[::step]
            ax.set_xticks(ticks, frame["instance"].iloc[::step], rotation=45, ha="right")
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("Gap to known solution (%)")
    ax.set_xlabel("Benchmark instance")
    ax.legend(frameon=False)
    save(fig, output)


def plot_single_known_predicted(path: Path, output: Path, title: str) -> None:
    frame = pd.read_csv(path)
    row = frame.iloc[0]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    values = [float(row["known_cost"]), float(row["predicted_cost"])]
    bars = ax.bar(["Known", "Predicted"], values, color=["#3366CC", "#DC3912"])
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,.0f}", ha="center", va="bottom")
    ax.set_title(title)
    ax.set_ylabel("Route cost")
    ax.text(0.98, 0.95, f"gap = {float(row['gap_pct']):.1f}%", transform=ax.transAxes, ha="right", va="top")
    save(fig, output)


def plot_pyvrp_solomon(path: Path, output: Path) -> None:
    frame = pd.read_csv(path)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    order = np.arange(len(frame))
    colors = ["#109618" if bool(value) else "#DC3912" for value in frame["is_feasible"]]
    ax.bar(order, frame["gap_pct"], color=colors, width=0.75)
    step = max(1, len(frame) // 15)
    ax.set_xticks(order[::step], frame["instance"].iloc[::step], rotation=45, ha="right")
    ax.set_title("PyVRP on Solomon benchmarks")
    ax.set_ylabel("Gap to known solution (%)")
    ax.set_xlabel("Instance (green = feasible)")
    save(fig, output)


def plot_method_comparison(path: Path, output: Path) -> None:
    frame = pd.read_csv(path)
    frame["method"] = frame["algorithm"].map(short_method)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for method, group in frame.groupby("method", sort=False):
        color = COLORS.get(method, None)
        axes[0].plot(group["clients"], group["objective_value"], marker="o", label=method, color=color)
        axes[1].plot(group["clients"], group["runtime_seconds"], marker="o", label=method, color=color)
    axes[0].set_title("Objective by problem size")
    axes[0].set_xlabel("Clients")
    axes[0].set_ylabel("Route distance")
    axes[1].set_title("Runtime by problem size")
    axes[1].set_xlabel("Clients")
    axes[1].set_ylabel("Runtime (s)")
    axes[1].set_yscale("log")
    axes[0].legend(frameon=False)
    save(fig, output)


def plot_pipeline_versions(paths: list[Path], output: Path) -> None:
    rows = []
    for path in paths:
        metrics = read_json(path).get("metrics") or {}
        rows.append(
            {
                "version": "v3 partial charge" if "v3" in path.stem else "baseline repair",
                "distance": metrics.get("total_distance", 0),
                "duration": metrics.get("total_duration", 0),
                "charging": metrics.get("charging_time", 0),
            }
        )
    frame = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.2))
    for ax, field, label in zip(axes, ["distance", "duration", "charging"], ["Distance", "Duration", "Charging time"]):
        bars = ax.bar(frame["version"], frame[field], color=["#3366CC", "#109618"])
        ax.set_title(label)
        ax.tick_params(axis="x", rotation=25)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{bar.get_height():.0f}", ha="center", va="bottom")
    save(fig, output)


def parse_ga_log(path: Path) -> pd.DataFrame:
    generation = None
    rows: list[dict] = []
    generation_pattern = re.compile(r"-- Generation (\d+) --")
    max_pattern = re.compile(r"^\s*Max\s+([0-9.eE+-]+)")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = generation_pattern.search(line)
        if match:
            generation = int(match.group(1))
            continue
        match = max_pattern.search(line)
        if match and generation is not None:
            fitness = float(match.group(1))
            if fitness > 0:
                rows.append({"generation": generation, "objective": 1.0 / fitness})
    return pd.DataFrame(rows)


def plot_penalty_convergence(log_dir: Path, output: Path, penalty: str) -> None:
    file_pattern = re.compile(r"C101_(\d+)_seed(\d+)")
    curves: dict[int, list[pd.DataFrame]] = {}
    for path in sorted((log_dir / "raw").glob("*.log")):
        match = file_pattern.search(path.name)
        if not match:
            continue
        size = int(match.group(1))
        frame = parse_ga_log(path)
        if not frame.empty:
            frame["best"] = frame["objective"].cummin()
            curves.setdefault(size, []).append(frame)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for size, frames in sorted(curves.items()):
        merged = pd.concat([f.set_index("generation")["best"].rename(i) for i, f in enumerate(frames)], axis=1)
        mean = merged.mean(axis=1)
        std = merged.std(axis=1).fillna(0)
        ax.plot(mean.index, mean, label=f"{size} clients", linewidth=1.7)
        ax.fill_between(mean.index, mean - std, mean + std, alpha=0.15)
    ax.set_title(f"py-ga best-so-far convergence (delay penalty {penalty})")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Penalized objective (lower is better)")
    ax.set_yscale("log")
    ax.legend(frameon=False)
    save(fig, output)


def plot_json_records(paths: list[Path], output: Path, title: str) -> None:
    rows = [record for path in paths if (record := metric_record(path)) is not None]
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"No metric-bearing JSON files for {title}")
    labels = [str(value) for value in frame["instance"]]
    x = np.arange(len(frame))
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    for ax, field, label in zip(axes, ["distance", "runtime", "vehicles"], ["Distance", "Runtime (s)", "Vehicles"]):
        colors = ["#109618" if feasible else "#DC3912" for feasible in frame["feasible"]]
        bars = ax.bar(x, frame[field], color=colors)
        for bar, feasible in zip(bars, frame["feasible"]):
            if not feasible:
                bar.set_hatch("///")
        ax.set_title(label)
        ax.set_xticks(x, labels, rotation=35, ha="right")
    fig.suptitle(title + " (hatched = infeasible)")
    save(fig, output)


def plot_summary_csv(path: Path, output: Path, title: str) -> None:
    frame = pd.read_csv(path)
    method_column = "method" if "method" in frame.columns else "algorithm"
    frame["method_short"] = frame[method_column].map(short_method)
    feasible = frame["feasible"].astype(str).str.lower().eq("true") if "feasible" in frame.columns else pd.Series(True, index=frame.index)
    frame["feasible_bool"] = feasible
    instance_column = "instance" if "instance" in frame.columns else "clients"
    metric_fields = [
        ("total_distance" if "total_distance" in frame.columns else "objective_value", "Distance"),
        ("runtime_seconds", "Runtime (s)"),
        ("vehicle_count" if "vehicle_count" in frame.columns else None, "Vehicles"),
    ]
    metric_fields = [(field, label) for field, label in metric_fields if field is not None and field in frame.columns]
    fig, axes = plt.subplots(1, len(metric_fields), figsize=(5 * len(metric_fields), 4.8), squeeze=False)
    instances = list(dict.fromkeys(frame[instance_column].astype(str)))
    methods = list(dict.fromkeys(frame["method_short"]))
    width = 0.8 / max(1, len(methods))
    base = np.arange(len(instances))
    for ax, (field, label) in zip(axes[0], metric_fields):
        for index, method in enumerate(methods):
            values = []
            statuses = []
            for instance in instances:
                rows = frame[(frame[instance_column].astype(str) == instance) & (frame["method_short"] == method)]
                values.append(float(rows[field].iloc[0]) if not rows.empty and pd.notna(rows[field].iloc[0]) else np.nan)
                statuses.append(bool(rows["feasible_bool"].iloc[0]) if not rows.empty else False)
            positions = base - 0.4 + width / 2 + index * width
            bars = ax.bar(positions, values, width=width, label=method, color=COLORS.get(method), alpha=0.9)
            for bar, status in zip(bars, statuses):
                if not status:
                    bar.set_hatch("///")
                    bar.set_alpha(0.45)
        ax.set_title(label)
        ax.set_xticks(base, instances, rotation=35, ha="right")
        if label == "Runtime (s)" and frame[field].max() / max(frame[field].replace(0, np.nan).min(), 1e-9) > 100:
            ax.set_yscale("log")
    axes[0, 0].legend(frameon=False)
    fig.suptitle(title + " (hatched = infeasible)")
    save(fig, output)


def plot_pomo_route_distribution(path: Path, output: Path) -> None:
    data = read_json(path)
    routes = data.get("routes") or []
    customer_counts = [sum(1 for node in route if str(node).startswith("C")) for route in routes]
    metrics = data.get("metrics") or {}
    values, counts = np.unique(customer_counts, return_counts=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(values, counts, color="#DC3912")
    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, count, str(count), ha="center", va="bottom")
    ax.set_title("POMO + repair route fragmentation on c101_21")
    ax.set_xlabel("Customers served per route")
    ax.set_ylabel("Number of routes")
    ax.set_xticks(values)
    ax.text(
        0.98,
        0.95,
        f"{metrics.get('vehicle_count', 0)} vehicles · distance {metrics.get('total_distance', 0):,.0f}\n"
        f"{metrics.get('served_customers', 0)} customers · feasible={metrics.get('feasible', False)}",
        transform=ax.transAxes,
        ha="right",
        va="top",
    )
    save(fig, output)


def main() -> None:
    configure_style()

    plot_gap_files(
        sorted((LOG / "week1" / "pomo-a-eval").glob("*.csv")),
        RESULTS / "week1" / "pomo-a-eval" / "overview.png",
        "POMO training variants on Augerat A",
    )
    plot_gap_files(
        sorted((LOG / "week1" / "pomo-solomon-eval").glob("*.csv")),
        RESULTS / "week1" / "pomo-solomon-eval" / "overview.png",
        "POMO training variants on Solomon",
    )
    plot_single_known_predicted(
        LOG / "week1" / "pomo-holmberger-eval" / "pomo_holmberger_C1_2_1_eval.csv",
        RESULTS / "week1" / "pomo-holmberger-eval" / "overview.png",
        "POMO on Holmberger C1_2_1",
    )
    plot_pyvrp_solomon(
        LOG / "week1" / "pyvrp-solomon-eval" / "pyvrp_solomon_eval_results.csv",
        RESULTS / "week1" / "pyvrp-solomon-eval" / "overview.png",
    )

    plot_method_comparison(
        LOG / "week2" / "method-comparison-cvrp" / "cvrp_method_comparison.csv",
        RESULTS / "week2" / "method-comparison-cvrp" / "overview.png",
    )
    plot_pipeline_versions(
        [
            LOG / "week2" / "evrptw-pipeline" / "schneider_sample_solution.json",
            LOG / "week2" / "evrptw-pipeline" / "schneider_sample_v3_solution.json",
        ],
        RESULTS / "week2" / "evrptw-pipeline" / "overview.png",
    )

    plot_penalty_convergence(
        LOG / "week3" / "pyga-penalty-10000",
        RESULTS / "week3" / "pyga-penalty-10000" / "overview.png",
        "10,000",
    )
    plot_penalty_convergence(
        LOG / "week3" / "pyga-penalty-100000",
        RESULTS / "week3" / "pyga-penalty-100000" / "overview.png",
        "100,000",
    )
    plot_json_records(
        sorted((LOG / "week3" / "local-rerun" / "c101C5").glob("*.json")),
        RESULTS / "week3" / "local-rerun" / "c101C5" / "overview.png",
        "Local c101C5 method comparison",
    )

    plot_json_records(
        sorted((LOG / "week4" / "evrptw-four-instances").glob("*.json")),
        RESULTS / "week4" / "evrptw-four-instances" / "overview.png",
        "Four-instance EVRP-TW pilot",
    )
    plot_summary_csv(
        LOG / "week4" / "vns-ts-comparison" / "week4_summary.csv",
        RESULTS / "week4" / "vns-ts-comparison" / "overview.png",
        "Week 4 four-method comparison",
    )

    plot_summary_csv(
        LOG / "week5" / "four-methods-unlimited" / "four_methods_summary.csv",
        RESULTS / "week5" / "four-methods-unlimited" / "overview.png",
        "Week 5 comparison before shared fleet cap",
    )
    plot_best_route_petals(
        LOG / "week5" / "four-methods-unlimited" / "four_methods_summary.csv",
        RESULTS / "week5" / "four-methods-unlimited" / "best-route-petals.png",
        "Week 5 unlimited-fleet best routes",
    )
    plot_summary_csv(
        LOG / "week5" / "four-methods-vehicle-limit" / "four_methods_summary.csv",
        RESULTS / "week5" / "four-methods-vehicle-limit" / "overview.png",
        "Week 5 shared-fleet comparison",
    )
    plot_best_route_petals(
        LOG / "week5" / "four-methods-vehicle-limit" / "four_methods_summary.csv",
        RESULTS / "week5" / "four-methods-vehicle-limit" / "best-route-petals.png",
        "Week 5 vehicle-limited best routes",
    )
    plot_summary_csv(
        LOG / "week5" / "schneider-vns-ts-smoke" / "summary.csv",
        RESULTS / "week5" / "schneider-vns-ts-smoke" / "overview.png",
        "Schneider VNS/TS smoke runs",
    )
    plot_pomo_route_distribution(
        LOG / "week5" / "c101-21-pomo" / "c101_21_pomo_repair.json",
        RESULTS / "week5" / "c101-21-pomo" / "overview.png",
    )


if __name__ == "__main__":
    main()
