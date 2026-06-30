# Individual baseline tutorials for `src/data`

This guide is for running **one baseline at a time** on data under:

```text
E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW\src\data
```

It does not use the three-method comparison script as the main workflow.

## 0. Baseline map

| Baseline | Script | `src/data` input | Scope |
|---|---|---|---|
| GA | `src\experiments\GA\ga_cvrp_baseline.py` | `Solomon\*.txt`, `Holmberger\*.txt` | CVRP only |
| PyVRP | `src\experiments\PyVRP\evaluate_solomon_pyvrp.py` | `Solomon\*.txt`, `Holmberger\*.txt` | VRPTW, E disabled |
| PyVRP EVRP-TW pipeline | `src\experiments\PyVRP\solve_evrptw_pipeline.py` | project JSON / Schneider sample | PyVRP VRPTW + charging repair/checker |
| yd-kwon/POMO checkpoint | `src\experiments\ydkwon_pomo_method_comparison.py` | `Solomon\*.txt`, `Holmberger\*.txt` | CVRP model, TW checked after rollout |

## 1. Environments

From repo root:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
```

PyVRP / GA:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r src\requirements.txt
```

yd-kwon/POMO CPU:

```powershell
python -m venv .venv_pomo
.\.venv_pomo\Scripts\python.exe -m pip install --upgrade pip
.\.venv_pomo\Scripts\python.exe -m pip install -r src\requirements.txt
.\.venv_pomo\Scripts\python.exe -m pip install -r src\requirements-pomo-tools.txt
```

yd-kwon/POMO CUDA:

```powershell
python -m venv .venv_pomo_cuda
.\.venv_pomo_cuda\Scripts\python.exe -m pip install --upgrade pip
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements-pomo-cuda.txt
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements.txt
.\.venv_pomo_cuda\Scripts\python.exe -m pip install -r src\requirements-pomo-tools.txt
.\.venv_pomo_cuda\Scripts\python.exe -c "import torch; print('torch=' + torch.__version__); print('cuda_available=' + str(torch.cuda.is_available())); print('cuda_device=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))"
```

For PyVRP pipeline/checker imports:

```powershell
$env:PYTHONPATH = "src;src\experiments"
```

## 2. GA baseline only

This is a standalone GA baseline over Solomon-like `.txt` files. It does not call PyVRP or POMO.

Scope:

```text
CVRP only: distance + capacity. Time windows and EV constraints disabled.
```

Run one Solomon instance with all 100 customers:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\GA\ga_cvrp_baseline.py `
  --instance src\data\Solomon\C101.txt `
  --output-csv src\results\ga_srcdata_C101_100.csv `
  --seed 1234 `
  --pop-size 80 `
  --generations 50
```

Run only a sampled 20-customer case from C101:

```powershell
.\.venv\Scripts\python.exe src\experiments\GA\ga_cvrp_baseline.py `
  --instance src\data\Solomon\C101.txt `
  --client-count 20 `
  --output-csv src\results\ga_srcdata_C101_20.csv `
  --seed 1234 `
  --pop-size 80 `
  --generations 50
```

Run Holmberger:

```powershell
.\.venv\Scripts\python.exe src\experiments\GA\ga_cvrp_baseline.py `
  --instance src\data\Holmberger\C1_2_1.txt `
  --output-csv src\results\ga_srcdata_holmberger_C1_2_1.csv `
  --seed 1234 `
  --pop-size 240 `
  --generations 220
```

Parameters to tune:

| Argument | Meaning |
|---|---|
| `--client-count` | sample N customers from the instance; omit for all customers |
| `--pop-size` | GA population size |
| `--generations` | GA iteration count |
| `--mutation-prob` | reverse-mutation probability |
| `--elite-size` | number of best individuals kept each generation |
| `--tournament-size` | tournament selection size |
| `--seed` | reproducibility seed |

## 3. PyVRP baseline only

### 3.1 PyVRP on Solomon

Scope:

```text
VRPTW baseline: capacity + time windows. EV constraints disabled.
```

Run one instance:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\PyVRP\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --instance C101 `
  --runtime-seconds 1 `
  --seed 1234 `
  --output-csv src\results\pyvrp_srcdata_C101.csv
```

Run first five instances:

```powershell
.\.venv\Scripts\python.exe src\experiments\PyVRP\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Solomon `
  --limit 5 `
  --runtime-seconds 1 `
  --seed 1234 `
  --output-csv src\results\pyvrp_srcdata_solomon_limit5.csv
```

### 3.2 PyVRP on Holmberger

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\PyVRP\evaluate_solomon_pyvrp.py `
  --data-dir src\data\Holmberger `
  --instance C1_2_1 `
  --runtime-seconds 3 `
  --seed 1234 `
  --output-csv src\results\pyvrp_srcdata_holmberger_C1_2_1.csv
```

## 4. PyVRP EVRP-TW pipeline only

This is not plain PyVRP alone: it is PyVRP VRPTW routing plus charging-station repair and the independent EVRP-TW checker.

Scope:

```text
EVRP-TW via PyVRP baseline plus charging repair.
```

Project JSON smoke:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\solve_evrptw_pipeline.py `
  --instance src\data\smoke_test_instance.json `
  --runtime-seconds 2 `
  --seed 1 `
  --output src\results\srcdata_smoke_solution.json
```

Project JSON scale-up:

```powershell
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\solve_evrptw_pipeline.py `
  --instance src\data\scale_up_instance.json `
  --runtime-seconds 5 `
  --seed 1 `
  --output src\results\srcdata_scale_up_solution.json
```

Schneider-style sample:

```powershell
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\solve_evrptw_pipeline.py `
  --schneider src\data\schneider_sample.txt `
  --vehicles 2 `
  --runtime-seconds 2 `
  --seed 1 `
  --output src\results\srcdata_schneider_sample_solution.json
```

Explicit route checker:

```powershell
$env:PYTHONPATH = "src;src\experiments"
.\.venv\Scripts\python.exe src\experiments\PyVRP\parse_schneider_instance.py `
  src\data\schneider_sample.txt `
  --output src\results\srcdata_schneider_sample_converted.json `
  --vehicles 2 `
  --runtime-seconds 2 `
  --seed 1

.\.venv\Scripts\python.exe src\experiments\check_explicit_routes.py `
  --instance src\results\srcdata_schneider_sample_converted.json `
  --routes src\data\explicit_routes_sample.json
```

Do not report `schneider_sample.txt` as a benchmark reproduction. It is only a parser/checker sample.

## 5. yd-kwon/POMO pretrained checkpoint only

Scope:

```text
POMO CVRP checkpoint. Time-window/capacity feasibility checked after rollout. EV constraints disabled.
```

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

## 6. Run record template

```text
date:
baseline:
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

Use these labels:

- `CVRP only`
- `VRPTW, E disabled`
- `EVRP-TW via PyVRP baseline plus charging repair`
- `POMO CVRP checkpoint, TW checked after rollout, E disabled`
