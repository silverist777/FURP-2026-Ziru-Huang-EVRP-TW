## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: run
- Origin Date: 2026-07-11
- Verification Status: UNVERIFIED
- Version Label: exp_result_v1

# Four-Instance EVRPTW Pilot Result

## Configuration

- Method: PyVRP VRPTW customer routes + v3 partial-recharge EVRP-TW repair + independent checker
- Seed: `1`
- PyVRP search budget: `10` seconds per instance
- Vehicle rule: $K=\lceil n/8\rceil$
- Working directory: `/Users/emt/Workspace/FURP-2026-Ziru-Huang-EVRP-TW`
- Run date: 2026-07-11

The `10`-second setting limits the PyVRP baseline search, not the full repair and checker pipeline. Reported runtime is end-to-end elapsed time.

## Results

| Instance | Clients | Available vehicles | Status | Feasible | Vehicles used | Distance | Runtime (s) | Served / missing | TW / capacity / energy violations | Charging count / time |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| `c101_21` | 100 | 13 | solved | yes | 12 | 1055 | 139.201 | 100 / 0 | 0 / 0 / 0 | 7 / 606 |
| `c101C5` | 5 | 1 | unsolved | no | 0 | 0 | 10.005 | 0 / 5 | 0 / 0 / 0 | 0 / 0 |
| `c101C10` | 10 | 2 | unsolved | no | 0 | 0 | 10.023 | 0 / 10 | 0 / 0 / 0 | 0 / 0 |
| `c103C15` | 15 | 2 | unsolved | no | 0 | 0 | 10.051 | 0 / 15 | 0 / 0 / 0 | 0 / 0 |

## Failure Details

The three unsolved cases were not checker-feasible partial solutions. The repair stage discarded the incomplete route set and reported all customers as missing.

| Instance | Baseline status | Repair finding |
| --- | --- | --- |
| `c101C5` | PyVRP route has time warp `100` | Fixed customer order could not be repaired; splitting required at least 2 vehicles, exceeding $K=1$. |
| `c101C10` | PyVRP route set has time warp `2` | Repair required at least 3 vehicles, exceeding $K=2$. |
| `c103C15` | PyVRP baseline is VRPTW-feasible | EVRP-TW charging repair required at least 3 vehicles, exceeding $K=2$. |

These results show that $K=\lceil n/8\rceil$ is a strict fleet limit, not a guarantee that every instance is feasible. A failure under this limit should remain an experimental outcome unless the protocol explicitly permits a larger fleet.

## Output Files

- `c101_21_pyvrp_repair_seed1.json`
- `c101C5_pyvrp_repair_seed1.json`
- `c101C10_pyvrp_repair_seed1.json`
- `c103C15_pyvrp_repair_seed1.json`

## Anomalies Detected

- PyVRP emitted `PenaltyBoundWarning` on `c101C5` and `c101C10`.
- The 100-customer end-to-end runtime was `139.201` seconds despite a `10`-second PyVRP search budget because charging repair is outside that limit.
- No experiment was automatically retried with a larger fleet or different seed.

