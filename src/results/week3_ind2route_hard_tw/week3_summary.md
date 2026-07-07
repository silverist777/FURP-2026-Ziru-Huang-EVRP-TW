# Week 3 Experiment Summary

## Aggregated Results

| size_group | instance_size | method_name | runs | feasible_rate | best_objective | avg_objective | std_objective | avg_runtime_seconds | avg_vehicles_used | gap_to_best_observed_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| small | 20 | PyVRP | 3 | 1.0 | 175.374 | 175.374 | 0.0 | 1.002 | 3.0 | 0.0 |
| small | 20 | py-ga-VRPTW | 3 | 1.0 | 497.214 | 525.749 | 20.317 | 0.278 | 8.667 | 183.516 |
| small | 20 | yd-kwon/POMO | 3 | 0.0 | 315.817 | 315.817 | 0.0 | 0.022 | 4.0 | 80.082 |
| medium | 50 | PyVRP | 3 | 1.0 | 363.248 | 363.248 | 0.0 | 1.013 | 5.0 | 0.0 |
| medium | 50 | py-ga-VRPTW | 3 | 1.0 | 1655.543 | 1670.801 | 11.058 | 0.34 | 23.333 | 355.761 |
| medium | 50 | yd-kwon/POMO | 3 | 0.0 | 407.03 | 407.03 | 0.0 | 0.02 | 5.0 | 12.053 |
| large | 100 | PyVRP | 3 | 1.0 | 828.937 | 828.937 | 0.0 | 1.011 | 10.0 | 0.0 |
| large | 100 | py-ga-VRPTW | 3 | 1.0 | 4522.272 | 4574.741 | 39.639 | 0.519 | 54.333 | 445.551 |
| large | 100 | yd-kwon/POMO | 3 | 0.0 | 835.89 | 835.89 | 0.0 | 0.056 | 10.0 | 0.839 |

## Per-run Records

| instance_size | method_name | random_seed | is_feasible | objective_value | runtime_seconds | vehicles_used | constraint_violations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | py-ga-VRPTW | 1234 | True | 537.107 | 0.376 | 10 | none |
| 20 | py-ga-VRPTW | 2026 | True | 542.927 | 0.228 | 9 | none |
| 20 | py-ga-VRPTW | 114514 | True | 497.214 | 0.231 | 7 | none |
| 50 | py-ga-VRPTW | 1234 | True | 1675.462 | 0.341 | 26 | none |
| 50 | py-ga-VRPTW | 2026 | True | 1655.543 | 0.351 | 22 | none |
| 50 | py-ga-VRPTW | 114514 | True | 1681.399 | 0.329 | 22 | none |
| 100 | py-ga-VRPTW | 1234 | True | 4583.882 | 0.534 | 56 | none |
| 100 | py-ga-VRPTW | 2026 | True | 4618.068 | 0.514 | 54 | none |
| 100 | py-ga-VRPTW | 114514 | True | 4522.272 | 0.509 | 53 | none |
| 20 | PyVRP | 1234 | True | 175.374 | 1.004 | 3 | none |
| 20 | PyVRP | 2026 | True | 175.374 | 1.001 | 3 | none |
| 20 | PyVRP | 114514 | True | 175.374 | 1.001 | 3 | none |
| 50 | PyVRP | 1234 | True | 363.248 | 1.004 | 5 | none |
| 50 | PyVRP | 2026 | True | 363.248 | 1.003 | 5 | none |
| 50 | PyVRP | 114514 | True | 363.248 | 1.031 | 5 | none |
| 100 | PyVRP | 1234 | True | 828.937 | 1.011 | 10 | none |
| 100 | PyVRP | 2026 | True | 828.937 | 1.011 | 10 | none |
| 100 | PyVRP | 114514 | True | 828.937 | 1.011 | 10 | none |
| 20 | yd-kwon/POMO | 1234 | False | 315.817 | 0.044 | 4 | time_window_violations=16; depot_return_violations=2 |
| 20 | yd-kwon/POMO | 2026 | False | 315.817 | 0.009 | 4 | time_window_violations=16; depot_return_violations=2 |
| 20 | yd-kwon/POMO | 114514 | False | 315.817 | 0.013 | 4 | time_window_violations=16; depot_return_violations=2 |
| 50 | yd-kwon/POMO | 1234 | False | 407.03 | 0.019 | 5 | time_window_violations=30; depot_return_violations=3 |
| 50 | yd-kwon/POMO | 2026 | False | 407.03 | 0.019 | 5 | time_window_violations=30; depot_return_violations=3 |
| 50 | yd-kwon/POMO | 114514 | False | 407.03 | 0.021 | 5 | time_window_violations=30; depot_return_violations=3 |
| 100 | yd-kwon/POMO | 1234 | False | 835.89 | 0.055 | 10 | time_window_violations=48; depot_return_violations=5 |
| 100 | yd-kwon/POMO | 2026 | False | 835.89 | 0.057 | 10 | time_window_violations=48; depot_return_violations=5 |
| 100 | yd-kwon/POMO | 114514 | False | 835.89 | 0.055 | 10 | time_window_violations=48; depot_return_violations=5 |
