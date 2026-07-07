# Week 4 Lab Report: EVRPTW Baseline Comparison Plan and Implementation

## Goal

Week 4 extends the Week 3 comparison from 100-customer-only experiments to a fixed two-case setup:

- `src/data/Solomon/C101.txt`
- `src/data/Holmberger/R1_10_9.txt`

The main addition is a new method, `Tabu-assisted VNS EVRP-TW`, compared against:

- `PyVRP VRPTW + EVRP-TW repair`
- `py-ga-VRPTW + custom Solomon/Holmberger JSON`
- `POMO100 cluster + EVRP-TW repair`

`C101` and `R1_10_9.txt` are Solomon/Holmberger VRPTW files. The project converts them into the shared project schema and runs them through the same route repair/checker interface. Since these files do not contain charging stations or battery parameters, energy constraints are disabled for these two cases.

## Week 3 Limitation Addressed

Week 3 left `R1_10_9.txt` as a failure/limitation case because:

- `py-ga-VRPTW` only shipped 100-customer Solomon JSON files.
- the retained `yd-kwon/POMO` checkpoint is CVRP100.

Week 4 addresses this before comparison:

- GA now has a generic Solomon/Holmberger to `py-ga-VRPTW/data/json_customize` converter.
- POMO now uses `1000-client instance -> sweep clusters of 100 -> POMO100 candidate order -> insertion greedy full pack -> EVRP-TW repair -> checker`.
- PyVRP now accepts `--solomon` directly for both `C101` and `R1_10_9.txt`.

## Implemented Scripts

- `src/experiments/solomon_to_project_instance.py`
  - converts Solomon/Holmberger VRPTW text files into the project JSON schema.
- `src/experiments/GA/solomon_to_pyga_json.py`
  - converts any contiguous Solomon/Holmberger instance into py-ga custom JSON, including the full `1001 x 1001` matrix for `R1_10_9`.
- `src/experiments/pomo_decomposed_evrptw_pipeline.py`
  - decomposes large instances into CVRP100-sized clusters, runs POMO per cluster, then repairs/checks the merged full solution.
- `src/experiments/vns_ts_evrptw_baseline.py`
  - new Week 4 baseline: insertion construction plus tabu-assisted VNS neighborhoods, validated by the shared checker.
- `src/experiments/week4_collect_results.py`
  - collects JSON solver outputs into `week4_summary.csv` and `week4_summary.md`.

## Smoke Validation

Smoke tests run on July 7, 2026:

| Case | Method | Setting | Feasible | Served | Vehicles | Distance |
|---|---|---|---:|---:|---:|---:|
| `C101` | PyVRP + repair | 1s | yes | 100 | 10 | 829 |
| `C101` | VNS/TS EVRP-TW | 0 iterations | yes | 100 | 11 | 1049 |
| `C101` | POMO100 cluster + repair | cluster 20, 1 candidate | yes | 100 | 12 | 1210 |
| `R1_10_9` | PyVRP + repair | 1s | yes | 1000 | 107 | 56537 |
| `R1_10_9` | VNS/TS EVRP-TW | 0 iterations | yes | 1000 | 103 | 83323 |
| `R1_10_9` | POMO100 cluster + repair | cluster 100, 1 candidate | yes | 1000 | 93 | 76863 |

GA custom-input smoke:

- `C101` custom JSON generated with 100 customers and `101 x 101` distance matrix.
- `R1_10_9` custom JSON generated with 1000 customers and `1001 x 1001` distance matrix.
- `run_py_ga_vrptw.py --customize-data` successfully read the custom `C101` JSON in a 0-generation smoke test.

## Formal Experiment Commands

Run from repository root.

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
```

Prepare GA custom data:

```bash
python3 src/experiments/GA/solomon_to_pyga_json.py src/data/Solomon/C101.txt
python3 src/experiments/GA/solomon_to_pyga_json.py src/data/Holmberger/R1_10_9.txt
```

Run GA with bounded budgets:

```bash
src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw.py \
  --instance C101 \
  --ind-size 100 \
  --pop-size 80 \
  --generations 50 \
  --customize-data \
  --output-csv src/results/week4_vns_ts_comparison/C101_pyga.csv

src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw.py \
  --instance R1_10_9 \
  --ind-size 1000 \
  --pop-size 40 \
  --generations 10 \
  --customize-data \
  --output-csv src/results/week4_vns_ts_comparison/R1_10_9_pyga.csv
```

Collect JSON result tables:

```bash
python3 src/experiments/week4_collect_results.py \
  --results-dir src/results/week4_vns_ts_comparison
```

## Notes

- POMO is not retrained. The method name must remain `POMO100 cluster + EVRP-TW repair`.
- `R1_10_9` POMO support is a decomposition baseline, not a true POMO1000 model.
- GA support is input-scale support. Full `R1_10_9` GA runtime may still be poor and should be reported as timeout if it exceeds the chosen budget.
- All final comparison rows should be based on shared checker outputs, not raw solver claims.
