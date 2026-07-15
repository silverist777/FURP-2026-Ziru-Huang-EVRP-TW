# Week 5 Project Checkpoint


## 1. Current Project Status

The project now has a common evaluation pipeline for four EVRP-TW approaches: PyVRP with charging-station repair, a Schneider-style hybrid VNS/TS baseline, POMO with EVRP-TW repair, and py-ga-VRPTW with a shared feasibility checker.

This week I introduced a hard vehicle-number rule for every EVRP-TW instance:

```text
vehicle_limit = ceil((number_of_clients + number_of_charging_stations) / 4)
```

The charging-station count includes `S0`. The rule is applied by the shared instance loader and checked again after solving. I reran all four methods on the 5-, 10-, 15-, and 100-client instances, giving a complete 16-run matrix. The 100-client POMO run was executed separately because of its long runtime.

## 2. Evidence of Progress

### 2.1 Comparison results

| Instance | Method | Feasible | Distance | Vehicles / limit | Runtime (s) | Main diagnostic |
|---|---|---:|---:|---:|---:|---|
| c101C5 | PyVRP + repair | Yes | 264 | 2 / 2 | 10.014 | none |
| c101C5 | Hybrid VNS/TS | Yes | 259 | 2 / 2 | 10.708 | none |
| c101C5 | POMO + repair | Yes | 264 | 2 / 2 | 1.017 | none |
| c101C5 | py-ga + checker | No | 240 | 2 / 2 | 0.094 | 3 energy violations |
| c101C10 | PyVRP + repair | Yes | 387 | 3 / 4 | 10.151 | none |
| c101C10 | Hybrid VNS/TS | Yes | 392 | 3 / 4 | 64.957 | none |
| c101C10 | POMO + repair | No | 151 | 1 / 4 | 1.696 | 8 missing clients |
| c101C10 | py-ga + checker | No | 470 | 5 / 4 | 0.118 | 5 energy and 1 fleet violations |
| c103C15 | PyVRP + repair | Yes | 410 | 4 / 5 | 10.318 | none |
| c103C15 | Hybrid VNS/TS | Yes | 384 | 3 / 5 | 114.764 | none |
| c103C15 | POMO + repair | No | 348 | 3 / 5 | 2.977 | 4 missing clients |
| c103C15 | py-ga + checker | No | 558 | 4 / 5 | 0.139 | 12 energy violations |
| c101_21 | PyVRP + repair | Yes | 1055 | 12 / 31 | 263.780 | none |
| c101_21 | Hybrid VNS/TS | Yes | 1085 | 13 / 31 | 4674.126 | none |
| c101_21 | POMO + repair | No | 1749 | 24 / 31 | 4235.942 | 67 missing clients |
| c101_21 | py-ga + checker | No | 4644 | 51 / 31 | 0.615 | 52 energy and 1 fleet violations |

The complete readable table is in `src/results/week5/four-methods-vehicle-limit/summary.md`. The machine CSV and solver records are in `src/log/week5/four-methods-vehicle-limit/`, while `overview.png` provides the visual comparison.

### 2.2 Baseline comparison

PyVRP + repair is used as the consistent feasible reference because it produced feasible solutions for all four instances. Comparing only feasible outputs:

- VNS/TS is 1.9% shorter than PyVRP on c101C5 and 6.3% shorter on c103C15.
- PyVRP is 1.3% shorter than VNS/TS on c101C10 and 2.8% shorter on c101_21.
- POMO matches PyVRP on c101C5, but its shorter distances on c101C10, c103C15, and c101_21 are not valid improvements because clients are missing.
- py-ga distances are not treated as baseline improvements because every checked output violates at least the energy constraint.

### 2.3 Stability, bug fixes, and reproducibility

- All retained solver outputs pass through one checker for client coverage, duplicates, time windows, capacity, battery energy, and fleet size.
- A regression self-test verifies the new fleet-limit formula and confirms that an oversized requested fleet is capped.
- The 100-client VNS/TS rerun again produced a feasible distance of 1085 using 13 vehicles, providing a useful same-seed regression point after the fleet-policy change.
- Solver logs, routes, metrics, random seed, runtime, and violations are retained in JSON rather than reporting distance alone.
- `src/experiments/runners/run_week5_track_b.ps1` provides a single sequential reproduction entry point and documents the optional POMO 100-client run.

## 3. Problems and Limitations

1. The available POMO checkpoint was trained for CVRP rather than EVRP-TW. Its repair stage succeeds on c101C5 but loses customers under the tighter fleet policy on the 10-, 15-, and 100-client cases. On c101_21 it served only 33 of 100 customers.
2. The external py-ga implementation does not model charging-station insertion as a hard part of route construction and can exceed the fleet cap. The shared checker catches these failures, but the solver itself is not yet constraint-safe.
3. VNS/TS is computationally expensive: the c101_21 run took approximately 78 minutes, compared with about 4.4 minutes for PyVRP + repair.
4. The current comparison uses one seed and four instances. It is adequate for a pipeline checkpoint, but not yet sufficient for a statistical claim about stability or general performance.
5. There is no direct paper-value comparison yet because the current subset and evaluation pipeline must first be matched carefully to the published benchmark settings.

## 4. Next Step

1. Run a multi-seed stability study on the 5-, 10-, and 15-client instances, reporting feasible rate plus mean and standard deviation of distance and runtime.
2. Implement a fleet-aware, charging-aware repair/construction mechanism for POMO and py-ga, then rerun the same shared checker. The immediate success criterion is complete customer coverage with zero energy and fleet violations; distance optimization comes after feasibility.

The completed POMO c101_21 failure will be used as a regression case for the next fleet-aware repair implementation.

## Reproduction Command

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_week5_track_b.ps1
```

The default command skips POMO on 100 clients. Add `-IncludePomo100` to reproduce the complete 16-run matrix.
