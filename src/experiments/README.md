# Experiments

This directory contains the runnable EVRP-TW experiment scripts.

Current scope:

1. Build PyVRP-based VRPTW baselines.
2. Load shared JSON instance data.
3. Convert a small Schneider-style text sample into the project JSON schema.
4. Replay explicit EVRP-TW routes with customers and charging stations.
5. Report feasibility metrics: customer coverage, capacity, time windows, energy, charging count, and charging time.

This stage is CPU-only. It does not use CUDA, PyTorch, reinforcement learning, or neural training. PyVRP is used as a classical VRPTW baseline, while full EVRP-TW feasibility is checked by the independent route replay code.

## Scripts

- `smoke_test_pyvrp.py`: small PyVRP VRPTW smoke test.
- `scale_up_test.py`: larger PyVRP VRPTW baseline test.
- `feasibility_checker.py`: independent feasibility checker for route replay.
- `instance_loader.py`: shared loader for the project JSON schema.
- `parse_schneider_instance.py`: converts Schneider-style EVRP-TW text data to JSON.
- `check_explicit_routes.py`: checks explicit named routes containing customers and charging stations.
- `evrptw_repair.py`: inserts charging stations into fixed customer-order routes.
- `solve_evrptw_pipeline.py`: solves EVRP-TW with PyVRP customer routes plus station repair.
- `evrptw_checker_self_test.py`: parser and checker regression self-test.
- `evrptw_pipeline_self_test.py`: parser, repair, split, and unsolved-route regression tests.

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

Run the solver pipeline regression self-test:

```bash
src/.venv_pyvrp/bin/python src/experiments/evrptw_pipeline_self_test.py \
  --schneider /Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt
```
