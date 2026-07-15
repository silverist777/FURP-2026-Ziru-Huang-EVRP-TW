# Week 4 EVRPTW Baseline Comparison Results

| instance | clients | method | status | feasible | distance | vehicles | runtime_s | served | missing | duplicate | tw_vio | cap_vio | energy_vio | charge_count | charge_time | reason |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| C101 | 100 | POMO100 cluster + EVRP-TW repair | solved | True | 939 | 11 | 0.244 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| C101 | 100 | PyVRP VRPTW + EVRP-TW station repair | solved | True | 829 | 10 | 5.032 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| C101 | 100 | Tabu-assisted VNS EVRP-TW | solved | True | 1049 | 11 | 0.629 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| C101 | 100 | py-ga-VRPTW custom + shared checker | solved | True | 4697 | 53 | 0.437 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| R1_10_9 | 1000 | POMO100 cluster + EVRP-TW repair | solved | True | 74795 | 94 | 3.793 | 1000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| R1_10_9 | 1000 | PyVRP VRPTW + EVRP-TW station repair | solved | True | 52252 | 95 | 12.083 | 1000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| R1_10_9 | 1000 | Tabu-assisted VNS EVRP-TW | solved | True | 83323 | 103 | 7.322 | 1000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| R1_10_9 | 1000 | py-ga-VRPTW custom + shared checker | solved | True | 328681 | 620 | 1.54 | 1000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
