# Week 5 three-group EVRP-TW method stability benchmark

Generated: `2026-07-22T14:37:34.507922+00:00`

## Coverage

- Expected jobs: **60**
- Strict-feasible jobs: **25**
- Failed or incomplete jobs: **35**
- Unexpected job directories excluded from statistics: **0**

Feasibility is accepted only from a fresh, contract-valid `checker.json` with `strict_feasible=true`; solver self-reports are ignored. Distance uses only those strict-feasible runs. Runner wall time includes every valid runner record, including failed attempts. Sample SD is undefined when fewer than two values are available.

Raw distance is never aggregated across different client sizes.

## Method × size cells

| method | clients | feasible | rate | Wilson 95% | distance n | distance mean ± sample SD | runtime n | wall runtime mean ± sample SD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pyvrp_repair | 5 | 3/3 | 100.0% | 43.9%–100.0% | 3 | 216.000 ± 69.742 | 3 | 10.260 ± 0.018 |
| pyvrp_repair | 10 | 2/3 | 66.7% | 20.8%–93.9% | 2 | 317.500 ± 98.288 | 3 | 10.361 ± 0.122 |
| pyvrp_repair | 15 | 3/3 | 100.0% | 43.9%–100.0% | 3 | 426.333 ± 38.214 | 3 | 10.696 ± 0.343 |
| pyvrp_repair | 100 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 0 | — |
| vns_ts | 5 | 3/3 | 100.0% | 43.9%–100.0% | 3 | 213.000 ± 67.104 | 3 | 11.647 ± 4.218 |
| vns_ts | 10 | 2/3 | 66.7% | 20.8%–93.9% | 2 | 320.000 ± 101.823 | 3 | 84.312 ± 25.543 |
| vns_ts | 15 | 2/3 | 66.7% | 20.8%–93.9% | 2 | 399.000 ± 21.213 | 2 | 189.058 ± 102.246 |
| vns_ts | 100 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 0 | — |
| pomo_repair | 5 | 3/3 | 100.0% | 43.9%–100.0% | 3 | 231.000 ± 37.643 | 3 | 2.559 ± 0.089 |
| pomo_repair | 10 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 3 | 2.801 ± 0.374 |
| pomo_repair | 15 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 2 | 5.156 ± 1.542 |
| pomo_repair | 100 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 0 | — |
| pyga_checked | 5 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 3 | 0.516 ± 0.253 |
| pyga_checked | 10 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 3 | 0.352 ± 0.010 |
| pyga_checked | 15 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 2 | 0.373 ± 0.005 |
| pyga_checked | 100 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 0 | — |
| routefinder_repair | 5 | 3/3 | 100.0% | 43.9%–100.0% | 3 | 214.333 ± 68.061 | 3 | 10.391 ± 0.287 |
| routefinder_repair | 10 | 2/3 | 66.7% | 20.8%–93.9% | 2 | 361.000 ± 89.095 | 3 | 10.697 ± 0.476 |
| routefinder_repair | 15 | 2/3 | 66.7% | 20.8%–93.9% | 2 | 471.000 ± 1.414 | 2 | 12.378 ± 1.267 |
| routefinder_repair | 100 | 0/3 | 0.0% | 0.0%–56.1% | 0 | — | 0 | — |

## Failure classes

| class | count |
|---|---:|
| infeasible | 9 |
| invalid | 1 |
| missing | 25 |

## Failed or incomplete jobs

| group | clients | instance | method | class | stage | detail |
|---|---:|---|---|---|---|---|
| C | 5 | c101C5 | pyga_checked | infeasible | checker | checker_infeasible:energy_or_charging |
| C | 10 | c101C10 | pomo_repair | missing | checker | checker_infeasible:coverage_missing |
| C | 10 | c101C10 | pyga_checked | infeasible | checker | checker_infeasible:fleet |
| C | 15 | c103C15 | pomo_repair | missing | checker | checker_infeasible:coverage_missing |
| C | 15 | c103C15 | pyga_checked | infeasible | checker | checker_infeasible:energy_or_charging |
| C | 100 | c101_21 | pyvrp_repair | missing | job | expected job directory is missing |
| C | 100 | c101_21 | vns_ts | missing | job | expected job directory is missing |
| C | 100 | c101_21 | pomo_repair | missing | job | expected job directory is missing |
| C | 100 | c101_21 | pyga_checked | missing | job | expected job directory is missing |
| C | 100 | c101_21 | routefinder_repair | missing | job | expected job directory is missing |
| R | 5 | r104C5 | pyga_checked | infeasible | checker | checker_infeasible:energy_or_charging |
| R | 10 | r102C10 | pomo_repair | missing | checker | checker_infeasible:coverage_missing |
| R | 10 | r102C10 | pyga_checked | infeasible | checker | checker_infeasible:energy_or_charging |
| R | 15 | r102C15 | pomo_repair | missing | checker | checker_infeasible:coverage_missing |
| R | 15 | r102C15 | pyga_checked | infeasible | checker | checker_infeasible:fleet |
| R | 100 | r101_21 | pyvrp_repair | missing | job | expected job directory is missing |
| R | 100 | r101_21 | vns_ts | missing | job | expected job directory is missing |
| R | 100 | r101_21 | pomo_repair | missing | job | expected job directory is missing |
| R | 100 | r101_21 | pyga_checked | missing | job | expected job directory is missing |
| R | 100 | r101_21 | routefinder_repair | missing | job | expected job directory is missing |
| RC | 5 | rc105C5 | pyga_checked | infeasible | checker | checker_infeasible:energy_or_charging |
| RC | 10 | rc102C10 | pyvrp_repair | missing | checker | checker_infeasible:coverage_missing |
| RC | 10 | rc102C10 | vns_ts | infeasible | checker | checker_infeasible:time_window |
| RC | 10 | rc102C10 | pomo_repair | missing | checker | checker_infeasible:coverage_missing |
| RC | 10 | rc102C10 | pyga_checked | infeasible | checker | checker_infeasible:fleet |
| RC | 10 | rc102C10 | routefinder_repair | invalid | checker_contract | contract_mismatch |
| RC | 15 | rc103C15 | vns_ts | missing | runner | runner.json is missing |
| RC | 15 | rc103C15 | pomo_repair | missing | job | expected job directory is missing |
| RC | 15 | rc103C15 | pyga_checked | missing | job | expected job directory is missing |
| RC | 15 | rc103C15 | routefinder_repair | missing | job | expected job directory is missing |
| RC | 100 | rc101_21 | pyvrp_repair | missing | job | expected job directory is missing |
| RC | 100 | rc101_21 | vns_ts | missing | job | expected job directory is missing |
| RC | 100 | rc101_21 | pomo_repair | missing | job | expected job directory is missing |
| RC | 100 | rc101_21 | pyga_checked | missing | job | expected job directory is missing |
| RC | 100 | rc101_21 | routefinder_repair | missing | job | expected job directory is missing |

Machine-readable details: `runs.csv`, `cells.csv`, `failures.csv`, and `summary.json`.
