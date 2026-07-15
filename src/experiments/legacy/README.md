# Legacy Experiment Code

These scripts are retained to reproduce older Week 1–3 reports or to preserve superseded prototypes. They are not part of the current Week 5 EVRP-TW pipeline and should not be used as the default implementation.

## `cvrp/`

Historical CVRP/VRPTW benchmarks that do not implement the complete EVRP-TW constraint set:

- `cvrp_method_comparison.py`: Week 2 GA/PyVRP/POMO pure-CVRP comparison.
- `method_comparison_table.py`: shared cases and PyVRP table used by the old comparisons.
- `ydkwon_pomo_method_comparison.py`: old POMO-only comparison and time-window checking.
- `week3_pyga_pyvrp_pomo.py`: Week 3 multi-method experiment orchestrator.
- `ga_cvrp_baseline.py`: standalone permutation GA for CVRP.
- `evaluate_solomon_pyvrp.py`: plain Solomon VRPTW evaluation without battery constraints.

## `prototypes/`

Superseded or unchecked implementations:

- `evrptw_repair.py`: earlier repair algorithm, superseded by `PyVRP/evrptw_v3_repair.py`.
- `run_py_ga_vrptw.py`: unchecked py-ga wrapper, superseded by `GA/run_py_ga_vrptw_checked.py`.
- `smoke_test_pyvrp.py` and `scale_up_test.py`: early manual smoke scripts, superseded by the self-tests.

## `runners/`

Temporary one-off PowerShell scripts used while the unlimited and vehicle-limited experiment batches were being completed. They are preserved as run history but superseded by `../runners/run_week5_track_b.ps1`.

Legacy files are archived, not deleted. If an old report must be reproduced, run from the repository root with `PYTHONPATH=src;src/experiments` and verify its original assumptions first.
