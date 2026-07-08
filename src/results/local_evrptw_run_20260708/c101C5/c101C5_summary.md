# Week 4 EVRPTW Baseline Comparison Results

| instance | clients | method | feasible | distance | vehicles | runtime_s | served | missing | duplicate |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| c101C5 | 5 | PyVRP VRPTW + EVRP-TW station repair | True | 264 | 2 | 2.011 | 5 | 0 | 0 |
| c101C5 | 5 | Tabu-assisted VNS EVRP-TW | True | 259 | 2 | 1.124 | 5 | 0 | 0 |
| c101C5 | 5 | yd-kwon/POMO CVRP + EVRP-TW repair | True | 264 | 2 | 0.237 | 5 | 0 | 0 |
