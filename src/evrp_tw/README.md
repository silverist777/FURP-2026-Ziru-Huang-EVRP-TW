# EVRP-TW Baseline 环境

这个目录先作为 PyVRP / VRPTW / EVRP-TW 的实验起点。

## 1. 激活环境

当前可用环境是 `.venv_pyvrp`，它使用 Python 3.13，可以安装当前 PyVRP。

```bash
cd /Users/emt/Workspace/evrp_tw
source .venv_pyvrp/bin/activate
```

检查版本：

```bash
python --version
python -c "from importlib.metadata import version; print(version('pyvrp'))"
```

## 2. 重新安装依赖

如果以后换电脑或环境坏了，重新执行：

```bash
python -m pip install -r requirements.txt
```

## 3. 跑第一个 VRPTW smoke test

```bash
python scripts/smoke_test_pyvrp.py
```

预期结果是输出一个小型 VRPTW 解，包括车辆路线、目标值、距离、总时长、运行时间，以及每条路线的时间窗服务 schedule。

## 4. 当前进度与下一步

已经完成：

1. 跑通 PyVRP 环境。
2. 跑通一个 tiny CVRP smoke test。
3. 把 smoke test 升级成带 time windows 的 VRPTW 小例子。

下一步建议：

1. 写一个更独立的 feasibility checker，检查路线的容量、到达时间、等待时间、服务时间和时间窗违反情况。
2. 把 tiny instance 抽成可复用的数据文件，方便后面换 benchmark。
3. 再加入 EVRP-TW 的电池、电站和充电逻辑。
