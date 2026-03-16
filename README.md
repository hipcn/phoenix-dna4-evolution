# PhoenixDNA

> 把 "AI 进化" 从概念变成可运行的工程闭环：可复现、可门禁、可回写。

English Version: [README_EN.md](README_EN.md)

<a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python"></a>
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey" alt="Platform">
<img src="https://img.shields.io/badge/Status-Research%20Prototype-orange" alt="Status">

<img src="./gate_snapshot.svg" alt="PhoenixDNA Gate Snapshot">

## 这是什么

这是一个最小可复现项目，验证一件事：  
**AI 策略可以像自然选择一样自动迭代，而不是每次都靠人工调参。**

项目提供三层能力：
- **Research**：基线、消融、重复统计，一次性产出报告与表格。
- **Gate**：上线前硬门槛校验，不过线就失败。
- **Evolution**：种群进化（选择/交叉/变异），并导出可执行策略。

## 为什么值得关注

很多“进化 AI”停留在概念层；这个项目强调工程可执行性：
- 有对照，不靠“感觉变好”。
- 有门禁，不让低质量策略进入运行链路。
- 有回写，让“学到的最优策略”能被下一次运行直接使用。

一句话：  
**不是展示一个漂亮想法，而是交付一个能跑的自优化流程。**

## 灵感来源

这个项目来自一个很现实的工程痛点：  
当 Agent 系统接入更多模型、工具和路由规则后，策略空间会爆炸，人工调参越来越慢、越来越脆弱。

我们想回答三个直接问题：
- 能不能把“调策略”变成“进化策略”，让系统自己搜索更优解？
- 能不能把“优化结果”绑定到门禁，不达标就不允许进入生产链路？
- 能不能把“最优策略”自动落盘，下一次运行开局就站在上一次最优点上？

PhoenixDNA 就是这三个问题的最小工程答案。

## 现状分析

今天大量“进化 AI”项目的常见断点是：
- **只展示曲线，不展示准入条件**：指标看起来更好，但没有明确“可上线”标准。
- **只在 Notebook 里有效**：换机器、换参数、换数据后很难复现。
- **只做离线实验，不做运行回写**：学到的策略无法直接驱动线上路由。

PhoenixDNA 的取舍是：
- 用 `validate` 模式做硬门禁，提供一票否决；
- 用结构化产物（JSON/CSV/TEX/SVG）保证复现和审计；
- 用 `benchmark_route_policy.json` + `apply_route_policy.py` 打通“实验 → 运行时”。

## 快速开始（3 分钟）

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 跑应用门禁验证（推荐第一个命令）

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1
```

预期结果：终端显示 `APPLICATION GATE` 并给出 `Overall: PASS`，同时生成：
- `benchmark_research_report.json`
- `benchmark_application_gate.json`
- `benchmark_research_methods.csv`
- `benchmark_research_ablations.csv`
- `benchmark_research_stress.csv`
- `benchmark_research_tables.tex`

### 3) 跑进化模式

```bash
python -X utf8 dna_benchmark.py --mode evolution --dna-file phoenix_dna_quaternary_sample.json --limit 64 --generations 6 --population-size 24 --evolution-sample-size 32 --mutation-rate 0.08 --evolution-selection-ratio 0.25
```

预期结果：生成 `benchmark_evolution_report.json`、`benchmark_route_policy.json`，并输出最优代与适应度历史。

### 4) 生成业务价值快照

```bash
python -X utf8 value_case.py
```

预期结果：生成 `business_value_case.json`，包含吞吐提升、时延下降、Top1变化和压力边际增益。

### 5) 生成可视化图

```bash
python -X utf8 render_gate_svg.py
```

预期结果：生成 `gate_snapshot.svg`，可直接放到 GitHub 展示门禁结果。

### 6) 生成最小集成入口

```bash
python -X utf8 apply_route_policy.py
```

预期结果：生成 `route_policy.env`、`apply_route_policy.ps1`、`route_policy_summary.json`。

可选：将产物统一写入 `out/`（保持仓库根目录整洁）：

```bash
python -X utf8 value_case.py --input-dir . --output-dir out
python -X utf8 render_gate_svg.py --input-dir . --output-dir out
python -X utf8 apply_route_policy.py --input-dir . --output-dir out
```

## 如何快速利用这个项目

如果你只想“今天就接上去”，按下面三种模式选一种：

- **模式 A：只做上线门禁（最低接入成本）**  
  在你的 CI/CD 里运行：

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1
```

  规则：命令返回非 0 就阻断发布。

- **模式 B：做策略搜索 + 路由回写（推荐）**  
  先搜索最优策略，再生成运行时路由：

```bash
python -X utf8 dna_benchmark.py --mode evolution --dna-file phoenix_dna_quaternary_sample.json --limit 64 --generations 6 --population-size 24 --evolution-sample-size 32 --mutation-rate 0.08 --evolution-selection-ratio 0.25
python -X utf8 apply_route_policy.py
```

  产物 `route_policy.env` 可直接注入你的服务环境变量。

- **模式 C：做管理层可见的价值展示（汇报友好）**  
  自动生成业务快照 + 可视化图：

```bash
python -X utf8 value_case.py
python -X utf8 render_gate_svg.py
```

  产物 `business_value_case.json` + `gate_snapshot.svg` 可直接用于 PR、周报和评审会。

## 龙虾使用者快速上手

如果你是“以工具为主、少改代码”的使用者，建议直接走这条路径：

1) **先验证可用性（1 条命令）**

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1
```

看到 `Overall: PASS` 再继续下一步。

2) **再产出可落地策略（1 条命令）**

```bash
python -X utf8 apply_route_policy.py
```

拿到 `route_policy.env` 后，直接注入你的运行环境变量。

3) **最后做对外展示（2 条命令）**

```bash
python -X utf8 value_case.py
python -X utf8 render_gate_svg.py
```

你会得到：
- `business_value_case.json`（业务指标摘要，适合汇报）
- `gate_snapshot.svg`（可视化证据图，适合放在仓库首页）

这条路径的核心思路是：  
**先过门禁，再接路由，最后补展示。**

## 目录结构

```text
phoenixdna/
├─ apply_route_policy.py
├─ value_case.py
├─ render_gate_svg.py
├─ dna_benchmark.py
├─ phoenix_dna_quaternary_sample.json
├─ requirements.txt
└─ tools/
   └─ dna_codec.py
```

## 核心创新点（大众可读版）

- **会试错**：自动产生多种策略并比较好坏。  
- **会淘汰**：不过门槛的策略直接淘汰。  
- **会继承**：优胜策略通过交叉和变异进入下一代。  
- **会落地**：最优结果可以导出给运行时路由使用。  

这意味着：  
AI 系统从“人工反复调”走向“自动持续优化”。

## 可复现承诺

- 所有关键模式都可通过单命令运行。
- 报告产物全部自动落盘，不需要手工整理。
- 支持固定参数重跑，便于对比不同实验设置。

## 适用场景

- Agent 路由策略搜索
- 模型/工具选择策略优化
- 上线前质量门禁自动化
- 需要“可解释 + 可复现”的进化式策略实验

## 路线图

- 增加更多公开基线任务
- 增加多目标优化（成功率/延迟/成本）
- 输出更完整的可视化与对比报告
- 完善独立开源仓库发布流程

---

如果你也在做 Agent 或自优化系统，欢迎基于这个最小骨架继续扩展。
