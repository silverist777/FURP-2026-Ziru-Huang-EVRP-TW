# py-ga-VRPTW wait=1 delay=10000 rerun

Configuration: unit_cost=1, init_cost=0, wait_cost=1, delay_cost=10000, pop_size=80, generations=50.

## Aggregated Results

| instance_size | runs | feasible_rate | best_checked_route_distance | avg_checked_route_distance | std_checked_route_distance | avg_runtime_seconds | avg_vehicles_used |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 3 | 0.0 | 318.205 | 395.4 | 64.557 | 2.003 | 2.333 |
| 50 | 3 | 0.0 | 1448.346 | 1454.363 | 5.445 | 1.768 | 6.0 |
| 100 | 3 | 0.0 | 4022.803 | 4213.701 | 137.613 | 2.525 | 12.0 |

## Per-run Records

| instance_size | random_seed | is_feasible | checked_route_distance | printed_total_cost | csv_best_so_far_cost | runtime_seconds | vehicles_used | constraint_violations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 1234 | False | 318.205 | 27582305.042 | 27582305.042 | 3.146 | 2 | time_window_violations=15; depot_return_violations=2 |
| 20 | 2026 | False | 476.213 | 27669291.005 | 22572152.401 | 1.397 | 3 | time_window_violations=13; depot_return_violations=2 |
| 20 | 114514 | False | 391.782 | 26440564.048 | 24425706.457 | 1.467 | 2 | time_window_violations=14; depot_return_violations=2 |
| 50 | 1234 | False | 1461.534 | 76083162.48 | 76083162.48 | 1.647 | 6 | time_window_violations=41; depot_return_violations=5 |
| 50 | 2026 | False | 1453.209 | 73708078.103 | 67403061.987 | 2.079 | 6 | time_window_violations=34; depot_return_violations=6 |
| 50 | 114514 | False | 1448.346 | 72978895.162 | 72978895.162 | 1.577 | 6 | time_window_violations=34; depot_return_violations=4 |
| 100 | 1234 | False | 4022.803 | 159108751.009 | 159108751.009 | 2.865 | 12 | time_window_violations=76; depot_return_violations=11 |
| 100 | 2026 | False | 4341.93 | 165975918.393 | 161524727.469 | 2.568 | 12 | time_window_violations=76; depot_return_violations=11 |
| 100 | 114514 | False | 4276.37 | 169395317.631 | 162250883.158 | 2.143 | 12 | time_window_violations=72; depot_return_violations=10 |
