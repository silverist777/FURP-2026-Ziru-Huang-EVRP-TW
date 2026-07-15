# Week 3 Experiment Summary

## Aggregated Results

| size_group | instance_size | method_name | runs | feasible_rate | best_objective | avg_objective | std_objective | avg_runtime_seconds | avg_vehicles_used | gap_to_best_observed_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| small | 20 | PyVRP | 1 | 1.0 | 175.374 | 175.374 | 0 | 1.005 | 3.0 | 0.0 |
| small | 20 | py-ga-VRPTW | 1 | 1.0 | 537.107 | 537.107 | 0 | 0.212 | 10.0 | 206.264 |
| small | 20 | yd-kwon/POMO | 1 | 0.0 | 315.817 | 315.817 | 0 | 0.034 | 4.0 | 80.082 |
| medium | 50 | PyVRP | 1 | 1.0 | 363.248 | 363.248 | 0 | 1.004 | 5.0 | 0.0 |
| medium | 50 | py-ga-VRPTW | 1 | 1.0 | 1675.462 | 1675.462 | 0 | 0.183 | 25.0 | 361.245 |
| medium | 50 | yd-kwon/POMO | 1 | 0.0 | 407.03 | 407.03 | 0 | 0.017 | 5.0 | 12.053 |
| large | 100 | PyVRP | 1 | 1.0 | 828.937 | 828.937 | 0 | 1.012 | 10.0 | 0.0 |
| large | 100 | py-ga-VRPTW | 1 | 1.0 | 4669.128 | 4669.128 | 0 | 0.275 | 56.0 | 463.267 |
| large | 100 | yd-kwon/POMO | 1 | 0.0 | 835.89 | 835.89 | 0 | 0.05 | 10.0 | 0.839 |

## Per-run Records

| instance_size | method_name | random_seed | is_feasible | objective_value | runtime_seconds | vehicles_used | constraint_violations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | py-ga-VRPTW | 1234 | True | 537.107 | 0.212 | 10 | none |
| 50 | py-ga-VRPTW | 1234 | True | 1675.462 | 0.183 | 25 | none |
| 100 | py-ga-VRPTW | 1234 | True | 4669.128 | 0.275 | 56 | none |
| 20 | PyVRP | 1234 | True | 175.374 | 1.005 | 3 | none |
| 50 | PyVRP | 1234 | True | 363.248 | 1.004 | 5 | none |
| 100 | PyVRP | 1234 | True | 828.937 | 1.012 | 10 | none |
| 20 | yd-kwon/POMO | 1234 | False | 315.817 | 0.034 | 4 | time_window_violations=16; depot_return_violations=2 |
| 50 | yd-kwon/POMO | 1234 | False | 407.03 | 0.017 | 5 | time_window_violations=30; depot_return_violations=3 |
| 100 | yd-kwon/POMO | 1234 | False | 835.89 | 0.05 | 10 | time_window_violations=48; depot_return_violations=5 |
