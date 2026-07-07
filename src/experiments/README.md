# Experiments

This directory contains the runnable EVRP-TW experiment scripts.

Current scope:

1. Build PyVRP-based VRPTW baselines.
2. Load shared JSON instance data.
3. Convert a small Schneider-style text sample into the project JSON schema.
4. Replay explicit EVRP-TW routes with customers and charging stations.
5. Report feasibility metrics: customer coverage, capacity, time windows, energy, charging count, and charging time.
6. Use a pretrained CVRP-POMO checkpoint as a candidate-route source before EVRP-TW repair.
7. Run Week 4 scale-up baselines on Solomon/Holmberger `C101` and `R1_10_9`.

The PyVRP baseline stage is CPU-only. The POMO hybrid path uses PyTorch for pretrained checkpoint inference, but it does not retrain a neural model. PyVRP is used as a classical VRPTW baseline, while full EVRP-TW feasibility is checked by the independent route replay code.

yd-kwon/POMO CUDA preparation is handled by `setup_pomo_cuda_env.ps1`. It checks whether the isolated Python environment can run PyTorch on the NVIDIA GPU; it is not part of the EVRP-TW CPU baseline.

## Scripts

- `smoke_test_pyvrp.py`: small PyVRP VRPTW smoke test.
- `scale_up_test.py`: larger PyVRP VRPTW baseline test.
- `feasibility_checker.py`: independent feasibility checker for route replay.
- `instance_loader.py`: shared loader for the project JSON schema.
- `parse_schneider_instance.py`: converts Schneider-style EVRP-TW text data to JSON.
- `solomon_to_project_instance.py`: converts Solomon/Holmberger VRPTW text data to the shared project schema.
- `check_explicit_routes.py`: checks explicit named routes containing customers and charging stations.
- `evrptw_repair.py`: inserts charging stations into fixed customer-order routes.
- `solve_evrptw_pipeline.py`: solves EVRP-TW with PyVRP customer routes plus station repair.
- `pomo_evrptw_repair_pipeline.py`: uses the pretrained yd-kwon CVRP-POMO checkpoint to propose customer routes, then applies time-window and battery-aware EVRP-TW repair.
- `pomo_decomposed_evrptw_pipeline.py`: decomposes large cases into 100-customer POMO subproblems, then repairs/checks the merged full solution.
- `vns_ts_evrptw_baseline.py`: Week 4 tabu-assisted VNS baseline with checker-validated outputs.
- `week4_collect_results.py`: collects Week 4 JSON outputs into CSV and Markdown tables.
- `evrptw_checker_self_test.py`: parser and checker regression self-test.
- `evrptw_pipeline_self_test.py`: parser, repair, split, and unsolved-route regression tests.
- `setup_pomo_cuda_env.ps1`: Windows helper for creating/checking the isolated POMO CUDA environment.

## Common Commands

Run from the repository root:

```bash
src/.venv_pyvrp/bin/python -m py_compile src/experiments/*.py
src/.venv_pyvrp/bin/python src/experiments/smoke_test_pyvrp.py
src/.venv_pyvrp/bin/python src/experiments/scale_up_test.py
```

Convert the bundled Schneider-style sample:

```bash
src/.venv_pyvrp/bin/python src/experiments/parse_schneider_instance.py \
  src/data/schneider_sample.txt \
  --output src/results/schneider_sample_converted.json \
  --vehicles 2 \
  --runtime-seconds 1
```

Check an explicit EVRP-TW route:

```bash
src/.venv_pyvrp/bin/python src/experiments/check_explicit_routes.py \
  --instance src/results/schneider_sample_converted.json \
  --routes src/data/explicit_routes_sample.json
```

Run the parser/checker self-test:

```bash
src/.venv_pyvrp/bin/python src/experiments/evrptw_checker_self_test.py
```

Run the EVRP-TW solving pipeline on an external Schneider benchmark file:

```bash
src/.venv_pyvrp/bin/python src/experiments/solve_evrptw_pipeline.py \
  --schneider /Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt \
  --vehicles 2 \
  --runtime-seconds 2 \
  --output src/results/c101C5_solution.json \
  --fail-on-unsolved
```

Run the pretrained POMO + EVRP-TW repair pipeline. Use a Python environment with `torch` installed; the PyVRP-only venv may not include it.

```bash
python3 src/experiments/pomo_evrptw_repair_pipeline.py \
  --instance src/results/schneider_sample_converted.json \
  --output src/results/schneider_sample_pomo_repair_solution.json \
  --fail-on-unsolved
```

Run the Week 4 POMO100 decomposition baseline on the 1000-customer Holmberger case:

```bash
python3 src/experiments/pomo_decomposed_evrptw_pipeline.py \
  --solomon src/data/Holmberger/R1_10_9.txt \
  --cluster-size 100 \
  --max-candidates 4 \
  --output src/results/week4_vns_ts_comparison/R1_10_9_pomo100_cluster_repair.json
```

Run the Week 4 VNS/TS baseline:

```bash
src/.venv_pyvrp/bin/python src/experiments/vns_ts_evrptw_baseline.py \
  --solomon src/data/Holmberger/R1_10_9.txt \
  --iterations 40 \
  --neighbors-per-iteration 10 \
  --output src/results/week4_vns_ts_comparison/R1_10_9_vns_ts.json
```

Prepare py-ga custom JSON for the same large case:

```bash
python3 src/experiments/GA/solomon_to_pyga_json.py src/data/Holmberger/R1_10_9.txt
```

Run the solver pipeline regression self-test:

```bash
src/.venv_pyvrp/bin/python src/experiments/evrptw_pipeline_self_test.py \
  --schneider /Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt
```

Install and verify the POMO CUDA environment when network access is available:

```powershell
powershell -ExecutionPolicy Bypass -File src\experiments\setup_pomo_cuda_env.ps1
```
