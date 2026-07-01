# Week 3 Lab Report: PyVRP vs py-ga-VRPTW vs yd-kwon/POMO


## Step 1: Define the Comparison Target

- Testing method:
  - `yd-kwon/POMO`
- Baselines:
  - `PyVRP`
  - `py-ga-VRPTW`
- Main difference:
  - `yd-kwon/POMO` is a learning-based CVRP policy using the upstream pretrained CVRP100 checkpoint.
  - `PyVRP` uses hybrid genetic search and explicitly enforces VRPTW capacity and time-window constraints.
  - `py-ga-VRPTW` is an external genetic algorithm implementation for Solomon-style VRPTW.
- Question:
  - What is the advantage of POMO, and what does it lose when time-window feasibility is checked?

## Step 2: Choose Fair Test Cases

Initial plan:

- Small and medium: Solomon-style instance set `C101.txt`.
- Large: Holmberger instance set `R1_10_9.txt`.

Final fair comparison used:

- `C101_20`: first 20 customers from `src/data/Solomon/C101.txt`.
- `C101_50`: first 50 customers from `src/data/Solomon/C101.txt`.
- `C101_100`: first 100 customers from `src/data/Solomon/C101.txt`.

Reason: `R1_10_9.txt` has 1000 customers. The external `py-ga-VRPTW` repository only ships Solomon 100-customer JSON instances, and the retained `yd-kwon/POMO` model is a CVRP100 checkpoint. Therefore `R1_10_9` is recorded as a limitation/failure case rather than mixed into an unfair three-method table.

## Step 3: Decide What to Record

For every run, the experiment records:

| Field | Meaning |
|---|---|
| `instance_name`, `instance_size` | Case name and customer count |
| `method_name` | PyVRP, py-ga-VRPTW, or yd-kwon/POMO |
| `objective_value` | Route distance under the post-run checker |
| `runtime_seconds` | Wall-clock runtime |
| `feasibility_status` | Solomon time-window/capacity check result |
| `vehicles_used` | Number of routes/vehicles |
| `constraint_violations` | Missing customers, duplicates, TW violations, capacity violations, depot-return violations |
| `random_seed` | Seed used for stochastic methods |
| `best_solution_found` | Route list |
| `convergence_curve` | Available for py-ga-VRPTW |
| `search_steps` | Generations/population or inference action count |

Raw and cleaned outputs:

- Raw records: [week3_raw_records.csv](../src/results/week3/week3_raw_records.csv)
- Aggregated table: [week3_summary_by_method_size.csv](../src/results/week3/week3_summary_by_method_size.csv)
- Markdown summary: [week3_summary.md](../src/results/week3/week3_summary.md)
- Raw logs/py-ga curves: [raw/](../src/results/week3/raw/)

## Step 4: Run Repeated Trials

Repeated trials:

- Seeds: `1234`, `2026`, `114514`.
- Sizes: `20`, `50`, `100`.
- Runs per method: `3 sizes * 3 seeds = 9`.
- Total records: `27`.

Experiment commands:

```bash
cd /Users/emt/Workspace/FURP-2026-Ziru-Huang-EVRP-TW
git submodule update --init external/POMO

src/.venv_pyvrp/bin/python src/experiments/week3_pyga_pyvrp_pomo.py \
  --method pyga \
  --output-dir src/results/week3 \
  --sizes 20 50 100 \
  --seeds 1234 2026 114514 \
  --pyga-pop-size 80 \
  --pyga-generations 50

src/.venv_pyvrp/bin/python src/experiments/week3_pyga_pyvrp_pomo.py \
  --method pyvrp \
  --output-dir src/results/week3 \
  --sizes 20 50 100 \
  --seeds 1234 2026 114514 \
  --pyvrp-runtime-seconds 1

PYTHONPYCACHEPREFIX=/tmp/furp_week3_pycache python3 \
  src/experiments/week3_pyga_pyvrp_pomo.py \
  --method pomo \
  --output-dir src/results/week3 \
  --sizes 20 50 100 \
  --seeds 1234 2026 114514 \
  --device cpu

src/.venv_pyvrp/bin/python src/experiments/week3_pyga_pyvrp_pomo.py \
  --method aggregate \
  --output-dir src/results/week3
```

Environment:

- macOS CPU run.
- PyVRP / py-ga environment: `src/.venv_pyvrp`, Python 3.13.9.
- PyVRP version: `0.13.4`.
- DEAP version used by py-ga-VRPTW: `1.4.4`.
- POMO environment: system `python3`, Python 3.9.6, torch `2.8.0`, CUDA unavailable.
- `yd-kwon/POMO` submodule commit: `d7c3d6e`.
- `py-ga-VRPTW` submodule commit: `8e005ca`.

## Step 5: Organize Results Clearly

Aggregated results:

| Size group | Size | Method | Runs | Feasible rate | Best objective | Avg objective | Std objective | Avg runtime (s) | Avg vehicles | Gap to best observed |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| small | 20 | PyVRP | 3 | 1.000 | 175.374 | 175.374 | 0.000 | 1.001 | 3.000 | 0.000% |
| small | 20 | py-ga-VRPTW | 3 | 0.000 | 226.155 | 268.536 | 30.027 | 0.232 | 2.000 | 28.956% |
| small | 20 | yd-kwon/POMO | 3 | 0.000 | 315.817 | 315.817 | 0.000 | 0.010 | 4.000 | 80.082% |
| medium | 50 | PyVRP | 3 | 1.000 | 363.248 | 363.248 | 0.000 | 1.003 | 5.000 | 0.000% |
| medium | 50 | py-ga-VRPTW | 3 | 0.000 | 1196.947 | 1217.793 | 18.884 | 0.318 | 5.667 | 229.512% |
| medium | 50 | yd-kwon/POMO | 3 | 0.000 | 407.030 | 407.030 | 0.000 | 0.018 | 5.000 | 12.053% |
| large | 100 | PyVRP | 3 | 1.000 | 828.937 | 828.937 | 0.000 | 1.011 | 10.000 | 0.000% |
| large | 100 | py-ga-VRPTW | 3 | 0.000 | 3607.984 | 3686.905 | 65.746 | 0.497 | 11.333 | 335.254% |
| large | 100 | yd-kwon/POMO | 3 | 0.000 | 835.890 | 835.890 | 0.000 | 0.055 | 10.000 | 0.839% |

Figures:

![Objective by size](../src/results/week3/plots/objective_by_size.png)

![Runtime by size](../src/results/week3/plots/runtime_by_size.png)


![py-ga convergence for seed 1234](../src/results/week3/plots/pyga_convergence_seed1234.png)


The convergence figure above plots the best-so-far objective, so it becomes flat
after the GA finds no better historical best. The per-generation best objective
is plotted separately below.

![py-ga per-generation best objective for seed 1234](../src/results/week3/plots/pyga_generation_best_seed1234.png)



## Step 6: Analyze, Do Not Just Display

Objective value:

- PyVRP gives the best feasible objective on all three sizes.
- POMO is very close to PyVRP on 100 customers: best/avg objective `835.890` vs PyVRP `828.937`, only `0.839%` worse by distance.
- POMO is worse on 20 and 50 customers, especially on 20 customers. This matches the fact that the checkpoint is trained for CVRP100, not small custom subsets.
- py-ga-VRPTW performs poorly under this short run setting. The objective grows much faster than the other methods as size increases.

Runtime:

- POMO is the fastest method by far: about `0.010s`, `0.018s`, and `0.055s` for 20/50/100 customers.
- py-ga-VRPTW is also faster than PyVRP in this configuration, but its solutions are not feasible under the Solomon time-window checker.
- PyVRP is around `1s` because it was deliberately given `MaxRuntime=1s`.

Feasibility:

- PyVRP is the only method with `100%` feasibility under the Solomon time-window/capacity checker.
- POMO has good distance behavior at 100 customers but `0%` TW feasibility because the upstream checkpoint is CVRP-only.
- py-ga-VRPTW also has `0%` TW feasibility in this run. Its exported objective was normalized to distance by using `unit_cost=1`, `init_cost=0`, `wait_cost=0`, `delay_cost=0`; this made objective comparison cleaner, but it also means time-window penalties were not part of the optimized cost.

Trade-off:

- POMO's main advantage is inference speed. It produces a full route extremely quickly.
- Its main weakness is constraint mismatch: the model does not know Solomon time windows or EV constraints.
- PyVRP is slower, but it is much more reliable when feasibility matters.

## Step 7: Discuss Failure Cases

Failure case 1: POMO ignores time windows.

- The POMO checkpoint used here is `yd-kwon/POMO` CVRP100 pretrained checkpoint.
- It handles coordinates, demand, and capacity, but not ready time / due time.
- After post-checking its routes against Solomon time windows, all runs are infeasible.
- This is not a coding crash; it is a modeling mismatch.

Failure case 2: py-ga-VRPTW under this setting does not satisfy TW.

- The run used `unit_cost=1`, `init_cost=0`, `wait_cost=0`, `delay_cost=0` to compare route distance against PyVRP/POMO.
- Because delay cost was disabled, time-window violations were not punished in the GA objective.
- Future runs should tune `wait_cost` and `delay_cost`, increase generations, and compare feasibility again.

Failure case 3: Holmberger `R1_10_9` was not included in the fair three-way table.

- `R1_10_9` has 1000 customers.
- `py-ga-VRPTW` ships 100-customer Solomon JSON data and its parser assumes the Solomon 100-customer structure.
- The retained POMO checkpoint is CVRP100, so a 1000-customer Holmberger comparison would not answer the same question.
- A fair large-scale experiment should either use methods that all support 1000 customers, or retrain/adapt POMO and convert py-ga inputs carefully.

## Discussion

The results show that POMO's advantage is speed, not feasibility robustness. On the 100-customer case, POMO's route distance is close to PyVRP, which suggests that the learned CVRP policy captures useful routing structure. However, once Solomon time windows are enforced after rollout, the POMO solution fails. Therefore, POMO cannot currently replace a VRPTW/EVRP-TW solver without a time-window-aware model, repair operator, or feasibility layer.

PyVRP is the strongest baseline for this week because it returns feasible VRPTW solutions consistently within the fixed 1-second runtime. py-ga-VRPTW needs more careful parameterization before it can be a fair feasibility baseline; in this quick setting, its convergence curve improves only slightly and the final routes still violate many time windows.

## Conclusion

This week I compared `PyVRP`, external `py-ga-VRPTW`, and upstream `yd-kwon/POMO` on C101 subsets of 20, 50, and 100 customers with three seeds. POMO is much faster than the heuristic solvers and becomes distance-competitive on 100 customers, but it is infeasible under Solomon time-window checks because the checkpoint is CVRP-only. PyVRP is slower but consistently feasible and gives the best feasible objective. The next step should be to either add a repair/checking layer after POMO rollout or find/retrain a time-window-aware neural model before using POMO as an EVRP-TW method.
