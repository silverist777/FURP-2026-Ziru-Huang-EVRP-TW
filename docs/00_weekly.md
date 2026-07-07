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
- Experiment script: `src/experiments/week3_pyga_pyvrp_pomo.py`
- Summary results: `src/results/week3/week3_summary.md`
- Plots: `src/results/week3/plots/`
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
