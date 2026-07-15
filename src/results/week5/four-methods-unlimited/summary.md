# Week 5 Four-Method Unlimited-Fleet Comparison

| instance | clients | method | status | feasible | distance | vehicles | runtime_s | served | missing | duplicate | tw_vio | cap_vio | energy_vio | vehicle_vio | charge_count | charge_time | reason |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| c101C10 | 10 | PyVRP VRPTW + EVRP-TW station repair | solved | True | 387 | 3 | 10.152 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 536 |  |
| c101C10 | 10 | Tabu-assisted VNS EVRP-TW | solved | True | 387 | 3 | 297.275 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 536 |  |
| c101C10 | 10 | py-ga-VRPTW custom + shared checker | unsolved | False | 470 | 5 | 0.123 | 10 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |  |
| c101C10 | 10 | yd-kwon/POMO CVRP + EVRP-TW repair | solved | True | 516 | 7 | 2.379 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 287 |  |
| c101C5 | 5 | PyVRP VRPTW + EVRP-TW station repair | solved | True | 248 | 3 | 10.006 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 177 |  |
| c101C5 | 5 | Tabu-assisted VNS EVRP-TW | solved | True | 259 | 2 | 11.283 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 361 |  |
| c101C5 | 5 | py-ga-VRPTW custom + shared checker | unsolved | False | 240 | 2 | 0.094 | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |  |
| c101C5 | 5 | yd-kwon/POMO CVRP + EVRP-TW repair | solved | True | 248 | 3 | 0.667 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 177 |  |
| c101_21 | 100 | PyVRP VRPTW + EVRP-TW station repair | solved | True | 1058 | 12 | 219.316 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 608 |  |
| c101_21 | 100 | Schneider-2014 hybrid VNS/TS E-VRPTW | solved | True | 1085 | 13 | 4180.195 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 1074 |  |
| c101_21 | 100 | py-ga-VRPTW custom + shared checker | unsolved | False | 4644 | 51 | 0.612 | 100 | 0 | 0 | 0 | 0 | 52 | 0 | 0 | 0 |  |
| c101_21 | 100 | yd-kwon/POMO CVRP + EVRP-TW repair | solved | True | 4833 | 79 | 6507.581 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 1095 |  |
| c103C15 | 15 | PyVRP VRPTW + EVRP-TW station repair | solved | True | 350 | 3 | 10.277 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 407 |  |
| c103C15 | 15 | Tabu-assisted VNS EVRP-TW | solved | True | 382 | 3 | 472.708 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 518 |  |
| c103C15 | 15 | py-ga-VRPTW custom + shared checker | unsolved | False | 558 | 4 | 0.149 | 15 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 0 |  |
| c103C15 | 15 | yd-kwon/POMO CVRP + EVRP-TW repair | solved | True | 588 | 6 | 4.057 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 478 |  |
