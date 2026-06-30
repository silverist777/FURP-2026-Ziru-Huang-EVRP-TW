# Results

This directory stores generated experiment outputs.

Current files:

- `schneider_sample_converted.json`: generated JSON output from `src/data/schneider_sample.txt`.
- `schneider_sample_solution.json`: EVRP-TW repair-pipeline output for the bundled sample instance.
- `c101C5_solution.json`: EVRP-TW repair-pipeline output for the external Schneider-style `c101C5.txt` instance.

## `c101C5_solution.json`

This is the current reproducible Week 2 baseline result.

Solver stack:

```text
PyVRP VRPTW baseline + station_insertion_label_setting repair
```

Source instance:

```text
/Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt
```

Result snapshot:

| Metric | Value |
| --- | ---: |
| status | solved |
| routes | 2 |
| total_distance | 264 |
| total_duration | 1729 |
| charging_count | 3 |
| charging_time | 439 |
| time_window_violations | 0 |
| capacity_violations | 0 |
| energy_violations | 0 |

Reproduce it from the repository root:

```bash
src/.venv_pyvrp/bin/python src/experiments/solve_evrptw_pipeline.py \
  --schneider /Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt \
  --vehicles 2 \
  --runtime-seconds 2 \
  --output src/results/c101C5_solution.json \
  --fail-on-unsolved
```

This output is a baseline-plus-repair result. PyVRP builds customer routes with VRPTW constraints, then the project repair/checker code inserts charging stations and verifies EVRP-TW feasibility. It is not a full reproduction of the Schneider 2014 hybrid VNS/TS algorithm.

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
