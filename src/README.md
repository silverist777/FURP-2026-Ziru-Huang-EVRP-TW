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

## RouteFinder VRPTW baseline

RouteFinder 0.4.0 is deployed as a pinned submodule under `src/routefinder`.
Its source, isolated virtual environment, downloaded checkpoints, and official
datasets all remain inside that directory. Checkpoints, datasets, and the
virtual environment are ignored by the RouteFinder repository and are not
committed.

The deployed environment uses:

- Python 3.12;
- PyTorch 2.11.0 with CUDA 12.8;
- RL4CO 0.6.0;
- TorchRL 0.6.0;
- TensorDict 0.6.0.

TorchRL and TensorDict are pinned because newer releases remove the
`CompositeSpec` symbol referenced by the official checkpoint. The PyTorch
compatibility variable in the runner is required because the trusted official
checkpoint predates the `weights_only=True` loading default.

Run the verified 50-node VRPTW GPU smoke test from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File src\run_routefinder_smoke.ps1
```

The deployment validation on the current RTX 4070 evaluated 1,000 official
VRPTW instances and reported:

```text
VRPTW | Cost: 16.365 | Gap: 2.078% | Inference time: 2.909 s
```

To rebuild the isolated environment, create `src/routefinder/.venv` with
Python 3.12 and install from `src`:

```powershell
.\routefinder\.venv\Scripts\python.exe -m pip install -r requirements-routefinder.txt
.\routefinder\.venv\Scripts\python.exe .\routefinder\scripts\download_hf.py
```

RouteFinder currently serves as a VRPTW neural baseline. Its official
environment does not model battery energy, charging stations, or charging
time, so EVRP-TW use requires a separate environment and training extension.

### Run the existing Week 5 benchmark with RouteFinder

The RouteFinder adapter uses the same four Schneider instances, fleet policy,
partial-recharge repair, independent checker, and result collector as the
existing Track B benchmark. From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_routefinder_week5_benchmark.ps1
```

For a fast single-instance check:

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_routefinder_week5_benchmark.ps1 -Cases c101C5
```

The default protocol uses eight geometric augmentations, up to four distinct
RouteFinder candidates, the 50-node checkpoint for the 5/10/15-client cases,
and the 100-node checkpoint for `c101_21`. The repair-aware greedy packing
variant is limited to at most 50 clients because applying the full label-setting
repair after every insertion is prohibitively slow at 100 clients.

RouteFinder raw records are written to
`src/log/week5/routefinder-vehicle-limit/`. A combined table containing the
existing four methods and RouteFinder is written to
`src/results/week5/five-methods-vehicle-limit/`.

The official RouteFinder environment has no fleet-size action constraint.
Consequently, a run may finish normally with `status=unsolved` and
`vehicle_limit_exceeded` when the model opens more routes than the shared FURP
fleet limit. This is a benchmark result rather than a runner failure.
