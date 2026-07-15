# EVRPTW Four-Method Experiment Handoff

## 1. Objective

Run the following four methods on the same four Schneider EVRPTW instances, for a total of 16 runs:

| Method | Entry point |
| --- | --- |
| PyVRP + EVRP-TW repair | `src/experiments/methods/pyvrp/solve_evrptw_pipeline.py` |
| POMO + EVRP-TW repair | `src/experiments/methods/pomo/pomo_evrptw_repair_pipeline.py` |
| Tabu-assisted VNS/TS | `src/experiments/methods/vns_ts/vns_ts_evrptw_baseline.py` |
| py-ga-VRPTW + shared checker | `src/experiments/methods/ga/run_py_ga_vrptw_checked.py` |

Instances:

- `src/data/evrptw_instances/c101_21.txt` — 100 customers
- `src/data/evrptw_instances/c101C5.txt` — 5 customers
- `src/data/evrptw_instances/c101C10.txt` — 10 customers
- `src/data/evrptw_instances/c103C15.txt` — 15 customers

All methods use seed `1`. Every result must be validated by the shared EVRP-TW checker.

## 2. Vehicle Policy

The previous rule $K=\lceil n/8\rceil$ has been cancelled for this experiment.

To remove the practical fleet restriction while keeping the input finite, pass:

```text
vehicles = number of customers
```

Therefore:

| Instance | `--vehicles` |
| --- | ---: |
| `c101_21` | 100 |
| `c101C5` | 5 |
| `c101C10` | 10 |
| `c103C15` | 15 |

This permits the worst case of one vehicle per customer. The reported `vehicle_count` is the number actually used, not this upper bound.

## 3. Current Handoff State

Completed locally:

- all four PyVRP + repair runs;
- all four PyVRP outputs are checker-feasible;
- GA wrapper syntax and Schneider customer-name mapping were verified.

Not completed:

- POMO + repair: `c101_21` was started on CPU and manually interrupted after a long repair stage; no completed POMO JSON should be treated as available;
- the remaining three POMO runs;
- all four VNS/TS runs;
- all four GA runs;
- final 16-row aggregation.

Current completed PyVRP files:

```text
src/log/week5/four-methods-unlimited/c101_21_pyvrp_repair.json
src/log/week5/four-methods-unlimited/c101C5_pyvrp_repair.json
src/log/week5/four-methods-unlimited/c101C10_pyvrp_repair.json
src/log/week5/four-methods-unlimited/c103C15_pyvrp_repair.json
```

Current PyVRP snapshot:

| Instance | Feasible | Distance | Vehicles used | Runtime (s) | Charging count |
| --- | ---: | ---: | ---: | ---: | ---: |
| `c101_21` | yes | 1058 | 12 | 128.668 | 8 |
| `c101C5` | yes | 248 | 3 | 10.004 | 2 |
| `c101C10` | yes | 387 | 3 | 10.090 | 5 |
| `c103C15` | yes | 350 | 3 | 10.146 | 5 |

> If runtime is part of the formal comparison, rerun all 16 methods on the same computer. Do not mix the above Mac CPU runtimes with Windows/GPU runtimes in one runtime comparison. If only solution quality is needed, copy these four JSON files and run the remaining 12 cases.

## 4. Files That Must Be Transferred

The current work is not fully committed. Before using a fresh clone on the other computer, either commit/push the required files or copy the working tree directly.

Required uncommitted/untracked content includes:

```text
src/data/evrptw_instances/
src/experiments/methods/ga/run_py_ga_vrptw_checked.py
docs/EVRPTW_FOUR_METHODS_HANDOFF.md
```

Copy `src/log/week5/four-methods-unlimited/` as well if retaining the four completed PyVRP results.

The GA wrapper must include Schneider support. Verify on the target computer:

```powershell
.\src\.venv_pyvrp\Scripts\python.exe src\experiments\methods\ga\run_py_ga_vrptw_checked.py --help
```

The help output must contain `--schneider`. If it does not, the target computer has the old wrapper and cannot run the GA portion of this experiment correctly.

## 5. Repository and Submodules

Open PowerShell in the repository root, then run:

```powershell
git submodule update --init --recursive
git submodule status
```

Expected submodule commits for this handoff:

```text
external/POMO  d7c3d6ea580499a53e874fe9e065f69e799a8551
py-ga-VRPTW   b5598e401bc0357e0b12f30fe07fd9ac5cb8c40d
```

Confirm that the pretrained checkpoint exists:

```powershell
Test-Path external\POMO\NEW_py_ver\CVRP\POMO\result\saved_CVRP100_model\checkpoint-30500.pt
```

The command must return `True`.

## 6. Python Environments on Windows

### 6.1 PyVRP, VNS/TS, and GA environment

Python 3.11–3.13 is suitable. The previous working environment used Python 3.13.9.

```powershell
py -3.13 -m venv src\.venv_pyvrp
.\src\.venv_pyvrp\Scripts\python.exe -m pip install --upgrade pip
.\src\.venv_pyvrp\Scripts\python.exe -m pip install -r src\requirements.txt
.\src\.venv_pyvrp\Scripts\python.exe -m pip install -r py-ga-VRPTW\requirements.txt
```

Set the shared module path for the current PowerShell window:

```powershell
$env:PYTHONPATH = "src;src\experiments"
```

### 6.2 POMO CUDA environment

POMO uses a pretrained CVRP100 checkpoint. It does not train a model in this experiment.

On an NVIDIA/CUDA computer, create the POMO environment with Python 3.11:

```powershell
py -3.11 -m venv .venv_pomo_cuda
.\.venv_pomo_cuda\Scripts\python.exe -m pip install --upgrade pip
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements-pomo-cuda.txt
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements-pomo-tools.txt
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements.txt
```

Verify CUDA:

```powershell
.\.venv_pomo_cuda\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

Do not use `--device cuda` unless `torch.cuda.is_available()` prints `True`.

## 7. Preflight Checks

```powershell
$env:PYTHONPATH = "src;src\experiments"

.\src\.venv_pyvrp\Scripts\python.exe -m py_compile src\experiments\methods\ga\run_py_ga_vrptw_checked.py
.\src\.venv_pyvrp\Scripts\python.exe src\experiments\tests\evrptw_checker_self_test.py
.\src\.venv_pyvrp\Scripts\python.exe src\experiments\tests\evrptw_pipeline_self_test.py --schneider src\data\evrptw_instances\c101C5.txt
```

Create the result directory:

```powershell
$ResultDir = "src\log\week5\four-methods-unlimited"
New-Item -ItemType Directory -Force $ResultDir | Out-Null
```

## 8. Shared Case Configuration

Run this once in PowerShell:

```powershell
$Cases = @(
    @{ Name = "c101_21"; Clients = 100 },
    @{ Name = "c101C5"; Clients = 5 },
    @{ Name = "c101C10"; Clients = 10 },
    @{ Name = "c103C15"; Clients = 15 }
)

$ResultDir = "src\log\week5\four-methods-unlimited"
$Py = ".\src\.venv_pyvrp\Scripts\python.exe"
$PomoPy = ".\.venv_pomo_cuda\Scripts\python.exe"
$env:PYTHONPATH = "src;src\experiments"
```

## 9. Run Commands

Do not add `--fail-on-unsolved` to the batch commands. An infeasible run is a valid experimental outcome and must still produce JSON so the other cases continue.

### 9.1 PyVRP + EVRP-TW repair — four runs

Skip this section only if retaining the four transferred PyVRP JSON files and not comparing runtime across computers.

```powershell
foreach ($Case in $Cases) {
    & $Py src\experiments\methods\pyvrp\solve_evrptw_pipeline.py `
        --schneider "src\data\evrptw_instances\$($Case.Name).txt" `
        --vehicles $Case.Clients `
        --runtime-seconds 10 `
        --seed 1 `
        --output "$ResultDir\$($Case.Name)_pyvrp_repair.json"
}
```

### 9.2 POMO + EVRP-TW repair — four runs

```powershell
foreach ($Case in $Cases) {
    & $PomoPy src\experiments\methods\pomo\pomo_evrptw_repair_pipeline.py `
        --schneider "src\data\evrptw_instances\$($Case.Name).txt" `
        --vehicles $Case.Clients `
        --seed 1 `
        --device cuda `
        --max-candidates 4 `
        --output "$ResultDir\$($Case.Name)_pomo_repair.json"
}
```

If CUDA is unavailable, replace `--device cuda` with `--device cpu`. The CPU run of `c101_21` can spend a long time in label-setting charging repair even after POMO inference finishes.

### 9.3 Tabu-assisted VNS/TS — four runs

```powershell
foreach ($Case in $Cases) {
    & $Py src\experiments\methods\vns_ts\vns_ts_evrptw_baseline.py `
        --schneider "src\data\evrptw_instances\$($Case.Name).txt" `
        --vehicles $Case.Clients `
        --seed 1 `
        --iterations 80 `
        --neighbors-per-iteration 20 `
        --output "$ResultDir\$($Case.Name)_vns_ts.json"
}
```

### 9.4 py-ga-VRPTW + shared checker — four runs

The updated wrapper automatically converts Schneider customers to py-ga's contiguous internal IDs and maps the resulting routes back to the original names.

```powershell
foreach ($Case in $Cases) {
    & $Py src\experiments\methods\ga\run_py_ga_vrptw_checked.py `
        --schneider "src\data\evrptw_instances\$($Case.Name).txt" `
        --instance $Case.Name `
        --ind-size $Case.Clients `
        --vehicles $Case.Clients `
        --pop-size 80 `
        --generations 50 `
        --seed 1 `
        --customize-data `
        --output "$ResultDir\$($Case.Name)_pyga_checked.json" `
        --output-csv "$ResultDir\$($Case.Name)_pyga.csv" `
        --output-log "$ResultDir\$($Case.Name)_pyga.log"
}
```

Method boundary: GA does not insert charging stations. Its routes are checked against the same EVRP-TW constraints, so energy-infeasible GA results must remain reported as infeasible rather than being silently repaired by a different method.

## 10. Monitoring and Failure Handling

- Run the four method sections sequentially; do not run methods concurrently when runtime is a comparison metric.
- Do not silently retry a failed run with another seed, more vehicles, fewer POMO candidates, or a different search budget.
- If a process crashes, preserve its console output and record the exact command.
- If imposing a hard timeout, use the same declared timeout rule for every relevant run and record it separately from algorithm runtime.
- `--runtime-seconds 10` limits only the PyVRP search stage. Repair/checker time is additional; use `elapsed_runtime_seconds` from the JSON as end-to-end runtime.
- POMO CUDA accelerates neural inference, but the EVRP-TW repair remains a separate stage and may still dominate runtime.

## 11. Aggregate and Verify

After all runs:

```powershell
& $Py src\experiments\tools\week4_collect_results.py `
    --results-dir $ResultDir `
    --output-csv "$ResultDir\four_methods_summary.csv" `
    --output-md "$ResultDir\four_methods_summary.md"
```

Count solution JSON files:

```powershell
(Get-ChildItem $ResultDir -Filter *.json).Count
```

Expected count: `16`.

Validate every JSON file:

```powershell
Get-ChildItem $ResultDir -Filter *.json | ForEach-Object {
    & $Py -m json.tool $_.FullName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Invalid JSON: $($_.FullName)" }
}
```

The final table must retain:

- feasible and infeasible rows;
- total distance;
- actual vehicle count;
- end-to-end runtime;
- served, missing, and duplicate customers;
- time-window, capacity, and energy violations;
- charging count and charging time;
- failure/unsupported/timeout reason.

## 12. Completion Checklist

- [ ] Required uncommitted data and GA wrapper changes are present on the target computer.
- [ ] Both submodules are initialized at the expected commits.
- [ ] POMO checkpoint exists.
- [ ] PyVRP/GA/VNS environment passes self-tests.
- [ ] CUDA preflight passes, or POMO is explicitly switched to CPU.
- [ ] Four PyVRP results exist.
- [ ] Four POMO results exist.
- [ ] Four VNS/TS results exist.
- [ ] Four GA results exist.
- [ ] Exactly 16 solution JSON files exist.
- [ ] All JSON files pass parsing validation.
- [ ] `four_methods_summary.csv` and `four_methods_summary.md` are generated.
- [ ] Runtime comparisons use runs from the same computer and environment.
