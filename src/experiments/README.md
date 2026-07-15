# Experiment Code

The experiment code is physically organized by responsibility. See [`INVENTORY.md`](INVENTORY.md) for the per-file status and purpose.

```text
experiments/
├── methods/       current solver implementations
│   ├── pyvrp/     PyVRP construction and EVRP-TW repair
│   ├── pomo/      POMO construction and repair pipelines
│   ├── vns_ts/    Schneider-style VNS/TS
│   └── ga/        checked py-ga wrapper
├── core/          loader, fleet policy, record schema, shared data helpers
├── checkers/      shared feasibility checker and route-checking CLI
├── runners/       maintained multi-experiment entry points
├── tools/         converters, aggregation, plotting, environment setup
├── tests/         fast regression tests
└── legacy/        historical and superseded code retained for reproduction
```

## Track B entry point

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_week5_track_b.ps1
```

The default skips POMO on 100 clients. Add `-IncludePomo100` to opt in.

## Fast verification

```powershell
$env:PYTHONPATH = "src\experiments"
.\.venv\Scripts\python.exe src\experiments\tests\evrptw_fleet_policy_self_test.py
.\.venv\Scripts\python.exe src\experiments\tests\evrptw_checker_self_test.py
.\.venv\Scripts\python.exe src\experiments\tests\evrptw_pipeline_self_test.py
.\.venv\Scripts\python.exe src\experiments\tests\vns_ts_schneider_self_test.py
```

Raw run evidence belongs in `src/log/`; readable tables and figures belong in `src/results/`. Generated caches and outputs do not belong in this directory.
