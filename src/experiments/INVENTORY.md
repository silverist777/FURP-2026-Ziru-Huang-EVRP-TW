# Experiment Code Inventory

## Methods

| Status | File | Purpose |
|---|---|---|
| Maintained | `methods/pyvrp/solve_evrptw_pipeline.py` | PyVRP VRPTW construction and result export |
| Maintained repair | `methods/pyvrp/evrptw_v3_repair.py` | partial-recharge label setting and route splitting |
| Maintained | `methods/pomo/pomo_evrptw_repair_pipeline.py` | POMO construction followed by EVRP-TW repair |
| Specialized | `methods/pomo/pomo_decomposed_evrptw_pipeline.py` | cluster/decomposition path for large instances |
| Maintained | `methods/vns_ts/vns_ts_evrptw_baseline.py` | VNS/TS CLI and result export |
| Maintained | `methods/vns_ts/schneider_vns_ts.py` | VNS/TS search implementation |
| Maintained | `methods/ga/run_py_ga_vrptw_checked.py` | py-ga wrapper with shared post-solve validation |

## Core and checking

| Status | File | Purpose |
|---|---|---|
| Shared | `core/instance_loader.py` | authoritative instance loader |
| Shared | `core/evrptw_fleet_policy.py` | common vehicle-number policy |
| Shared | `core/experiment_record.py` | experiment metadata schema |
| Shared | `core/vrptw_support.py` | Solomon parsing and VRPTW data helpers |
| Shared checker | `checkers/feasibility_checker.py` | coverage, time-window, capacity, energy, and fleet validation |
| Checker CLI | `checkers/check_explicit_routes.py` | validates manually supplied routes |

## Runners, tools, and tests

| Category | Files |
|---|---|
| Runner | `runners/run_week5_track_b.ps1` |
| Aggregation and plots | `tools/week4_collect_results.py`, `tools/build_weekly_visualizations.py`, `tools/render_progress_plots.py` |
| Conversion | `tools/solomon_to_project_instance.py`, `tools/solomon_to_pyga_json.py`, `methods/pyvrp/parse_schneider_instance.py` |
| Environment | `tools/setup_pomo_cuda_env.ps1` |
| Tests | all four scripts under `tests/` |

`week4_collect_results.py` retains its historical filename but is the current general JSON result collector. `core/vrptw_support.py` and the decomposed POMO pipeline are retained because they still have defined uses; they are not abandoned code.

## Legacy

Historical CVRP/VRPTW comparisons and superseded prototypes are isolated under [`legacy/`](legacy/README.md). They are kept for reproducibility and are not imported by the current Track B runner.
