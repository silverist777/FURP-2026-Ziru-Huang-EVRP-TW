"""Collect Week 4 solver JSON outputs into comparison tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = REPO_ROOT / "src" / "results" / "week4_vns_ts_comparison"


FIELDS = [
    "instance",
    "clients",
    "method",
    "status",
    "feasible",
    "total_distance",
    "vehicle_count",
    "runtime_seconds",
    "served_customers",
    "missing_customers",
    "duplicate_customers",
    "time_window_violations",
    "capacity_violations",
    "energy_violations",
    "charging_count",
    "charging_time",
    "source_file",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Week 4 JSON solution outputs into CSV/Markdown tables."
    )
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    return parser.parse_args()


def row_from_solution(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    metrics = data.get("metrics", {})
    solver = data.get("solver", {})
    source = data.get("source", {})
    record = data.get("experiment_record", {})
    return {
        "instance": source.get("instance") or record.get("instance_name") or path.stem,
        "clients": record.get("instance_size") or metrics.get("served_customers", ""),
        "method": solver.get("method_name")
        or record.get("method_name")
        or solver.get("baseline", ""),
        "status": data.get("status", ""),
        "feasible": metrics.get("feasible", ""),
        "total_distance": metrics.get("total_distance", ""),
        "vehicle_count": metrics.get("vehicle_count", ""),
        "runtime_seconds": solver.get("elapsed_runtime_seconds")
        or record.get("runtime_seconds", ""),
        "served_customers": metrics.get("served_customers", ""),
        "missing_customers": metrics.get("missing_customers", ""),
        "duplicate_customers": metrics.get("duplicate_customers", ""),
        "time_window_violations": metrics.get("time_window_violations", ""),
        "capacity_violations": metrics.get("capacity_violations", ""),
        "energy_violations": metrics.get("energy_violations", ""),
        "charging_count": metrics.get("charging_count", ""),
        "charging_time": metrics.get("charging_time", ""),
        "source_file": str(path),
    }


def collect_rows(results_dir: Path) -> list[dict]:
    rows = [
        row_from_solution(path)
        for path in sorted(results_dir.glob("*.json"))
        if path.is_file()
    ]
    rows.sort(key=lambda row: (str(row["instance"]), str(row["method"])))
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        file.write("# Week 4 EVRPTW Baseline Comparison Results\n\n")
        if not rows:
            file.write("No JSON result files found yet.\n")
            return
        file.write(
            "| instance | clients | method | feasible | distance | vehicles | runtime_s | served | missing | duplicate |\n"
        )
        file.write("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for row in rows:
            file.write(
                "| {instance} | {clients} | {method} | {feasible} | {total_distance} | "
                "{vehicle_count} | {runtime_seconds} | {served_customers} | "
                "{missing_customers} | {duplicate_customers} |\n".format(**row)
            )


def main() -> int:
    args = parse_args()
    rows = collect_rows(args.results_dir)
    csv_path = args.output_csv or (args.results_dir / "week4_summary.csv")
    md_path = args.output_md or (args.results_dir / "week4_summary.md")
    write_csv(rows, csv_path)
    write_markdown(rows, md_path)
    print(f"rows: {len(rows)}")
    print(f"csv: {csv_path}")
    print(f"markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
