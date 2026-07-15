# py-ga-VRPTW / PyVRP / yd-kwon POMO tutorials

This tutorial is for running the datasets already stored under:

```text
E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW\src\data
```

The external `py-ga-VRPTW` GA baseline is separate from `src/data`: it reads
instances from `py-ga-VRPTW/data/json`. Do not treat the local comparison
script's fallback GA as a `py-ga-VRPTW` result.

The command blocks below are written for **Windows PowerShell**. If you run the
same tutorial on **macOS zsh/bash**, replace the command style as follows.

| Windows PowerShell | macOS zsh/bash |
|---|---|
| `cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW` | `cd /Users/emt/Workspace/FURP-2026-Ziru-Huang-EVRP-TW` or your local repo path |
| `src\data\Solomon\C101.txt` | `src/data/Solomon/C101.txt` |
| `.\.venv\Scripts\python.exe` | `src/.venv_pyvrp/bin/python` in this repo, or `.venv/bin/python` only if you created a root `.venv` yourself |
| `.\.venv_pomo\Scripts\python.exe` | `.venv_pomo/bin/python` |
| `.\.venv_pomo_cuda\Scripts\python.exe` | `.venv_pomo_cuda/bin/python` |
| PowerShell line continuation: `` ` `` | zsh/bash line continuation: `\` |
| `$env:PYTHONPATH = "src;src\experiments"` | `export PYTHONPATH="src:src/experiments"` |

macOS setup examples for this repo's existing PyVRP / py-ga-VRPTW environment:

```bash
cd /Users/emt/Workspace/FURP-2026-Ziru-Huang-EVRP-TW
src/.venv_pyvrp/bin/python -m pip install --upgrade pip
src/.venv_pyvrp/bin/python -m pip install -r src/requirements.txt
```

If `src/.venv_pyvrp/bin/python` is missing, recreate it first:

```bash
/Users/emt/Workspace/CS/anaconda3/bin/python -m venv src/.venv_pyvrp
src/.venv_pyvrp/bin/python -m pip install --upgrade pip
src/.venv_pyvrp/bin/python -m pip install -r src/requirements.txt
```

```bash
python3 -m venv .venv_pomo
.venv_pomo/bin/python -m pip install --upgrade pip
.venv_pomo/bin/python -m pip install -r src/requirements.txt
.venv_pomo/bin/python -m pip install -r src/requirements-pomo-tools.txt
```

For EVRP-TW pipeline/checker scripts on macOS, set imports with:

```bash
export PYTHONPATH="src:src/experiments"
```

Then convert a multi-line PowerShell command like this:

```powershell
.\.venv\Scripts\python.exe src\experiments\legacy\cvrp\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --instance C101
```

to:

```bash
src/.venv_pyvrp/bin/python src/experiments/legacy/cvrp/evaluate_solomon_pyvrp.py \
  --data-dir src/data/Solomon \
  --instance C101
```

CUDA note for macOS: the `*_cuda` commands and `setup_pomo_cuda_env.ps1` are
for Windows machines with NVIDIA CUDA. On macOS, use the CPU commands unless
you are deliberately running on a separate NVIDIA CUDA machine.

## 0. Data map

| Data path | Format | What can use it now |
|---|---|---|
| `src\data\Solomon\*.txt` + `.sol` | Solomon VRPTW | PyVRP VRPTW eval, yd-kwon/POMO checkpoint eval, local CVRP comparison; `py-ga-VRPTW` uses matching bundled JSON instances |
| `src\data\Holmberger\*.txt` + `.sol` | Solomon-like larger VRPTW | PyVRP eval, yd-kwon/POMO checkpoint eval, local CVRP comparison; not bundled by `py-ga-VRPTW` by default |
| `src\data\A\*.vrp` + `.sol` | CVRPLIB Augerat A | not used by the retained yd-kwon checkpoint scripts |
| `src\data\smoke_test_instance.json` | project JSON | PyVRP EVRP-TW pipeline |
| `src\data\scale_up_instance.json` | project JSON | PyVRP EVRP-TW pipeline |
| `src\data\schneider_sample.txt` | Schneider-style EVRP-TW sample | PyVRP parser / pipeline |
| `src\data\explicit_routes_sample.json` | explicit route list | EVRP-TW route checker |

Important:

- The GA baseline for the experiment is the external `py-ga-VRPTW` submodule.
- `py-ga-VRPTW` reads `py-ga-VRPTW\data\json\<instance>.json`, not `src\data` directly.
- `src\experiments\legacy\cvrp\cvrp_method_comparison.py` still contains a local fallback GA
  for same-data CVRP comparison only. Do not report that row as `py-ga-VRPTW`.
- PyVRP is the main current path for VRPTW and EVRP-TW repair/checker runs on `src/data`.
- The retained POMO path is the upstream yd-kwon/POMO CVRP checkpoint. The old
  local RL4CO experiment folder has been removed.

## 1. Environment setup

Start from the repo root:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
```

PyVRP environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r src\requirements.txt
git submodule update --init py-ga-VRPTW
.\.venv\Scripts\python.exe -m pip install -r py-ga-VRPTW\requirements.txt
```

yd-kwon/POMO / combined method environment, CPU:

```powershell
python -m venv .venv_pomo
.\.venv_pomo\Scripts\python.exe -m pip install --upgrade pip
.\.venv_pomo\Scripts\python.exe -m pip install -r src\requirements.txt
.\.venv_pomo\Scripts\python.exe -m pip install -r src\requirements-pomo-tools.txt
```

yd-kwon/POMO / combined method environment, CUDA:

```powershell
python -m venv .venv_pomo_cuda
.\.venv_pomo_cuda\Scripts\python.exe -m pip install --upgrade pip
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements-pomo-cuda.txt
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements.txt
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements-pomo-tools.txt
```

CUDA check:

```powershell
.\.venv_pomo_cuda\Scripts\python.exe -c "import torch; print('torch=' + torch.__version__); print('cuda_available=' + str(torch.cuda.is_available())); print('cuda_device=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))"
```

For scripts that import shared helpers, set:

```powershell
$env:PYTHONPATH = "src;src\experiments"
```

## 2. Local same-data CVRP comparison, not py-ga-VRPTW

Use this only when you need one table where every method consumes the same
`src/data` cases. The GA rows here come from the repo's local fallback GA, not
from `py-ga-VRPTW`.

It builds:

- 20, 50, and 100-client cases from `src\data\Solomon\C101.txt`;
- one larger case from `src\data\Holmberger\C1_2_1.txt`;
- local fallback GA, PyVRP, and upstream yd-kwon/POMO rows.

Scope: **CVRP only**.

CPU quick run:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv_pomo\Scripts\python.exe src\experiments\cvrp_method_comparison.py `
  --device cpu `
  --solomon src\data\Solomon\C101.txt `
  --holmberger src\data\Holmberger\C1_2_1.txt `
  --output-dir src\log\week2\method-comparison-cvrp-srcdata-quick `
  --pyvrp-runtime-seconds 1 `
  --ga-pop-size 80 `
  --ga-generations 50 `
  --no-pomo-augmentation
```

CUDA run:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv_pomo_cuda\Scripts\python.exe src\experiments\cvrp_method_comparison.py `
  --device cuda `
  --solomon src\data\Solomon\C101.txt `
  --holmberger src\data\Holmberger\C1_2_1.txt `
  --output-dir src\log\week2\method-comparison-cvrp-srcdata-cuda `
  --pyvrp-runtime-seconds 1 `
  --ga-pop-size 240 `
  --ga-generations 220
```

Output files:

```text
src\log\week2\method-comparison-cvrp-srcdata-quick\cvrp_method_comparison.csv
src\log\week2\method-comparison-cvrp-srcdata-quick\cvrp_method_comparison.md
```

To view only local fallback GA rows after the run:

```powershell
Import-Csv src\log\week2\method-comparison-cvrp-srcdata-quick\cvrp_method_comparison.csv |
  Where-Object { $_.algorithm -eq "GA" }
```

Change data by replacing:

```powershell
--solomon src\data\Solomon\R101.txt
--holmberger src\data\Holmberger\RC1_2_1.txt
```

## 3. py-ga-VRPTW GA baseline

This is the GA baseline to use when the experiment asks for `py-ga-VRPTW`.
It calls the external submodule's `gavrptw.core.run_gavrptw`; the wrapper only
passes arguments and copies the generated CSV to a repo-local output path.

Initialize the submodule and install its requirements:

```powershell
git submodule update --init py-ga-VRPTW
.\.venv\Scripts\python.exe -m pip install -r py-ga-VRPTW\requirements.txt
```

macOS zsh/bash:

```bash
git submodule update --init py-ga-VRPTW
src/.venv_pyvrp/bin/python -m pip install -r py-ga-VRPTW/requirements.txt
```

Run C101 with all 100 customers:

```powershell
.\.venv\Scripts\python.exe src\experiments\legacy\prototypes\run_py_ga_vrptw.py `
  --instance C101 `
  --ind-size 100 `
  --pop-size 80 `
  --generations 50 `
  --export-csv `
  --output-csv src\log\week1\ga-progress\py_ga_vrptw_C101_100.csv
```

macOS zsh/bash:

```bash
src/.venv_pyvrp/bin/python src/experiments/legacy/prototypes/run_py_ga_vrptw.py \
  --instance C101 \
  --ind-size 100 \
  --pop-size 80 \
  --generations 50 \
  --export-csv \
  --output-csv src/log/week1/ga-progress/py_ga_vrptw_C101_100.csv
```

Main py-ga-VRPTW knobs:

| Argument | Meaning | Quick | Larger |
|---|---|---:|---:|
| `--instance` | bundled JSON instance name | `C101` | `R101`, `C204`, etc. |
| `--ind-size` | customer count used by py-ga-VRPTW | `25` | `100` |
| `--pop-size` | population size | `80` | `240+` |
| `--generations` | generations | `50` | `220+` |
| `--crossover-prob` | crossover probability | `0.85` | tune and record |
| `--mutation-prob` | inverse mutation probability | `0.02` | tune and record |

Record the constraint scope as:

```text
Solomon-style VRPTW GA from external py-ga-VRPTW. EV constraints disabled.
```

## 4. PyVRP on `src/data`

### 4.1 `src\data\Solomon`

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\legacy\cvrp\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --instance C101 `
  --runtime-seconds 1 `
  --seed 1234 `
  --output-csv src\log\week1\pyvrp-solomon-eval\pyvrp_srcdata_C101.csv
```

First five:

```powershell
.\.venv\Scripts\python.exe src\experiments\legacy\cvrp\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --limit 5 `
  --runtime-seconds 1 `
  --seed 1234 `
  --output-csv src\log\week1\pyvrp-solomon-eval\pyvrp_srcdata_solomon_limit5.csv
```

### 4.2 `src\data\Holmberger`

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\legacy\cvrp\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Holmberger `
  --instance C1_2_1 `
  --runtime-seconds 3 `
  --seed 1234 `
  --output-csv src\log\week1\pyvrp-holmberger-eval\pyvrp_srcdata_holmberger_C1_2_1.csv
```

The script name says Solomon, but the parser can read the bundled Holmberger Solomon-like `.txt` files.

### 4.3 Project JSON instances

Smoke JSON:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\methods\pyvrp\solve_evrptw_pipeline.py `
  --instance src\data\smoke_test_instance.json `
  --runtime-seconds 2 `
  --seed 1 `
  --output src\log\week2\evrptw-pipeline\srcdata_smoke_solution.json
```

Scale-up JSON:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\methods\pyvrp\solve_evrptw_pipeline.py `
  --instance src\data\scale_up_instance.json `
  --runtime-seconds 5 `
  --seed 1 `
  --output src\log\week2\evrptw-pipeline\srcdata_scale_up_solution.json
```

### 4.4 Schneider-style sample

Convert to JSON:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\methods\pyvrp\parse_schneider_instance.py `
  src\data\schneider_sample.txt `
  --output src\log\week2\evrptw-pipeline\srcdata_schneider_sample_converted.json `
  --vehicles 2 `
  --runtime-seconds 2 `
  --seed 1
```

Solve through the EVRP-TW pipeline:

```powershell
.\.venv\Scripts\python.exe src\experiments\methods\pyvrp\solve_evrptw_pipeline.py `
  --schneider src\data\schneider_sample.txt `
  --vehicles 2 `
  --runtime-seconds 2 `
  --seed 1 `
  --output src\log\week2\evrptw-pipeline\srcdata_schneider_sample_solution.json
```

Check explicit routes:

```powershell
.\.venv\Scripts\python.exe src\experiments\check_explicit_routes.py `
  --instance src\log\week2\evrptw-pipeline\srcdata_schneider_sample_converted.json `
  --routes src\data\explicit_routes_sample.json
```

Do not report `schneider_sample.txt` as a benchmark reproduction; it is only a parser/checker sample.

## 5. yd-kwon/POMO checkpoint on `src/data`

CPU:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv_pomo\Scripts\python.exe src\experiments\ydkwon_pomo_method_comparison.py `
  --device cpu `
  --solomon src\data\Solomon\C101.txt `
  --holmberger src\data\Holmberger\C1_2_1.txt `
  --output-dir src\log\week2\pomo-srcdata-cpu
```

CUDA with augmentation:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv_pomo_cuda\Scripts\python.exe src\experiments\ydkwon_pomo_method_comparison.py `
  --device cuda `
  --augmentation `
  --solomon src\data\Solomon\C101.txt `
  --holmberger src\data\Holmberger\C1_2_1.txt `
  --output-dir src\log\week2\pomo-srcdata-cuda-aug
```

Scope:

```text
POMO checkpoint is CVRP-only. Time-window/capacity feasibility is checked after rollout; EV constraints are disabled.
```

## 6. What to record

```text
date:
method:
script:
src/data file or folder:
command:
constraint scope:
seed:
runtime / epochs:
important parameters:
output path:
objective / gap:
feasibility:
notes:
```

Use explicit labels:

- `CVRP only`
- `VRPTW, E disabled`
- `EVRP-TW via PyVRP baseline plus charging repair`
- `py-ga-VRPTW Solomon-style VRPTW, E disabled`
- `POMO CVRP checkpoint, TW checked after rollout, E disabled`

## 7. Plot convergence / improvement curves

For `py-ga-VRPTW` CSVs generated by section 3, the plotting helper reads the
real per-generation `max_fitness` values and plots best cost as
`1 / max_fitness`.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe src\experiments\tools\render_progress_plots.py `
  --input-csv src\log\week1\ga-progress\py_ga_vrptw_C101_100.csv `
  --field convergence_curve `
  --output-dir src\results\week1\ga-progress\py-ga-C101-100
```

macOS zsh/bash:

```bash
src/.venv_pyvrp/bin/python src/experiments/tools/render_progress_plots.py \
  --input-csv src/log/week1/ga-progress/py_ga_vrptw_C101_100.csv \
  --field convergence_curve \
  --output-dir src/results/week1/ga-progress/py-ga-C101-100
```

Use `--field improvement_over_time` to plot the improvement curve instead. The
script writes `.png` matplotlib line charts.

For local fallback GA rows from `cvrp_method_comparison.py`, the same script can
still read the `convergence_curve` / `improvement_over_time` JSON columns. Label
those plots as `local fallback GA, CVRP only`.

## 8. Common pitfalls

If imports fail:

```powershell
$env:PYTHONPATH = "src;src\experiments"
```

If CUDA fails:

```powershell
.\.venv_pomo_cuda\Scripts\python.exe -c "import torch; print('torch=' + torch.__version__); print('cuda_available=' + str(torch.cuda.is_available())); print('cuda_device=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))"
```

If you need one same-data local comparison table, use `cvrp_method_comparison.py`
and label its GA row `local fallback GA, CVRP only`. If the experiment asks for
`py-ga-VRPTW`, run section 3 instead.
