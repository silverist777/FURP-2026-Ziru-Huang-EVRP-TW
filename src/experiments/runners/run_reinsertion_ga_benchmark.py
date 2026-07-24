"""Run RI-GA against cases from the current three-group benchmark config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = (
    REPO_ROOT / "src" / "experiments" / "configs" / "week5_three_group_stability.json"
)
PIPELINE = (
    REPO_ROOT
    / "src"
    / "experiments"
    / "methods"
    / "ga"
    / "run_reinsertion_ga_evrptw.py"
)
VALIDATOR = (
    REPO_ROOT
    / "src"
    / "experiments"
    / "tools"
    / "validate_stability_result.py"
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "src" / "log" / "week5" / "reinsertion-ga-benchmark",
    )
    parser.add_argument("--groups", nargs="+", default=["C", "R", "RC"])
    parser.add_argument("--sizes", nargs="+", type=int, default=[5, 10, 15, 100])
    parser.add_argument("--population-size", type=int, default=80)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--repair-candidates", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def selected_cases(config, groups, sizes):
    group_set = set(groups)
    size_set = set(sizes)
    for group in config["groups"]:
        if group["id"] not in group_set:
            continue
        for case in group["cases"]:
            if case["clients"] in size_set:
                yield group["id"], case


def run_command(command, *, cwd, dry_run):
    print(" ".join(str(part) for part in command), flush=True)
    if dry_run:
        return 0
    return subprocess.run(command, cwd=cwd, check=False).returncode


def main():
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    seed = config["seed"] if args.seed is None else args.seed
    cases = list(selected_cases(config, args.groups, args.sizes))
    if not cases:
        raise ValueError("No benchmark cases matched --groups and --sizes.")

    summary = []
    for group_id, case in cases:
        instance_path = REPO_ROOT / case["path"]
        case_dir = args.output_dir / group_id / case["instance"] / f"seed-{seed:04d}"
        result_path = case_dir / "result.json"
        checker_path = case_dir / "checker.json"
        job_id = f"{group_id}-{case['instance']}-reinsertion_ga-seed-{seed:04d}"
        solve_command = [
            sys.executable,
            str(PIPELINE),
            "--schneider",
            str(instance_path),
            "--vehicles",
            str(case["max_vehicles"]),
            "--population-size",
            str(args.population_size),
            "--generations",
            str(args.generations),
            "--repair-candidates",
            str(args.repair_candidates),
            "--seed",
            str(seed),
            "--output",
            str(result_path),
        ]
        solve_code = run_command(solve_command, cwd=REPO_ROOT, dry_run=args.dry_run)
        if args.dry_run:
            continue

        validate_command = [
            sys.executable,
            str(VALIDATOR),
            "--schneider",
            str(instance_path),
            "--result",
            str(result_path),
            "--output",
            str(checker_path),
            "--expected-instance",
            case["instance"],
            "--expected-clients",
            str(case["clients"]),
            "--expected-stations",
            str(case["stations"]),
            "--expected-vehicles",
            str(case["max_vehicles"]),
            "--expected-seed",
            str(seed),
            "--group",
            group_id,
            "--method",
            "reinsertion_ga",
            "--job-id",
            job_id,
        ]
        run_command(validate_command, cwd=REPO_ROOT, dry_run=False)
        checker = json.loads(checker_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        summary.append(
            {
                "group": group_id,
                "instance": case["instance"],
                "clients": case["clients"],
                "solve_exit_code": solve_code,
                "strict_feasible": checker["strict_feasible"],
                "validation_status": checker["validation_status"],
                "failure_class": checker["failure_class"],
                "distance": result.get("metrics", {}).get("total_distance"),
                "vehicles": result.get("metrics", {}).get("vehicle_count"),
                "runtime_seconds": result.get("solver", {}).get(
                    "elapsed_runtime_seconds"
                ),
                "result": str(result_path),
                "checker": str(checker_path),
            }
        )

    if args.dry_run:
        print(f"Dry run: {len(cases)} cases selected.")
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    feasible = sum(item["strict_feasible"] for item in summary)
    print(f"RI-GA benchmark: {feasible}/{len(summary)} strict-feasible")
    print(f"Summary: {summary_path}")
    return 0 if feasible == len(summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
