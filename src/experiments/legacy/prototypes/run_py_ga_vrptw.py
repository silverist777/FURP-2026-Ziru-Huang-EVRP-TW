"""Run the external py-ga-VRPTW submodule GA.

This script is only a thin runner around `py-ga-VRPTW/gavrptw.core.run_gavrptw`;
the genetic algorithm implementation lives in the submodule.
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PY_GA_ROOT = REPO_ROOT / "py-ga-VRPTW"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run external py-ga-VRPTW GA.")
    parser.add_argument("--instance", default="C101", help="Instance name in py-ga-VRPTW/data/json.")
    parser.add_argument("--ind-size", type=int, default=100)
    parser.add_argument("--pop-size", type=int, default=80)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--unit-cost", type=float, default=8.0)
    parser.add_argument("--init-cost", type=float, default=100.0)
    parser.add_argument("--wait-cost", type=float, default=1.0)
    parser.add_argument("--delay-cost", type=float, default=1.5)
    parser.add_argument("--crossover-prob", type=float, default=0.85)
    parser.add_argument("--mutation-prob", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--export-csv", action="store_true")
    parser.add_argument(
        "--customize-data",
        action="store_true",
        help="Load py-ga-VRPTW/data/json_customize/<instance>.json.",
    )
    parser.add_argument(
        "--keep-generated-csv",
        action="store_true",
        help="Keep the CSV that py-ga-VRPTW writes under py-ga-VRPTW/results.",
    )
    parser.add_argument("--output-csv", type=Path, default=None)
    return parser.parse_args()


def expected_py_ga_csv(args: argparse.Namespace) -> Path:
    name = (
        f"{args.instance}_uC{args.unit_cost}_iC{args.init_cost}"
        f"_wC{args.wait_cost}_dC{args.delay_cost}_iS{args.ind_size}"
        f"_pS{args.pop_size}_cP{args.crossover_prob}"
        f"_mP{args.mutation_prob}_nG{args.generations}.csv"
    )
    return PY_GA_ROOT / "results" / name


def main() -> int:
    if not PY_GA_ROOT.exists() or not (PY_GA_ROOT / "gavrptw").exists():
        raise RuntimeError(
            "py-ga-VRPTW submodule is missing. Run: git submodule update --init py-ga-VRPTW"
        )

    sys.path.insert(0, str(PY_GA_ROOT))
    from gavrptw.core import run_gavrptw  # noqa: PLC0415

    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    run_gavrptw(
        instance_name=args.instance,
        unit_cost=args.unit_cost,
        init_cost=args.init_cost,
        wait_cost=args.wait_cost,
        delay_cost=args.delay_cost,
        ind_size=args.ind_size,
        pop_size=args.pop_size,
        cx_pb=args.crossover_prob,
        mut_pb=args.mutation_prob,
        n_gen=args.generations,
        export_csv=args.export_csv or args.output_csv is not None,
        customize_data=args.customize_data,
    )

    generated_csv = expected_py_ga_csv(args)
    if args.output_csv is not None:
        if not generated_csv.exists():
            raise RuntimeError(f"Expected py-ga-VRPTW CSV was not created: {generated_csv}")
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(generated_csv, args.output_csv)
        print(f"copied_csv: {args.output_csv}")
        if not args.keep_generated_csv:
            generated_csv.unlink()

    print("run_py_ga_vrptw_ok: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
