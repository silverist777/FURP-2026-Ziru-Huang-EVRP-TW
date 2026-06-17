# Results

This directory stores generated experiment outputs.

Current file:

- `schneider_sample_converted.json`: generated JSON output from `src/data/schneider_sample.txt`.

Regenerate it from the repository root:

```bash
src/.venv_pyvrp/bin/python src/experiments/parse_schneider_instance.py \
  src/data/schneider_sample.txt \
  --output src/results/schneider_sample_converted.json \
  --vehicles 2 \
  --runtime-seconds 1
```

Check the converted result with the explicit route sample:

```bash
src/.venv_pyvrp/bin/python src/experiments/check_explicit_routes.py \
  --instance src/results/schneider_sample_converted.json \
  --routes src/data/explicit_routes_sample.json
```

Only keep small, reproducible outputs here. Large logs, full benchmark dumps, and temporary experiment artifacts should stay out of Git unless they are specifically needed for review.

The EVRP-TW solving pipeline writes solution files here by default:

```bash
src/.venv_pyvrp/bin/python src/experiments/solve_evrptw_pipeline.py \
  --schneider /Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt \
  --vehicles 2 \
  --runtime-seconds 2
```
