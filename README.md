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

## 首屏极速上手（3 行价值 + 1 条命令）

- 给大龙虾自动搜索更优路由策略
- 上线前强制门禁，不达标直接拦截
- 产出可直接接入与可对外展示的结果文件

复制即用（Windows PowerShell）：

```powershell
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1; if ($LASTEXITCODE -ne 0) { exit 1 }; python -X utf8 apply_route_policy.py; python -X utf8 value_case.py; python -X utf8 render_gate_svg.py
```

结果卡片：
- `Overall: PASS/FAIL`：是否允许上线
- `route_policy.env`：可直接注入的大龙虾路由配置
- `business_value_case.json`：业务价值快照
- `gate_snapshot.svg`：可视化门禁证据图

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

## TL;DR（给大龙虾使用者）

你的大龙虾负责对话与执行；PhoenixDNA 负责三件事：
- 找更优路由策略
- 用门禁判断是否可上线
- 产出可直接注入的大龙虾配置

## 一键集成（马上看到效果）

Windows PowerShell：

```powershell
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1; if ($LASTEXITCODE -ne 0) { exit 1 }; python -X utf8 apply_route_policy.py; python -X utf8 value_case.py; python -X utf8 render_gate_svg.py
```

macOS / Linux：

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1 && python -X utf8 apply_route_policy.py && python -X utf8 value_case.py && python -X utf8 render_gate_svg.py
```

跑完立即得到：
- `Overall: PASS/FAIL`（门禁结论）
- `route_policy.env`（可直接接入）
- `business_value_case.json`（业务效果）
- `gate_snapshot.svg`（可视化证据）

## 和大龙虾的直接映射

- 大龙虾要选模型 / 选工具 → PhoenixDNA 自动搜索策略  
- 大龙虾要稳定上线 → `validate` 给硬门禁  
- 大龙虾要快速接入 → `apply_route_policy.py` 产出 `route_policy.env`  
- 大龙虾要对外证明优化有效 → `value_case.py` + `render_gate_svg.py` 产出证据

## 三种接入模式（按投入从低到高）

- **Gate-only**：只接 `validate`，用于 CI 阻断低质量策略
- **Gate + Route**：`evolution + apply_route_policy`，用于生产策略迭代
- **Full**：再加 `value_case + render_gate_svg`，用于汇报和评审

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
