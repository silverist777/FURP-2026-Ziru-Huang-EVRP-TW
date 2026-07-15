# EVRP-TW Experiment Guide

This directory contains the implementation and experiment artifacts for comparing four approaches on electric vehicle routing with time windows (EVRP-TW):

- PyVRP VRPTW followed by charging-station repair;
- a Schneider-style hybrid VNS/TS baseline;
- yd-kwon POMO CVRP inference followed by EVRP-TW repair;
- py-ga-VRPTW followed by the shared feasibility checker.

## Common experiment policy

Every EVRP-TW run uses the same hard fleet limit:

```text
vehicle_limit = ceil((number_of_clients + number_of_charging_stations) / 4)
```

The station count includes station `S0`. The loader applies this rule even when a larger value is supplied, and the shared checker reports `vehicle_limit_violations` together with coverage, time-window, capacity, and energy violations.

## Environment

Run commands from the repository root on Windows PowerShell. The checked-in scripts expect the virtual environment at `.venv\Scripts\python.exe`, the POMO submodule at `external\POMO`, and py-ga-VRPTW at `py-ga-VRPTW`.

```powershell
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\tests\evrptw_fleet_policy_self_test.py
```

## Reproduce the Track B comparison

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_week5_track_b.ps1
```

The default run executes 15 experiments: all four methods on 5, 10, and 15 clients, and PyVRP, VNS/TS, and py-ga on the 100-client instance. POMO on 100 clients is intentionally skipped to control runtime. To include it:

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_week5_track_b.ps1 -IncludePomo100
```

The 100-client VNS/TS run took about 78 minutes on the current machine, so the full script should be run sequentially and left uninterrupted.

Raw outputs are written to `src/log/week5/four-methods-vehicle-limit/`. Each solver produces a JSON record, console logs are stored under `_run_logs/`, and `week4_collect_results.py` rebuilds the machine CSV there. The readable summary and visualizations are written to `src/results/week5/four-methods-vehicle-limit/`.

Infeasible outputs are retained deliberately. A distance from an infeasible solution must not be compared with a feasible baseline as if it were a valid improvement.

## Directory map

| Path | Contents | Detailed guide |
|---|---|---|
| `data/` | benchmark instances and small test inputs | [`data/README.md`](data/README.md) |
| `experiments/` | solvers, checkers, conversions, and runners | [`experiments/README.md`](experiments/README.md) |
| `log/` | raw solver records, machine tables, and console logs | [`log/README.md`](log/README.md) |
| `results/` | weekly summaries and data visualizations | [`results/README.md`](results/README.md) |

The latest project narrative is [`../docs/week05_checkpoint.md`](../docs/week05_checkpoint.md).
The longer per-method command reference is
[`../docs/src_data_method_run_tutorials.md`](../docs/src_data_method_run_tutorials.md).
