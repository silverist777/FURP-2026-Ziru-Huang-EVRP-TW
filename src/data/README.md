# Data

This directory stores small, commit-safe input data used by the experiment scripts.

Current files:

- `smoke_test_instance.json`: tiny EVRP-TW/VRPTW-style JSON instance for a quick PyVRP smoke test.
- `scale_up_instance.json`: larger JSON instance for baseline scaling checks.
- `schneider_sample.txt`: minimal Schneider-style EVRP-TW parser/checker sample.
- `explicit_routes_sample.json`: named route sample used by the explicit route checker.

The bundled `schneider_sample.txt` is not a Schneider benchmark reproduction instance. It is a small parser and feasibility-checker sample. Do not report its result as a benchmark reproduction.

Full Schneider benchmark files should be passed to the solver by path instead of copied here. Example:

```bash
src/.venv_pyvrp/bin/python src/experiments/solve_evrptw_pipeline.py \
  --schneider /Users/emt/Workspace/evrp_tw/data/schneider/c101C5.txt
```

## JSON Instance Shape

The shared JSON schema is centered on:

- `depot`
- `clients`
- `charging_stations`
- `vehicles`
- `energy`
- `charging`
- `solver`
- `distance`
- `duration`

Keep solver code out of data files. Add missing EVRP-TW fields defensively in JSON first, then let `src/experiments/instance_loader.py` pass them to solvers and checkers.

## Explicit Route Shape

`explicit_routes_sample.json` stores named routes:

```json
{
  "routes": [
    ["D0", "S1", "C2", "S1", "C1", "D0"]
  ]
}
```

Customer names count toward service coverage and capacity. Charging station names may appear more than once and are replayed by the feasibility checker.
