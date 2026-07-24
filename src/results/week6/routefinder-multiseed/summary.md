# RouteFinder c101_21 Multi-Seed Feasibility Summary

Run date: 2026-07-22  
Seeds: 1–10  
Hard vehicle limit: 31  
Result: 10/10 checker-feasible

| seed | status | served | vehicles/max | violations | distance | runtime_s |
|---:|---|---:|---:|---:|---:|---:|
| 1 | solved | 100 | 31/31 | 0 | 2060 | 38.954 |
| 2 | solved | 100 | 31/31 | 0 | 2060 | 39.442 |
| 3 | solved | 100 | 31/31 | 0 | 2060 | 38.002 |
| 4 | solved | 100 | 31/31 | 0 | 2060 | 38.306 |
| 5 | solved | 100 | 31/31 | 0 | 2060 | 38.721 |
| 6 | solved | 100 | 31/31 | 0 | 2060 | 38.293 |
| 7 | solved | 100 | 31/31 | 0 | 2060 | 39.259 |
| 8 | solved | 100 | 31/31 | 0 | 2060 | 38.277 |
| 9 | solved | 100 | 31/31 | 0 | 2060 | 38.582 |
| 10 | solved | 100 | 31/31 | 0 | 2060 | 37.803 |

Each row passed the runner's JSON contract gate: 100/100 unique customer
coverage, zero time-window/capacity/energy/fleet violations, and 31 or fewer
vehicles. The current greedy/multistart inference is deterministic, so all ten
seeds produced the same route and objective; the runs demonstrate process-level
repeatability rather than ten distinct stochastic solutions.
