"""Render convergence/improvement records from experiment CSVs as line plots.

Supports both the repo comparison CSV JSON fields and the external
py-ga-VRPTW per-generation CSV format.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render convergence/improvement CSV columns as matplotlib curves."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--field",
        choices=("convergence_curve", "improvement_over_time"),
        default="convergence_curve",
    )
    parser.add_argument("--method", default=None, help="Optional method/method_name filter.")
    parser.add_argument("--instance", default=None, help="Optional instance/instance_name filter.")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def looks_like_py_ga_csv(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and {"generation", "max_fitness"}.issubset(rows[0])


def py_ga_curve(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    curve: list[dict[str, Any]] = []
    best_so_far: float | None = None
    start_best: float | None = None
    previous_best: float | None = None

    def generation_key(row: dict[str, str]) -> int:
        try:
            return int(row.get("generation", "0"))
        except ValueError:
            return 0

    for row in sorted(rows, key=generation_key):
        generation = generation_key(row)
        generation_best = None
        try:
            max_fitness = float(row.get("max_fitness", ""))
            if max_fitness > 0:
                generation_best = 1.0 / max_fitness
        except ValueError:
            generation_best = None

        if generation_best is not None:
            best_so_far = generation_best if best_so_far is None else min(best_so_far, generation_best)
            start_best = best_so_far if start_best is None else start_best

        if best_so_far is None or start_best is None:
            improvement_from_start = None
            improvement_from_previous = None
        else:
            improvement_from_start = start_best - best_so_far
            improvement_from_previous = 0.0 if previous_best is None else previous_best - best_so_far
            previous_best = best_so_far

        curve.append(
            {
                "generation": generation,
                "generation_best": generation_best,
                "best_objective": best_so_far,
                "improvement_from_start": improvement_from_start,
                "improvement_from_previous": improvement_from_previous,
            }
        )
    return curve


def matches(row: dict[str, str], method: str | None, instance: str | None) -> bool:
    if method is not None:
        row_method = row.get("method_name") or row.get("method") or row.get("algorithm") or ""
        if row_method != method:
            return False
    if instance is not None:
        row_instance = row.get("instance_name") or row.get("instance") or ""
        if row_instance != instance:
            return False
    return True


def parse_curve(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def numeric_series(curve: list[dict[str, Any]], key: str) -> list[float | None]:
    values: list[float | None] = []
    for point in curve:
        value = point.get(key)
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            values.append(None)
    return values


def generations(curve: list[dict[str, Any]]) -> list[int]:
    xs: list[int] = []
    for idx, point in enumerate(curve, start=1):
        try:
            xs.append(int(point.get("generation", idx)))
        except (TypeError, ValueError):
            xs.append(idx)
    return xs


def plot_curve(
    curve: list[dict[str, Any]],
    field: str,
    title: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.2))

    if not curve:
        ax.text(
            0.5,
            0.5,
            "No curve data captured",
            ha="center",
            va="center",
            fontsize=14,
            transform=ax.transAxes,
        )
        ax.set_axis_off()
    else:
        xs = generations(curve)
        if field == "convergence_curve":
            plot_series(ax, xs, numeric_series(curve, "best_objective"), "best objective")
            plot_series(
                ax,
                xs,
                numeric_series(curve, "generation_best"),
                "generation best",
                linestyle="--",
            )
            ax.set_ylabel("Objective value")
        else:
            plot_series(
                ax,
                xs,
                numeric_series(curve, "improvement_from_start"),
                "improvement from start",
            )
            plot_series(
                ax,
                xs,
                numeric_series(curve, "improvement_from_previous"),
                "improvement from previous",
                linestyle="--",
            )
            ax.set_ylabel("Improvement")

        ax.set_xlabel("Generation")
        ax.grid(True, alpha=0.3)
        ax.legend()

    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def plot_series(
    ax,
    xs: list[int],
    ys: list[float | None],
    label: str,
    linestyle: str = "-",
) -> None:
    clean_x = [x for x, y in zip(xs, ys) if y is not None]
    clean_y = [y for y in ys if y is not None]
    if clean_x and clean_y:
        ax.plot(clean_x, clean_y, marker="o", linewidth=2, linestyle=linestyle, label=label)


def safe_name(value: str) -> str:
    value = value.strip() or "unknown"
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("_") or "unknown"


def main() -> None:
    args = parse_args()
    input_rows = read_rows(args.input_csv)
    output_dir = args.output_dir or args.input_csv.with_suffix("").parent / "progress_plots"
    written: list[Path] = []

    if looks_like_py_ga_csv(input_rows):
        instance = args.instance or args.input_csv.stem
        method = "py-ga-VRPTW"
        curve = py_ga_curve(input_rows)
        stem = f"{safe_name(instance)}_{safe_name(method)}_{args.field}"
        title = f"{args.field}: {method} on {instance}"
        png_path = output_dir / f"{stem}.png"
        plot_curve(curve, args.field, title, png_path)
        written.append(png_path)
        print("render_progress_plots_ok: True")
        for path in written:
            print(path)
        return

    rows = [row for row in input_rows if matches(row, args.method, args.instance)]
    if not rows:
        raise RuntimeError("No matching rows found.")

    for idx, row in enumerate(rows, start=1):
        method = row.get("method_name") or row.get("method") or row.get("algorithm") or "unknown_method"
        instance = row.get("instance_name") or row.get("instance") or f"row_{idx}"
        curve = parse_curve(row.get(args.field))
        stem = f"{idx:02d}_{safe_name(instance)}_{safe_name(method)}_{args.field}"
        title = f"{args.field}: {method} on {instance}"
        png_path = output_dir / f"{stem}.png"
        plot_curve(curve, args.field, title, png_path)
        written.append(png_path)

    print("render_progress_plots_ok: True")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
