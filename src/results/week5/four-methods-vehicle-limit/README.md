# Vehicle-Limited EVRP-TW Comparison

These results are the Week 5 Track B rerun with seed 1 and the common fleet rule `ceil((clients + charging stations) / 4)`. The completed matrix contains 16 solver records: four methods on four instances.

## What each experiment tests

| Method | Role in the comparison | EVRP-TW handling |
|---|---|---|
| PyVRP + repair | strong feasible baseline | solves the VRPTW routing core, then inserts charging stations with partial-recharge label setting |
| Hybrid VNS/TS | problem-specific baseline | searches routes directly with capacity, time-window, battery, and charging-station logic |
| POMO + repair | learned construction baseline | uses a pretrained CVRP policy, then checks and repairs the route for EVRP-TW constraints |
| py-ga + checker | genetic baseline and failure diagnostic | constructs VRPTW routes; the shared checker exposes unsupported battery and fleet behavior |

## Result summary

| Instance | Fleet cap | PyVRP | VNS/TS | POMO | py-ga |
|---|---:|---|---|---|---|
| c101C5 | 2 | feasible, 264, 2 vehicles | feasible, 259, 2 vehicles | feasible, 264, 2 vehicles | infeasible: 3 energy violations |
| c101C10 | 4 | feasible, 387, 3 vehicles | feasible, 392, 3 vehicles | infeasible: 8 missing clients | infeasible: 5 energy + 1 fleet violations |
| c103C15 | 5 | feasible, 410, 4 vehicles | feasible, 384, 3 vehicles | infeasible: 4 missing clients | infeasible: 12 energy violations |
| c101_21 | 31 | feasible, 1055, 12 vehicles | feasible, 1085, 13 vehicles | infeasible: 67 missing clients, 24 vehicles | infeasible: 52 energy + 1 fleet violations |

Numbers in the method cells are total distance and vehicles used. Only feasible rows are valid for objective comparison. Among feasible solutions, VNS/TS improves on PyVRP by 1.9% on c101C5 and 6.3% on c103C15; PyVRP is 1.3% shorter on c101C10 and 2.8% shorter on c101_21.

The machine-readable table and individual JSON records are in [`../../../log/week5/four-methods-vehicle-limit/`](../../../log/week5/four-methods-vehicle-limit/). The readable full table is [`summary.md`](summary.md), and [`overview.png`](overview.png) visualizes distance, runtime, vehicles, and infeasibility. The `reason` column is reserved for timeout or unsupported-condition text; blank values mean that the detailed failure is already represented by the numeric violation columns.

## Reproduction

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\runners\run_week5_track_b.ps1
```

The existing POMO 100-client result was produced with `-IncludePomo100`. Use that switch when reproducing the complete 16-run matrix.
