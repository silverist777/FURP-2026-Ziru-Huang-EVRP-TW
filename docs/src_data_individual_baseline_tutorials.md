# Individual baseline tutorials for `src/data`

This guide is for running **one baseline at a time**. Most commands use data under:

```text
E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW\src\data
```

It does not use the three-method comparison script as the main workflow.
The `py-ga-VRPTW` GA baseline is the exception: it uses the external submodule's
own `py-ga-VRPTW/data/json` instances.

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
.\.venv\Scripts\python.exe src\experiments\GA\run_py_ga_vrptw.py `
  --instance C101 `
  --ind-size 100 `
  --output-csv src\results\py_ga_vrptw_C101_100.csv `
  --export-csv
```

to:

```bash
src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw.py \
  --instance C101 \
  --ind-size 100 \
  --output-csv src/results/py_ga_vrptw_C101_100.csv \
  --export-csv
```

CUDA note for macOS: the `*_cuda` commands are for Windows machines with
NVIDIA CUDA. On macOS, use the CPU commands unless you are deliberately running
on a separate NVIDIA CUDA machine.

## 0. Baseline map

| Baseline | Script | `src/data` input | Scope |
|---|---|---|---|
| py-ga-VRPTW GA | `src\experiments\GA\run_py_ga_vrptw.py` | `py-ga-VRPTW\data\json\*.json` | Solomon-style VRPTW, external submodule |
| PyVRP | `src\experiments\PyVRP\evaluate_solomon_pyvrp.py` | `Solomon\*.txt`, `Holmberger\*.txt` | VRPTW, E disabled |
| PyVRP EVRP-TW pipeline | `src\experiments\PyVRP\solve_evrptw_pipeline.py` | project JSON / Schneider sample | PyVRP VRPTW + charging repair/checker |
| yd-kwon/POMO checkpoint | `src\experiments\ydkwon_pomo_method_comparison.py` | `Solomon\*.txt`, `Holmberger\*.txt` | CVRP model, TW checked after rollout |

## 1. Environments

From repo root:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
```

PyVRP / py-ga-VRPTW:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r src\requirements.txt
git submodule update --init py-ga-VRPTW
.\.venv\Scripts\python.exe -m pip install -r py-ga-VRPTW\requirements.txt
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

## 2. py-ga-VRPTW GA baseline only

This baseline uses the external `py-ga-VRPTW` submodule, not the local
fallback GA script. Initialise the submodule first if the directory is empty:

Windows PowerShell:

```powershell
git submodule update --init py-ga-VRPTW
.\.venv\Scripts\python.exe -m pip install -r py-ga-VRPTW\requirements.txt
```

macOS zsh/bash:

```bash
git submodule update --init py-ga-VRPTW
src/.venv_pyvrp/bin/python -m pip install -r py-ga-VRPTW/requirements.txt
```

Scope:

```text
VRPTW GA from py-ga-VRPTW. Uses py-ga-VRPTW/data/json instances.
```

Run one Solomon instance with all 100 customers:

```powershell
cd E:\WorkSpace\FURP-2026-Ziru-Huang-EVRP-TW
.\.venv\Scripts\python.exe src\experiments\GA\run_py_ga_vrptw.py `
  --instance C101 `
  --ind-size 100 `
  --output-csv src\results\py_ga_vrptw_C101_100.csv `
  --pop-size 80 `
  --generations 50 `
  --export-csv
```

macOS zsh/bash:

```bash
src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw.py \
  --instance C101 \
  --ind-size 100 \
  --output-csv src/results/py_ga_vrptw_C101_100.csv \
  --pop-size 80 \
  --generations 50 \
  --export-csv
```

Run only the first 25 customers of R101, matching the original sample style:

```bash
src/.venv_pyvrp/bin/python src/experiments/GA/run_py_ga_vrptw.py \
  --instance R101 \
  --ind-size 25 \
  --output-csv src/results/py_ga_vrptw_R101_25.csv \
  --pop-size 80 \
  --generations 50
```

Do not report this as Holmberger or EVRP-TW. `py-ga-VRPTW` is a Solomon-style
VRPTW GA baseline.

Parameters to tune:

| Argument | Meaning |
|---|---|
| `--instance` | instance name from `py-ga-VRPTW/data/json`, e.g. `C101`, `R101` |
| `--ind-size` | number of customers used by py-ga-VRPTW, e.g. `25`, `50`, `100` |
| `--pop-size` | GA population size |
| `--generations` | GA iteration count |
| `--crossover-prob` | crossover probability |
| `--mutation-prob` | inverse-mutation probability |
| `--unit-cost`, `--init-cost`, `--wait-cost`, `--delay-cost` | py-ga-VRPTW cost weights |

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
- `py-ga-VRPTW Solomon-style VRPTW, E disabled`
- `POMO CVRP checkpoint, TW checked after rollout, E disabled`

## 7. Plot convergence / improvement curves

For `py-ga-VRPTW` CSVs, the plotting helper reads the real per-generation
`max_fitness` values and plots best cost as `1 / max_fitness`.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe src\experiments\render_progress_plots.py `
  --input-csv src\results\py_ga_vrptw_C101_100.csv `
  --field convergence_curve `
  --output-dir src\results\py_ga_vrptw_C101_100_progress_plots
```

macOS zsh/bash:

```bash
src/.venv_pyvrp/bin/python src/experiments/render_progress_plots.py \
  --input-csv src/results/py_ga_vrptw_C101_100.csv \
  --field convergence_curve \
  --output-dir src/results/py_ga_vrptw_C101_100_progress_plots
```

Use `--field improvement_over_time` for the improvement curve. The script
writes `.png` matplotlib line charts.
