# GA / PyVRP / yd-kwon POMO tutorials for `src/data`

This tutorial is for running the datasets already stored under:

```text
E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW\src\data
```

All commands are for you to run manually in PowerShell.

## 0. Data map

| Data path | Format | What can use it now |
|---|---|---|
| `src\data\Solomon\*.txt` + `.sol` | Solomon VRPTW | PyVRP VRPTW eval, yd-kwon/POMO checkpoint eval, GA/PyVRP/yd-kwon POMO pure-CVRP comparison |
| `src\data\Holmberger\*.txt` + `.sol` | Solomon-like larger VRPTW | PyVRP eval, yd-kwon/POMO checkpoint eval, GA/PyVRP/yd-kwon POMO pure-CVRP comparison |
| `src\data\A\*.vrp` + `.sol` | CVRPLIB Augerat A | not used by the retained yd-kwon checkpoint scripts |
| `src\data\smoke_test_instance.json` | project JSON | PyVRP EVRP-TW pipeline |
| `src\data\scale_up_instance.json` | project JSON | PyVRP EVRP-TW pipeline |
| `src\data\schneider_sample.txt` | Schneider-style EVRP-TW sample | PyVRP parser / pipeline |
| `src\data\explicit_routes_sample.json` | explicit route list | EVRP-TW route checker |

Important:

- The GA that currently reads `src/data` directly is the GA inside `src\experiments\cvrp_method_comparison.py`.
- That GA comparison is **CVRP only**: distance + capacity; time windows and EV constraints are disabled.
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

## 2. One command to compare GA / PyVRP / yd-kwon POMO on `src/data`

This is the current cleanest same-data comparison. It builds:

- 20, 50, and 100-client cases from `src\data\Solomon\C101.txt`;
- one larger case from `src\data\Holmberger\C1_2_1.txt`;
- GA, PyVRP, and upstream yd-kwon/POMO rows.

Scope: **CVRP only**.

CPU quick run:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv_pomo\Scripts\python.exe src\experiments\cvrp_method_comparison.py `
  --device cpu `
  --solomon src\data\Solomon\C101.txt `
  --holmberger src\data\Holmberger\C1_2_1.txt `
  --output-dir src\results\method_comparison_cvrp_srcdata_quick `
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
  --output-dir src\results\method_comparison_cvrp_srcdata_cuda `
  --pyvrp-runtime-seconds 1 `
  --ga-pop-size 240 `
  --ga-generations 220
```

Output files:

```text
src\results\method_comparison_cvrp_srcdata_quick\cvrp_method_comparison.csv
src\results\method_comparison_cvrp_srcdata_quick\cvrp_method_comparison.md
```

To view only GA rows after the run:

```powershell
Import-Csv src\results\method_comparison_cvrp_srcdata_quick\cvrp_method_comparison.csv |
  Where-Object { $_.algorithm -eq "GA" }
```

Change data by replacing:

```powershell
--solomon src\data\Solomon\R101.txt
--holmberger src\data\Holmberger\RC1_2_1.txt
```

## 3. GA on `src/data`

Current status: there is no standalone GA CLI for every `src/data` format. Use the GA branch inside:

```text
src\experiments\cvrp_method_comparison.py
```

Main GA knobs:

| Argument | Meaning | Quick | Larger |
|---|---|---:|---:|
| `--ga-pop-size` | population size | `80` | `240+` |
| `--ga-generations` | generations | `50` | `220+` |
| `--seed` | random seed | `1234` | record every run |

Record the constraint scope as:

```text
CVRP only: distance + capacity. Time windows and EV constraints disabled.
```

## 4. PyVRP on `src/data`

### 4.1 `src\data\Solomon`

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\PyVRP\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --instance C101 `
  --runtime-seconds 1 `
  --seed 1234 `
  --output-csv src\results\pyvrp_srcdata_C101.csv
```

First five:

```powershell
.\.venv\Scripts\python.exe src\experiments\PyVRP\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --limit 5 `
  --runtime-seconds 1 `
  --seed 1234 `
  --output-csv src\results\pyvrp_srcdata_solomon_limit5.csv
```

### 4.2 `src\data\Holmberger`

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\PyVRP\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Holmberger `
  --instance C1_2_1 `
  --runtime-seconds 3 `
  --seed 1234 `
  --output-csv src\results\pyvrp_srcdata_holmberger_C1_2_1.csv
```

The script name says Solomon, but the parser can read the bundled Holmberger Solomon-like `.txt` files.

### 4.3 Project JSON instances

Smoke JSON:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\solve_evrptw_pipeline.py `
  --instance src\data\smoke_test_instance.json `
  --runtime-seconds 2 `
  --seed 1 `
  --output src\results\srcdata_smoke_solution.json
```

Scale-up JSON:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\solve_evrptw_pipeline.py `
  --instance src\data\scale_up_instance.json `
  --runtime-seconds 5 `
  --seed 1 `
  --output src\results\srcdata_scale_up_solution.json
```

### 4.4 Schneider-style sample

Convert to JSON:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\parse_schneider_instance.py `
  src\data\schneider_sample.txt `
  --output src\results\srcdata_schneider_sample_converted.json `
  --vehicles 2 `
  --runtime-seconds 2 `
  --seed 1
```

Solve through the EVRP-TW pipeline:

```powershell
.\.venv\Scripts\python.exe src\experiments\PyVRP\solve_evrptw_pipeline.py `
  --schneider src\data\schneider_sample.txt `
  --vehicles 2 `
  --runtime-seconds 2 `
  --seed 1 `
  --output src\results\srcdata_schneider_sample_solution.json
```

Check explicit routes:

```powershell
.\.venv\Scripts\python.exe src\experiments\check_explicit_routes.py `
  --instance src\results\srcdata_schneider_sample_converted.json `
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
  --output-dir src\results\ydkwon_pomo_srcdata_cpu
```

CUDA with augmentation:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv_pomo_cuda\Scripts\python.exe src\experiments\ydkwon_pomo_method_comparison.py `
  --device cuda `
  --augmentation `
  --solomon src\data\Solomon\C101.txt `
  --holmberger src\data\Holmberger\C1_2_1.txt `
  --output-dir src\results\ydkwon_pomo_srcdata_cuda_aug
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
- `POMO CVRP checkpoint, TW checked after rollout, E disabled`

## 7. Common pitfalls

If imports fail:

```powershell
$env:PYTHONPATH = "src;src\experiments"
```

If CUDA fails:

```powershell
.\.venv_pomo_cuda\Scripts\python.exe -c "import torch; print('torch=' + torch.__version__); print('cuda_available=' + str(torch.cuda.is_available())); print('cuda_device=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))"
```

If you need a fair GA/PyVRP/yd-kwon POMO comparison, use `cvrp_method_comparison.py` and label it `CVRP only`.
