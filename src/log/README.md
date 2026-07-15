# Raw Experiment Log

This directory stores original or machine-oriented experimental evidence that
was previously mixed with reader-facing results. It is organized by week and
then by experiment group.

```text
log/
├── week1/
├── week2/
├── week3/
├── week4/
└── week5/
```

Typical contents are solver JSON records, per-generation CSV files, aggregate
machine CSV files, console logs, and status TSV files. Files are placed here
because of their role as raw evidence—not merely because of their extension.
Human-readable summaries remain in [`../results/`](../results/).

Do not edit historical records to improve their appearance. Generate or rebuild
figures with `src/experiments/tools/build_weekly_visualizations.py` instead.

The current Track B raw data is in
[`week5/four-methods-vehicle-limit/`](week5/four-methods-vehicle-limit/); its
visual results are in
[`../results/week5/four-methods-vehicle-limit/`](../results/week5/four-methods-vehicle-limit/).
