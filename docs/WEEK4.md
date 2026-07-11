# Week 4 Lab Report: VNS/TS EVRP-TW Baseline Comparison

## Step 1: Define the Comparison Target

Week 4 compares runnable EVRP-TW/VRPTW baselines on two fixed test cases:

- `src/data/Solomon/C101.txt`
- `src/data/Holmberger/R1_10_9.txt`

Compared methods:

- `PyVRP VRPTW + EVRP-TW station repair`
- `Tabu-assisted VNS EVRP-TW`
- `POMO100 cluster + EVRP-TW repair`
- `py-ga-VRPTW custom + shared checker`

The key question is no longer only whether each method is theoretically suitable.
Week 4 first makes every baseline runnable on both 100-client and 1000-client
inputs, then compares the checked solution quality under the same validation
interface.

## Step 2: Address the Week 3 Limitation

Week 3 deliberately did not include `R1_10_9` in the fair three-way table.
The reason was a support mismatch:

- the retained `yd-kwon/POMO` checkpoint is a CVRP100 model, not a 1000-client model;
- the external `py-ga-VRPTW` code originally shipped Solomon-style 100-client JSON inputs;
- mixing a 1000-client Holmberger case into the Week 3 table would have compared
  unsupported method behavior rather than algorithm quality.

Week 4 resolves the runnability layer first:

- POMO is run as `1000-client instance -> 100-client sweep clusters -> POMO100 order -> greedy packing -> EVRP-TW repair -> checker`.
- GA gets a Solomon/Holmberger-to-`json_customize` converter plus a checked wrapper that replays the final GA route with the shared checker.
- PyVRP and VNS/TS read the same Solomon/Holmberger files through the shared project instance schema.

This is still not a perfect algorithmic apples-to-apples comparison: POMO is a
decomposition baseline rather than a true POMO1000 model, and GA is a generic
permutation GA with a hard time-window route splitter. It is, however, a fairer
Week 4 comparison because all final rows are produced by the same route checker.

## Step 3: Decide What to Record

For every checked JSON result, the experiment records:

| Field | Meaning |
|---|---|
| `feasible` | Shared checker feasibility result |
| `total_distance` | Replayed route distance from the shared checker |
| `vehicle_count` | Number of final routes |
| `runtime_seconds` | Wall-clock runtime of the method wrapper |
| `charging_count`, `charging_time` | Charging behavior after EVRP-TW repair |
| `missing_customers`, `duplicate_customers` | Customer coverage errors |
| `time_window_violations`, `capacity_violations`, `energy_violations` | Constraint violations |
| `timeout_or_unsupported_reason` | Empty for successful runs; filled for failed/unsupported rows |

Raw and cleaned outputs:

- Summary CSV: [week4_summary.csv](../src/results/week4_vns_ts_comparison/week4_summary.csv)
- Summary Markdown: [week4_summary.md](../src/results/week4_vns_ts_comparison/week4_summary.md)
- Result directory: [week4_vns_ts_comparison](../src/results/week4_vns_ts_comparison/)

Because `C101` and `R1_10_9` are VRPTW benchmark files without charging station
or battery fields, the converted project instances disable energy constraints.
Therefore `charging_count`, `charging_time`, and `energy_violations` are all
zero in this run.

## Step 4: Run the Experiment

Run date: 2026-07-08.

Environment:

- macOS CPU run.
- PyVRP / GA / VNS environment: `src/.venv_pyvrp`, Python `3.13.9`.
- PyVRP version: `0.13.4`.
- DEAP version used by `py-ga-VRPTW`: `1.4.4`.
- POMO environment: system `python3`, Python `3.9.6`, torch `2.8.0`, CUDA unavailable.
- `external/POMO` submodule commit: `d7c3d6e`.
- `py-ga-VRPTW` submodule commit: `b5598e4`.

Commands:

```bash
mkdir -p src/results/week4_vns_ts_comparison

src/.venv_pyvrp/bin/python src/experiments/PyVRP/solve_evrptw_pipeline.py \
  --solomon src/data/Solomon/C101.txt \
  --runtime-seconds 5 \
  --output src/results/week4_vns_ts_comparison/C101_pyvrp_repair.json

src/.venv_pyvrp/bin/python src/experiments/PyVRP/solve_evrptw_pipeline.py \
  --solomon src/data/Holmberger/R1_10_9.txt \
  --runtime-seconds 10 \
  --output src/results/week4_vns_ts_comparison/R1_10_9_pyvrp_repair.json

python3 src/experiments/pomo_decomposed_evrptw_pipeline.py \
  --solomon src/data/Solomon/C101.txt \
  --cluster-size 100 \
  --max-candidates 4 \
  --output src/results/week4_vns_ts_comparison/C101_pomo100_cluster_repair.json

python3 src/experiments/pomo_decomposed_evrptw_pipeline.py \
  --solomon src/data/Holmberger/R1_10_9.txt \
  --cluster-size 100 \
  --max-candidates 4 \
  --output src/results/week4_vns_ts_comparison/R1_10_9_pomo100_cluster_repair.json

src/.venv_pyvrp/bin/python src/experiments/vns_ts_evrptw_baseline.py \
  --solomon src/data/Solomon/C101.txt \
  --iterations 80 \
  --neighbors-per-iteration 20 \
  --output src/results/week4_vns_ts_comparison/C101_vns_ts.json

src/.venv_pyvrp/bin/python src/experiments/vns_ts_evrptw_baseline.py \
  --solomon src/data/Holmberger/R1_10_9.txt \
  --iterations 40 \
  --neighbors-per-iteration 10 \
  --output src/results/week4_vns_ts_comparison/R1_10_9_vns_ts.json

python3 src/experiments/GA/solomon_to_pyga_json.py src/data/Solomon/C101.txt
python3 src/experiments/GA/solomon_to_pyga_json.py src/data/Holmberger/R1_10_9.txt

src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw_checked.py \
  --solomon src/data/Solomon/C101.txt \
  --instance C101 \
  --ind-size 100 \
  --pop-size 80 \
  --generations 50 \
  --customize-data \
  --output src/results/week4_vns_ts_comparison/C101_pyga_checked.json \
  --output-csv src/results/week4_vns_ts_comparison/C101_pyga.csv \
  --output-log src/results/week4_vns_ts_comparison/C101_pyga.log

src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw_checked.py \
  --solomon src/data/Holmberger/R1_10_9.txt \
  --instance R1_10_9 \
  --ind-size 1000 \
  --pop-size 40 \
  --generations 10 \
  --customize-data \
  --output src/results/week4_vns_ts_comparison/R1_10_9_pyga_checked.json \
  --output-csv src/results/week4_vns_ts_comparison/R1_10_9_pyga.csv \
  --output-log src/results/week4_vns_ts_comparison/R1_10_9_pyga.log

python3 src/experiments/week4_collect_results.py \
  --results-dir src/results/week4_vns_ts_comparison
```

## Step 5: Organize Results Clearly

| Instance | Clients | Method | Feasible | Distance | Vehicles | Runtime (s) | Charging count | Charging time | Missing | Duplicate | Timeout / unsupported |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `C101` | 100 | PyVRP VRPTW + EVRP-TW station repair | yes | 829 | 10 | 5.032 | 0 | 0 | 0 | 0 | none |
| `C101` | 100 | POMO100 cluster + EVRP-TW repair | yes | 939 | 11 | 0.244 | 0 | 0 | 0 | 0 | none |
| `C101` | 100 | Tabu-assisted VNS EVRP-TW | yes | 1049 | 11 | 0.629 | 0 | 0 | 0 | 0 | none |
| `C101` | 100 | py-ga-VRPTW custom + shared checker | yes | 4697 | 53 | 0.437 | 0 | 0 | 0 | 0 | none |
| `R1_10_9` | 1000 | PyVRP VRPTW + EVRP-TW station repair | yes | 52252 | 95 | 12.083 | 0 | 0 | 0 | 0 | none |
| `R1_10_9` | 1000 | POMO100 cluster + EVRP-TW repair | yes | 74795 | 94 | 3.793 | 0 | 0 | 0 | 0 | none |
| `R1_10_9` | 1000 | Tabu-assisted VNS EVRP-TW | yes | 83323 | 103 | 7.322 | 0 | 0 | 0 | 0 | none |
| `R1_10_9` | 1000 | py-ga-VRPTW custom + shared checker | yes | 328681 | 620 | 1.540 | 0 | 0 | 0 | 0 | none |

All eight checked rows are feasible, serve every customer exactly once, and have
zero time-window, capacity, energy, missing-customer, and duplicate-customer
violations.

## Step 6: Analyze, Do Not Just Display

Feasibility:

- The main Week 4 improvement is runnability: every method now produces a checked
  solution on both `C101` and `R1_10_9`.
- There were no timeout or unsupported final rows in this bounded run.
- GA and POMO should still be interpreted carefully: GA feasibility comes from
  aggressive route splitting, while POMO100 support on `R1_10_9` comes from
  decomposition into 100-client clusters.

Distance:

- PyVRP is the best distance baseline on both cases: `829` on `C101` and `52252`
  on `R1_10_9`.
- POMO100 + repair is second-best by distance in both cases. On `R1_10_9`, it is
  feasible and uses one fewer vehicle than PyVRP, but its total distance is much
  longer: `74795` vs `52252`.
- VNS/TS is feasible but weaker than PyVRP in this budget: `1049` on `C101` and
  `83323` on `R1_10_9`.
- py-ga-VRPTW is feasible but not quality-competitive in this configuration:
  `4697` with 53 vehicles on `C101`, and `328681` with 620 vehicles on
  `R1_10_9`.

Runtime:

- POMO100 + repair is the fastest high-quality method in this run: `0.244s` on
  `C101` and `3.793s` on `R1_10_9`.
- PyVRP is slower because the run gives it fixed search budgets of 5s and 10s;
  elapsed wrapper time is `5.032s` and `12.083s`.
- VNS/TS is quick at these small search budgets, but the current neighborhood
  search does not yet beat PyVRP or POMO100 + repair in distance.
- GA appears fast here, but its very high vehicle count means the decoder is
  satisfying time windows mostly by fragmenting routes.

## Step 7: Discuss Failure Cases and Limitations

Limitation 1: These are VRPTW inputs, not full EVRP-TW charging benchmarks.

- `C101` and `R1_10_9` do not include charging stations or battery fields.
- The EVRP-TW checker fields remain present, but energy and charging metrics are
  disabled for this experiment.
- A true EVRP-TW charging comparison still needs Schneider-style instances or a
  controlled station/battery augmentation.

Limitation 2: POMO is still not a native large-scale EVRP-TW model.

- The retained checkpoint is `yd-kwon/POMO` CVRP100.
- Week 4 makes it runnable on `R1_10_9` through decomposition and repair.
- The result is useful as a hybrid baseline, but it should be named
  `POMO100 cluster + EVRP-TW repair`, not POMO1000 or an end-to-end EVRP-TW solver.

Limitation 3: GA is feasible but route-fragmented.

- The custom GA input path now supports `R1_10_9`.
- The checked GA output is feasible, but vehicle counts are very high.
- This confirms that runnability is solved, while quality still needs a better
  decoder, local search, or repair layer.

## Conclusion

Week 4 fixes the main Week 3 limitation by making all baselines runnable on both
`C101` and `R1_10_9`, including the 1000-client Holmberger case. The fair checked
comparison shows PyVRP remains the strongest distance baseline, POMO100 + repair
is the best speed/quality hybrid candidate, VNS/TS is feasible but needs stronger
search, and py-ga-VRPTW is now runnable at scale but currently achieves
feasibility through excessive route fragmentation.

The next experiment should move from VRPTW-only inputs to true EVRP-TW charging
instances, or augment these two cases with controlled charging stations and
battery parameters so `charging_count` and `charging_time` become meaningful
comparison metrics.
