# py-ga-VRPTW wait=1 delay=100000 rerun

Configuration: unit_cost=1, init_cost=0, wait_cost=1, delay_cost=100000, pop_size=80, generations=50.

## Aggregated Results

| instance_size | runs | feasible_rate | best_checked_route_distance | avg_checked_route_distance | std_checked_route_distance | avg_runtime_seconds | avg_vehicles_used |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 3 | 0.0 | 318.205 | 395.4 | 64.557 | 0.516 | 2.333 |
| 50 | 3 | 0.0 | 1448.346 | 1454.363 | 5.445 | 0.799 | 6.0 |
| 100 | 3 | 0.0 | 4022.803 | 4213.701 | 137.613 | 1.019 | 12.0 |

## Per-run Records

| instance_size | random_seed | is_feasible | checked_route_distance | printed_total_cost | csv_best_so_far_cost | runtime_seconds | vehicles_used | constraint_violations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 1234 | False | 318.205 | 275809293.567 | 275809293.567 | 0.536 | 2 | time_window_violations=15; depot_return_violations=2 |
| 20 | 2026 | False | 476.213 | 276673347.383 | 225699223.927 | 0.524 | 3 | time_window_violations=13; depot_return_violations=2 |
| 20 | 114514 | False | 391.782 | 264393136.227 | 244246194.131 | 0.489 | 2 | time_window_violations=14; depot_return_violations=2 |
| 50 | 1234 | False | 1461.534 | 760766743.21 | 760766743.21 | 1.054 | 6 | time_window_violations=41; depot_return_violations=5 |
| 50 | 2026 | False | 1453.209 | 737015768.535 | 673978817.655 | 0.768 | 6 | time_window_violations=34; depot_return_violations=6 |
| 50 | 114514 | False | 1448.346 | 729732597.206 | 729732597.206 | 0.574 | 6 | time_window_violations=34; depot_return_violations=4 |
| 100 | 1234 | False | 4022.803 | 1590945717.614 | 1590945717.614 | 0.906 | 12 | time_window_violations=76; depot_return_violations=11 |
| 100 | 2026 | False | 4341.93 | 1659629231.575 | 1615116456.252 | 1.228 | 12 | time_window_violations=76; depot_return_violations=11 |
| 100 | 114514 | False | 4276.37 | 1693812818.707 | 1622367371.941 | 0.923 | 12 | time_window_violations=72; depot_return_violations=10 |
