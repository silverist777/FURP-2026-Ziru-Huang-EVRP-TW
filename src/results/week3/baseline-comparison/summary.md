# Week 3 Experiment Summary

## Aggregated Results

| size_group | instance_size | method_name | runs | feasible_rate | best_objective | avg_objective | std_objective | avg_runtime_seconds | avg_vehicles_used | gap_to_best_observed_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| small | 20 | PyVRP | 3 | 1.0 | 175.374 | 175.374 | 0.0 | 1.001 | 3.0 | 0.0 |
| small | 20 | py-ga-VRPTW | 3 | 0.0 | 226.155 | 268.536 | 30.027 | 0.232 | 2.0 | 28.956 |
| small | 20 | yd-kwon/POMO | 3 | 0.0 | 315.817 | 315.817 | 0.0 | 0.01 | 4.0 | 80.082 |
| medium | 50 | PyVRP | 3 | 1.0 | 363.248 | 363.248 | 0.0 | 1.003 | 5.0 | 0.0 |
| medium | 50 | py-ga-VRPTW | 3 | 0.0 | 1196.947 | 1217.793 | 18.884 | 0.318 | 5.667 | 229.512 |
| medium | 50 | yd-kwon/POMO | 3 | 0.0 | 407.03 | 407.03 | 0.0 | 0.018 | 5.0 | 12.053 |
| large | 100 | PyVRP | 3 | 1.0 | 828.937 | 828.937 | 0.0 | 1.011 | 10.0 | 0.0 |
| large | 100 | py-ga-VRPTW | 3 | 0.0 | 3607.984 | 3686.905 | 65.746 | 0.497 | 11.333 | 335.254 |
| large | 100 | yd-kwon/POMO | 3 | 0.0 | 835.89 | 835.89 | 0.0 | 0.055 | 10.0 | 0.839 |

## Per-run Records

| instance_size | method_name | random_seed | is_feasible | objective_value | runtime_seconds | vehicles_used | constraint_violations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | py-ga-VRPTW | 1234 | False | 226.155 | 0.259 | 2 | time_window_violations=16; depot_return_violations=2 |
| 20 | py-ga-VRPTW | 2026 | False | 292.03 | 0.225 | 2 | time_window_violations=15; depot_return_violations=2 |
| 20 | py-ga-VRPTW | 114514 | False | 287.423 | 0.212 | 2 | time_window_violations=17; depot_return_violations=2 |
| 50 | py-ga-VRPTW | 1234 | False | 1213.759 | 0.325 | 5 | time_window_violations=37; depot_return_violations=5 |
| 50 | py-ga-VRPTW | 2026 | False | 1196.947 | 0.328 | 6 | time_window_violations=39; depot_return_violations=5 |
| 50 | py-ga-VRPTW | 114514 | False | 1242.673 | 0.3 | 6 | time_window_violations=38; depot_return_violations=5 |
| 100 | py-ga-VRPTW | 1234 | False | 3768.937 | 0.49 | 11 | time_window_violations=80; depot_return_violations=11 |
| 100 | py-ga-VRPTW | 2026 | False | 3607.984 | 0.51 | 12 | time_window_violations=77; depot_return_violations=9 |
| 100 | py-ga-VRPTW | 114514 | False | 3683.794 | 0.492 | 11 | time_window_violations=74; depot_return_violations=10 |
| 20 | PyVRP | 1234 | True | 175.374 | 1.002 | 3 | none |
| 20 | PyVRP | 2026 | True | 175.374 | 1.001 | 3 | none |
| 20 | PyVRP | 114514 | True | 175.374 | 1.001 | 3 | none |
| 50 | PyVRP | 1234 | True | 363.248 | 1.004 | 5 | none |
| 50 | PyVRP | 2026 | True | 363.248 | 1.003 | 5 | none |
| 50 | PyVRP | 114514 | True | 363.248 | 1.003 | 5 | none |
| 100 | PyVRP | 1234 | True | 828.937 | 1.011 | 10 | none |
| 100 | PyVRP | 2026 | True | 828.937 | 1.011 | 10 | none |
| 100 | PyVRP | 114514 | True | 828.937 | 1.011 | 10 | none |
| 20 | yd-kwon/POMO | 1234 | False | 315.817 | 0.011 | 4 | time_window_violations=16; depot_return_violations=2 |
| 20 | yd-kwon/POMO | 2026 | False | 315.817 | 0.01 | 4 | time_window_violations=16; depot_return_violations=2 |
| 20 | yd-kwon/POMO | 114514 | False | 315.817 | 0.009 | 4 | time_window_violations=16; depot_return_violations=2 |
| 50 | yd-kwon/POMO | 1234 | False | 407.03 | 0.018 | 5 | time_window_violations=30; depot_return_violations=3 |
| 50 | yd-kwon/POMO | 2026 | False | 407.03 | 0.018 | 5 | time_window_violations=30; depot_return_violations=3 |
| 50 | yd-kwon/POMO | 114514 | False | 407.03 | 0.019 | 5 | time_window_violations=30; depot_return_violations=3 |
| 100 | yd-kwon/POMO | 1234 | False | 835.89 | 0.056 | 10 | time_window_violations=48; depot_return_violations=5 |
| 100 | yd-kwon/POMO | 2026 | False | 835.89 | 0.054 | 10 | time_window_violations=48; depot_return_violations=5 |
| 100 | yd-kwon/POMO | 114514 | False | 835.89 | 0.055 | 10 | time_window_violations=48; depot_return_violations=5 |
