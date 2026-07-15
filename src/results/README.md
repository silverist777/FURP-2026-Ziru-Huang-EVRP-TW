# Results and Visualizations

This directory contains **derived, reader-facing outputs**: figures, experiment
summaries, and short interpretation notes. Raw solver records and machine tables
are stored separately in [`../log/`](../log/).

## Weekly index

| Period | Main contents |
|---|---|
| [`week1/`](week1/) | initial POMO/PyVRP evaluations and GA progress plots |
| [`week2/`](week2/) | CVRP method comparison and EVRP-TW pipeline versions |
| [`week3/`](week3/) | repeated trials, hard-TW decoder, penalty studies, local rerun |
| [`week4/`](week4/) | four-instance pilot and 100/1000-client comparison |
| [`week5/`](week5/) | shared-fleet four-method comparison and focused diagnostics |

Each experiment group contains at least one PNG visualization. Most newly
generated groups use `overview.png` as the visual entry point. Rebuild them with:

```powershell
.\.venv\Scripts\python.exe src\experiments\tools\build_weekly_visualizations.py
```

Interpretation rule: hatched bars are infeasible outputs. Their distance is
shown for diagnosis, not as a valid improvement over a feasible solution.

## What belongs here

- PNG figures and plots;
- readable Markdown summaries and result-specific README files;
- small derived tables only when they materially help a reader.

Solver JSON, GA generation CSV, aggregate machine CSV, `.log`, and `.tsv` files
normally belong in `src/log/weekN/<experiment>/`. Classification is based on
purpose, not extension: a readable `summary.md` stays here, while a Markdown
file that is itself a raw machine dump would go to `src/log/`.
