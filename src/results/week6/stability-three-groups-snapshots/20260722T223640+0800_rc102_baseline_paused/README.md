# 三组稳定性实验：暂停快照可视化

本目录参考 Week 5 的 “Four methods, vehicles limit” 表达方式，用一张总览图和一张 best-route petals 图展示 C/R/RC 三组、5/10/15 clients、五种方法在暂停时的结果。这里的图只使用冻结快照，不读取仍可能变化的在线实验目录。

## 数据范围

- 冻结快照：[`src/log/week5/stability-three-groups-snapshots/20260722T223640+0800_rc102_baseline_paused`](../../../../log/week5/stability-three-groups-snapshots/20260722T223640+0800_rc102_baseline_paused/)
- 计划矩阵：3 groups × 3 sizes × 5 methods，共 45 个 job。
- 已完成：41/45。
- fresh checker 严格可行：25/41。
- 超时：0。
- RC/15 仅 PyVRP 完成，其余 4/5 方法尚未运行，因此该格的最优路线是 provisional。
- RC/10 的 5 个方法均已完成，但在当前 `K=4` 约束下没有严格可行结果。
- 100-client 实验不属于该暂停快照可视化的范围。

生成器不会使用 `runs.csv` 中指向在线目录的绝对结果路径，而是从快照内的 `raw/runs/...` 重建每个 job 的 `runner.json`、`result.json` 和 `checker.json` 路径。

## 输出文件

- [`overview.png`](overview.png)：按 C/R/RC 分组比较 distance、wall runtime 和 vehicles。
- [`best-route-petals.png`](best-route-petals.png)：九个 group/size 格子的最优严格可行路线；RC/10 保留无可行结果占位符，RC/15 标为 provisional。
- [`best-route-selection.csv`](best-route-selection.csv)：petals 的机器可读选择表。
- [`visualization-metadata.json`](visualization-metadata.json)：输入范围、计数、选择规则及完整性信息。

## 可行性门槛与图例

一个已完成 job 只有同时满足以下 fresh checker 条件，才会参与 distance、vehicles 和 best-route 的比较：

```text
fresh_recheck == true
validation_status == "valid"
contract_valid == true
strict_feasible == true
```

距离取自 `checker.report.total_distance`。同一实例出现相同最短距离时，按 manifest 方法顺序 `PyVRP → VNS/TS → POMO → pyGA → RouteFinder` 确定 petals 的唯一选择。

图例语义如下：

- 实色结果：fresh checker 严格可行。
- 斜线阴影：job 已完成，但不是严格可行结果；其 distance/vehicles 不作为有效目标值比较。
- `×`：job 在暂停快照中尚未完成。
- runtime 面板可显示所有已完成 job 的 wall time，失败结果以阴影区分。
- vehicles 面板中的 fleet cap 是当前约束上限，不因可视化而改变。

## Best-route 选择

| Group | Clients | Instance | Selected method | Distance | Vehicles | 状态 |
|---|---:|---|---|---:|---:|---|
| C | 5 | c101C5 | VNS/TS | 259 | 2 | final in snapshot |
| R | 5 | r104C5 | PyVRP | 136 | 2 | final in snapshot |
| RC | 5 | rc105C5 | POMO | 239 | 3 | final in snapshot |
| C | 10 | c101C10 | PyVRP | 387 | 3 | final in snapshot |
| R | 10 | r102C10 | PyVRP | 248 | 3 | final in snapshot |
| C | 15 | c103C15 | VNS/TS | 384 | 3 | final in snapshot |
| R | 15 | r102C15 | VNS/TS | 414 | 5 | final in snapshot |
| RC | 15 | rc103C15 | PyVRP | 399 | 4 | provisional：仅 1/5 完成 |

RC/10 不在上述 8 项选择中：`rc102C10` 在当前 `K=4` 下没有 fresh-checker 严格可行结果，因此 petals 图显示 `No strict-feasible result (K=4)`，不会用失败路线代替。

## 快照完整性

SHA-256 清单包含 251 个受校验文件。当前已知仅 `results/summary.md` 与清单记录不一致；其余 250 项匹配，包括可视化依赖的 `raw/` job 记录与 `protocol/` 输入。生成器不读取 `results/summary.md`，因此该已知差异不会进入图表数据；完整性警告仍保留在 metadata 中，便于审计。

## 复现

从仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe src\experiments\tools\build_stability_snapshot_visualizations.py `
  --snapshot-dir "src\log\week5\stability-three-groups-snapshots\20260722T223640+0800_rc102_baseline_paused" `
  --output-dir "src\results\week5\stability-three-groups-snapshots\20260722T223640+0800_rc102_baseline_paused"
```

该命令只重建派生图表和元数据，不运行 solver，也不应修改冻结快照。后续补跑 RC/15 或 100-client 时，应建立新的 revision/快照及输出目录，不覆盖本目录。
