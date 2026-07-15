# Data Guide

This directory contains committed, reviewable inputs. Solver code belongs in
`src/experiments/`; generated artifacts belong in `src/results/`.

## Dataset map

| Path | Problem / format | Current use |
|---|---|---|
| `evrptw_instances/*.txt` | Schneider-style EVRP-TW | current four-method Track B comparison |
| `Solomon/*.txt`, `*.sol` | Solomon VRPTW | PyVRP, POMO checkpoint evaluation, and conversion utilities |
| `Holmberger/*.txt`, `*.sol` | large Solomon-like VRPTW | scale-up experiments and conversion utilities |
| `A/*.vrp`, `*.sol` | CVRPLIB Augerat A CVRP | CVRP-only method experiments |
| `smoke_test_instance.json` | small project-schema instance | fast parser/solver checks |
| `scale_up_instance.json` | larger project-schema instance | pipeline scale check |
| `schneider_sample.txt` | minimal Schneider-style sample | parser/checker tests only |
| `explicit_routes_sample.json` | named route list | explicit route replay test |

The bundled `schneider_sample.txt` is synthetic test data, not a benchmark
reproduction. Do not report its result as a paper comparison.

The py-ga baseline reads instances from the `py-ga-VRPTW` submodule. Conversion
helpers may create custom submodule data during a run; do not confuse those files
with the canonical inputs in this directory.

## Shared JSON shape

Project JSON instances use these top-level sections:

- `depot`, `clients`, and `charging_stations`;
- `vehicles`, `energy`, and `charging`;
- `distance`, `duration`, and `solver`.

`src/experiments/core/instance_loader.py` is the authoritative loader. EVRP-TW data
loaded through it receives the shared hard fleet cap documented in the root
README. Keep solver decisions out of input files.

Named explicit routes use this shape:

```json
{
  "routes": [
    ["D0", "S1", "C2", "S1", "C1", "D0"]
  ]
}
```

Customer names count toward coverage and capacity. Charging-station names may
appear multiple times and are replayed by the feasibility checker.

## Adding data

Commit only data that is small enough for review and whose source and problem
type are clear. Add the dataset to the table above, retain its original naming,
and record any conversion in `docs/` or the experiment output. Large or
restricted datasets should be referenced by source rather than committed.
