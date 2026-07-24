# 三组稳定性实验暂停快照

- 快照时间：2026-07-22 22:36:40 +08:00
- 状态：按用户要求暂停；相关 runner、PowerShell 子进程和当前 Python solver 已停止。
- 实验清单：原始 `week5_three_group_stability`，RC/10 仍为 `rc102C10`；本快照没有应用后续候选实例调整。
- 固定 seed：1
- 硬车辆上限：`ceil((clients + stations) / 4)`，未放宽任何约束。

## 当前覆盖

- 本次 runner 请求：三组 × 5/10/15 clients × 5 methods = 45 jobs。
- 完整原子记录：41/45；每个完整 job 均含 `runner.json`、`result.json` 和 fresh `checker.json`。
- 严格可行：25/41 个已完成 job。
- 超时：0。
- 暂停时未完成：
  - `RC-rc103C15-vns_ts-seed-0001`（运行中被暂停，没有完整 runner/checker）
  - `RC-rc103C15-pomo_repair-seed-0001`
  - `RC-rc103C15-pyga_checked-seed-0001`
  - `RC-rc103C15-routefinder_repair-seed-0001`
- 三组 100-client 共 15 个 job 尚未启动。

## 已完成单元的严格可行计数

| clients | PyVRP | VNS/TS | POMO | pyGA | RouteFinder |
|---:|---:|---:|---:|---:|---:|
| 5 | 3/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| 10 | 2/3 | 2/3 | 0/3 | 0/3 | 2/3 |
| 15 | 3/3 | 2/2 | 0/2 | 0/2 | 2/2 |

15-client 的非 PyVRP 分母只有 2，是因为 RC/15 的其余任务尚未完成。

## 已知解释

`rc102C10` 在原约束和 `K=4` 下至少需要 5 辆车。独立精确诊断找到互斥客户团
`{C70, C49, C45, C26, C11}`，任意两点均不能组成一条能源、充电和时间窗均可行的路线，
因此该实例不可能在不改约束时达到 4 车可行。五个方法在该实例均失败与此一致。

同家族同规模候选 `rc108C10` 仍为 10 clients、4 stations、`K=4`，已在临时诊断中由
RouteFinder 得到 4 车、distance 430 的 fresh-checker 可行解；该替换尚未写入本快照的正式 manifest。

## 文件布局与完整性

- `raw/`：暂停时的全部原始任务目录、日志与 batch index。
- `results/`：暂停后重新生成的 `runs.csv`、`cells.csv`、`failures.csv`、`summary.json` 和 `summary.md`。
- `protocol/`：当时的 manifest、runner、validator、summarizer、checker、fleet policy、loader、converter、repair 与 RouteFinder compaction 源码。
- `sha256sums.csv`：除自身外每个快照文件的字节数和 SHA-256。

后续实验必须写入新的 raw/result 目录；不要覆盖本目录。若正式切换到 `rc108C10`，应使用新的实验 revision，
并把新旧 manifest 与结果分开报告。
