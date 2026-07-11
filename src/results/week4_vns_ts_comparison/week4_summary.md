# Week 4 EVRPTW Baseline Comparison Results

| instance | clients | method | feasible | distance | vehicles | runtime_s | served | missing | duplicate |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| C101 | 100 | POMO100 cluster + EVRP-TW repair | True | 939 | 11 | 0.233 | 100 | 0 | 0 |
| C101 | 100 | PyVRP VRPTW + EVRP-TW station repair | True | 829 | 10 | 5.031 | 100 | 0 | 0 |
| C101 | 100 | Tabu-assisted VNS EVRP-TW | True | 1049 | 11 | 0.93 | 100 | 0 | 0 |
| C101 | 100 | py-ga-VRPTW + checker | False | 4046 | 12 | 0.782 | 100 | 0 | 0 |
| R1_10_9 | 1000 | POMO100 cluster + EVRP-TW repair | True | 74795 | 94 | 3.255 | 1000 | 0 | 0 |
| R1_10_9 | 1000 | PyVRP VRPTW + EVRP-TW station repair | True | 52405 | 94 | 12.735 | 1000 | 0 | 0 |
| R1_10_9 | 1000 | Tabu-assisted VNS EVRP-TW | True | 83323 | 103 | 11.599 | 1000 | 0 | 0 |
| R1_10_9 | 1000 | py-ga-VRPTW + checker | False | 268756 | 160 | 2.118 | 1000 | 0 | 0 |
