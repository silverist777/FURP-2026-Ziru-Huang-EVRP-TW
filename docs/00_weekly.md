# Weekly Progress Log

> Update this file **every week**. Add a new entry at the top for each week.
> This is the first thing we check during review. Keep it honest and specific — it also feeds your attendance record (Rule 1).

**How to use:** copy the *Week template* block below for each new week. Newest week goes at the top.

---

## Week template — copy me

### Week N — YYYY-MM-DD

**Attended this week's meeting:** Yes / No (if No, did you email leave? Yes / No)

**Progress this week**
- _What did you actually do / finish?_

**Challenges & blockers**
- _What got in the way? What are you stuck on?_

**Next steps**
- _What will you do next week?_

**Hours spent (optional):** _e.g. 6h_

**Links (optional):** _commits, notebooks, docs, datasets..._

---

<!-- =================  YOUR ENTRIES BELOW  ================= -->

### Week 5 — 2026/7/15

**Attended this week's meeting:** Yes

**Progress this week**
- Introduced a shared hard vehicle-number rule for every EVRP-TW instance: `vehicle_limit = ceil((number_of_clients + number_of_charging_stations) / 4)`, including charging station `S0`.
- Applied the fleet limit in the shared instance loader and feasibility checker, and added a regression self-test for the formula and fleet capping behavior.
- Reran PyVRP + repair, Hybrid VNS/TS, POMO + repair, and py-ga + checker on the 5-, 10-, 15-, and 100-client EVRP-TW instances, completing a 16-run comparison matrix.
- Retained routes, metrics, runtimes, random seeds, and constraint violations in JSON, and generated a readable comparison table plus overview and route-petal visualizations.
- Confirmed that PyVRP + repair remained feasible on all four instances. Hybrid VNS/TS was also feasible on all four and achieved shorter routes than PyVRP on `c101C5` and `c103C15`.
- Added a sequential reproduction script for the Week 5 experiment, with the long 100-client POMO run available through the optional `-IncludePomo100` flag.

**Challenges & blockers**
- The retained POMO checkpoint was trained for CVRP rather than EVRP-TW. Under the fleet limit, its repair stage missed customers on the 10-, 15-, and 100-client instances; on `c101_21`, it served only 33 of 100 customers.
- The external py-ga solver does not construct routes with charging-station insertion as a hard constraint. All four checked outputs had energy violations, and some also exceeded the vehicle limit.
- Hybrid VNS/TS is computationally expensive: the `c101_21` run took about 78 minutes, compared with about 4.4 minutes for PyVRP + repair.
- The current comparison uses one seed and four instances, so it is a pipeline checkpoint rather than sufficient evidence for a statistical performance claim.

**Next steps**
- Run a multi-seed stability study on the 5-, 10-, and 15-client instances, reporting feasibility rate and the mean and standard deviation of distance and runtime.
- Implement fleet-aware and charging-aware construction or repair for POMO and py-ga, using complete customer coverage with zero energy and fleet violations as the first success criterion.
- Reuse the failed `c101_21` POMO result as a regression case for the improved repair mechanism.
- Match the current instance and evaluation settings carefully to published benchmarks before making direct comparisons with paper results.

**Hours spent (optional):**

**Links (optional):**
- [Week 5 project checkpoint](week05_checkpoint.md)
- [Week 5 results index](../src/results/week5/README.md)
- [Shared-fleet comparison and interpretation](../src/results/week5/four-methods-vehicle-limit/README.md)
- [Full comparison table](../src/results/week5/four-methods-vehicle-limit/summary.md)
- [Raw solver records](../src/log/week5/four-methods-vehicle-limit/)
- [Reproduction script](../src/experiments/runners/run_week5_track_b.ps1)

### Week 4 — 2026/7/8

**Attended this week's meeting:** Yes

**Progress this week**
- Completed the Week 4 EVRP-TW baseline comparison on two test cases: Solomon `C101` and Holmberger `R1_10_9`.
- Fixed the Week 3 limitation where POMO and GA were mainly suitable for 100-customer inputs. This week first focused on making all baselines runnable on both 100-customer and 1000-customer cases, then compared them fairly with the shared checker.
- Added and tested the `POMO100 cluster + EVRP-TW repair` pipeline, which decomposes the 1000-customer instance into 100-customer clusters, runs the retained CVRP100 POMO checkpoint, then repairs and validates the full solution.
- Added custom Solomon/Holmberger input support for `py-ga-VRPTW`, plus a checked wrapper that replays the GA route with the shared project checker.
- Ran four checked methods: `PyVRP VRPTW + EVRP-TW station repair`, `POMO100 cluster + EVRP-TW repair`, `Tabu-assisted VNS EVRP-TW`, and `py-ga-VRPTW custom + shared checker`.
- Stored Week 4 raw records under `src/log/week4/vns-ts-comparison/` and reader-facing summaries/plots under `src/results/week4/vns-ts-comparison/`.
- Finished the Week 4 report in `docs/WEEK4.md`. All eight final rows were feasible, served all customers, and had zero missing, duplicate, time-window, capacity, and energy violations.
- Main result: PyVRP is still the best distance baseline; POMO100 + repair is the strongest speed/quality hybrid candidate; VNS/TS is feasible but needs stronger search; py-ga is runnable at 1000 customers but uses too many fragmented routes.

**Challenges & blockers**
- `C101` and `R1_10_9` are VRPTW benchmark files, not full EVRP-TW charging benchmarks, so charging count, charging time, and energy violations are all zero in this experiment.
- The retained `yd-kwon/POMO` checkpoint is still CVRP100, so the large-case result must be reported as `POMO100 cluster + EVRP-TW repair`, not as a true POMO1000 or end-to-end EVRP-TW model.
- `py-ga-VRPTW` can now run on `R1_10_9`, but it achieves feasibility mainly by splitting routes aggressively, leading to 620 vehicles on the 1000-customer case.
- The current VNS/TS implementation is feasible, but its distance is still worse than PyVRP and POMO100 + repair under the current runtime/search budget.

**Next steps**
- Move from VRPTW-only inputs to true EVRP-TW charging instances, or add controlled charging stations and battery parameters to the current test cases.
- Improve the VNS/TS neighborhoods and search budget so it can compete on distance, not only feasibility.
- Improve the GA decoder or add local search/repair so feasibility does not require excessive route fragmentation.
- Keep PyVRP as the reliable feasible baseline, and use POMO100 + repair as the main hybrid speed/quality comparison method.

**Hours spent (optional):**

**Links (optional):**
**Links (optional):**
- [Week 4 report](WEEK4.md)
- [Raw records and summary CSV](../src/log/week4/vns-ts-comparison/)
- [Summary Markdown](../src/results/week4/vns-ts-comparison/summary.md)
- [Visualization](../src/results/week4/vns-ts-comparison/overview.png)
- [GA checked wrapper](../src/experiments/methods/ga/run_py_ga_vrptw_checked.py)
- [VNS/TS baseline](../src/experiments/methods/vns_ts/vns_ts_evrptw_baseline.py)
- [POMO decomposed pipeline](../src/experiments/methods/pomo/pomo_decomposed_evrptw_pipeline.py)



### Week 3 — 2026/7/1

**Attended this week's meeting:** Yes

**Progress this week**
- Implemented and ran Week 3 comparison experiments for `PyVRP`, `py-ga-VRPTW`, and upstream `yd-kwon/POMO`.
- Used Solomon `C101` subsets with 20, 50, and 100 customers, and tested each method with three random seeds.
- Built the experiment script to record objective value, runtime, feasibility status, vehicles used, constraint violations, routes, and convergence data.
- Generated result tables and plots for objective value, runtime, and GA convergence curves.
- Finished the Week 3 report explaining the main result: POMO is very fast and close to PyVRP on the 100-customer distance objective, but it is infeasible under Solomon time-window checks because the checkpoint is CVRP-only.
- Cleaned up the previous local RL4CO/POMO path and kept the retained upstream `yd-kwon/POMO` checkpoint workflow.

**Challenges & blockers**
- POMO does not model time windows or EVRP-TW constraints, so its routes fail the post-run feasibility checker even when the distance is good.
- The external `py-ga-VRPTW` baseline was not feasible under the initial distance-only setting, and penalty tuning still needs more work.
- A fair large-scale comparison with Holmberger instances is difficult because `py-ga-VRPTW` and the retained POMO checkpoint are mainly aligned with 100-customer Solomon/CVRP-style inputs.

**Next steps**
- Tune `py-ga-VRPTW` with stronger time-window penalties and/or more generations.
- Add a repair or checking layer after POMO rollout, or look for a time-window-aware neural model.
- Move from VRPTW comparison toward EVRP-TW-specific constraints such as battery, charging stations, and recharge time.
- Keep PyVRP as the reliable feasible baseline for later EVRP-TW experiments.

**Hours spent (optional):** 

**Links (optional):**
- Week 3 report: `docs/WEEK3.md`
- Archived experiment script: `src/experiments/legacy/cvrp/week3_pyga_pyvrp_pomo.py`
- Summary results: `src/results/week3/baseline-comparison/summary.md`
- Plots: `src/results/week3/baseline-comparison/plots/`
- Commits: `5ffe517`, `da5d4b8`, `8e015f7`, `a655fa6`

### Week 2 — 2026/6/24

**Attended this week's meeting:** Yes 

**Progress this week**
- _What did you actually do / finish?_
  - Read POMO and inspected the code
  - trained the model and added time window constraint 
**Challenges & blockers**
- _What got in the way? What are you stuck on?_
    - Using RL to train the model did not work well. Maybe because the data batch size and training epoch is too small.
    - Did the randomly generated data set work well in training?
    - 
**Next steps**
- _What will you do next week?_
    - Implement GA for VRPTW
**Hours spent (optional):** _e.g. 6h_

**Links (optional):** _commits, notebooks, docs, datasets..._
[POMO](https://proceedings.neurips.cc/paper/2020/hash/f231f2107df69eab0a3862d50018a9b2-Abstract.html)
[Data Set][https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances]
[Results]()
### Week 1 — YYYY-MM-DD

**Attended this week's meeting:** Yes

**Progress this week**
- Set up repository from the FURP template.
- Apply PyVRP to solve traditional VRPTW problems
- Read EVPR-TW related paper and got to know the VNS+TS metaheuristic algorithm. 

**Challenges & blockers**
- PyVRP cannot solve EVRP-TW problems because electric-related parameters are not contained.

**Next steps**
- build a pipeline for EVRP-TW problem
- Implement attention model to solve this problem

**Hours spent (optional):**

**Links (optional):**
