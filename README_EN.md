# PhoenixDNA

> Turning “AI evolution” from an idea into an executable engineering loop: reproducible, gate-validated, and runtime-writable.

中文版本: [README.md](README.md)

<a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python"></a>
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey" alt="Platform">
<img src="https://img.shields.io/badge/Status-Research%20Prototype-orange" alt="Status">

<img src="./gate_snapshot.svg" alt="PhoenixDNA Gate Snapshot">

## What This Is

This is a minimal reproducible project to validate one core idea:  
**AI strategies can evolve automatically through selection, instead of manual tuning every time.**

The project provides three capability layers:
- **Research**: baselines, ablations, repeated statistics, and one-shot report generation.
- **Gate**: hard pre-deployment checks that fail fast if quality is below threshold.
- **Evolution**: population evolution (selection/crossover/mutation) with executable strategy output.

## Why It Matters

Many “evolutionary AI” projects stop at concept demos. This project focuses on engineering execution:
- Uses controlled comparisons, not subjective “feels better”.
- Uses strict quality gates before runtime entry.
- Writes learned best strategy back for direct reuse in later runs.

In one line:  
**This is not just a nice idea, but a working self-optimization pipeline.**

## Inspiration

This project starts from a practical engineering pain point:  
as Agent systems connect more models, tools, and routing rules, strategy search space explodes, while manual tuning becomes slower and less reliable.

We wanted concrete answers to three questions:
- Can we turn strategy tuning into strategy evolution, so the system searches better policies by itself?
- Can we bind optimization results to hard gates, so underperforming policies never enter runtime paths?
- Can we write back the best policy artifacts, so each run starts from the previous best point?

PhoenixDNA is the minimal executable answer to these three questions.

## Current Landscape

Many current “evolutionary AI” projects still break at one of these points:
- **Curves without admission criteria**: metrics look better, but no clear production gate.
- **Notebook-only results**: hard to reproduce across machines, parameters, and datasets.
- **Offline-only optimization**: best strategies are not directly consumable by runtime routing.

PhoenixDNA addresses this by:
- using `validate` mode as a hard gate with one-vote veto;
- exporting structured artifacts (JSON/CSV/TEX/SVG) for reproducibility and auditability;
- bridging experiment-to-runtime through `benchmark_route_policy.json` and `apply_route_policy.py`.

## Quick Start (3 Minutes)

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Run application gate validation (recommended first command)

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1
```

Expected outputs:
- `benchmark_research_report.json`
- `benchmark_application_gate.json`
- `benchmark_research_methods.csv`
- `benchmark_research_ablations.csv`
- `benchmark_research_stress.csv`
- `benchmark_research_tables.tex`

### 3) Run evolution mode

```bash
python -X utf8 dna_benchmark.py --mode evolution --dna-file phoenix_dna_quaternary_sample.json --limit 64 --generations 6 --population-size 24 --evolution-sample-size 32 --mutation-rate 0.08 --evolution-selection-ratio 0.25
```

Expected outputs:
- `benchmark_evolution_report.json`
- `benchmark_route_policy.json`

### 4) Generate business value snapshot

```bash
python -X utf8 value_case.py
```

Expected output:
- `business_value_case.json` with speedup, latency reduction, Top1 delta, and stress margin gain.

### 5) Generate visualization

```bash
python -X utf8 render_gate_svg.py
```

Expected output:
- `gate_snapshot.svg` for GitHub-ready gate result presentation.

### 6) Generate minimal integration entry

```bash
python -X utf8 apply_route_policy.py
```

Expected outputs:
- `route_policy.env`
- `apply_route_policy.ps1`
- `route_policy_summary.json`

Optional: write artifacts into `out/` to keep repository root clean:

```bash
python -X utf8 value_case.py --input-dir . --output-dir out
python -X utf8 render_gate_svg.py --input-dir . --output-dir out
python -X utf8 apply_route_policy.py --input-dir . --output-dir out
```

## How To Use This Project Quickly

If you want practical value today, choose one of these three adoption paths:

- **Path A: Gate-only integration (lowest effort)**  
  Run this in your CI/CD pipeline:

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1
```

  Rule: block deployment when exit code is non-zero.

- **Path B: Strategy search + routing write-back (recommended)**  
  Search best strategy first, then generate runtime route artifacts:

```bash
python -X utf8 dna_benchmark.py --mode evolution --dna-file phoenix_dna_quaternary_sample.json --limit 64 --generations 6 --population-size 24 --evolution-sample-size 32 --mutation-rate 0.08 --evolution-selection-ratio 0.25
python -X utf8 apply_route_policy.py
```

  `route_policy.env` can be injected directly into your service environment.

- **Path C: Business-facing value presentation (stakeholder-friendly)**  
  Generate both value snapshot and visual gate evidence:

```bash
python -X utf8 value_case.py
python -X utf8 render_gate_svg.py
```

  `business_value_case.json` + `gate_snapshot.svg` are ready for PRs, reviews, and weekly reports.

## Operator-Friendly Fast Track

If your team mostly uses tools and workflows (with minimal code changes), use this path:

1) **Validate first (one command)**

```bash
python -X utf8 dna_benchmark.py --mode validate --dna-file phoenix_dna_quaternary_sample.json --limit 64 --sample-size 32 --mutation-rate 0.1 --repeats 1
```

Only continue when you see `Overall: PASS`.

2) **Generate deployable route artifacts (one command)**

```bash
python -X utf8 apply_route_policy.py
```

Inject `route_policy.env` into your runtime environment variables.

3) **Generate stakeholder-ready evidence (two commands)**

```bash
python -X utf8 value_case.py
python -X utf8 render_gate_svg.py
```

You will get:
- `business_value_case.json` for business summary
- `gate_snapshot.svg` for visual gate evidence on repo landing pages

Guiding principle:  
**gate first, route second, presentation third.**

## Structure

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

## Core Innovations

- **Trial generation**: automatically generates candidate strategies and compares them.
- **Quality filtering**: strategies that fail gate thresholds are rejected.
- **Inheritance loop**: better strategies enter next generations through crossover and mutation.
- **Runtime landing**: best result is exportable for runtime routing.

This shifts AI systems from repeated manual tuning to continuous automatic optimization.

## Reproducibility Promise

- Every key mode runs with single commands.
- All report artifacts are auto-generated to files.
- Supports fixed-parameter reruns for clean experiment comparison.

## Use Cases

- Agent routing strategy search
- Model/tool selection optimization
- Pre-release quality gate automation
- Evolutionary strategy experiments requiring explainability and reproducibility

## Roadmap

- Add more public baseline tasks
- Add multi-objective optimization (success rate / latency / cost)
- Improve visualization and comparison outputs
- Harden standalone open-source release process
