# Repository Structure

This repo mixes three kinds of things:

1. product code
2. research/evaluation tooling
3. generated run artifacts

The goal of this file is to make it obvious which is which.

## Core Source

These files are the actual pipeline implementation:

- `run_pipeline.py`: main orchestrator
- `fanin_rank.py`: structural fan-in step
- `git_history_rank.py`: git history step
- `vulnerability_scan.py`: vulnerability baseline step
- `llm_reachability_scan.py`: LLM semantic ranking step
- `prioritize_targets.py`: final scoring and merge step
- `generate_report.py`: HTML report builder
- `connect_provider.py`: provider credential storage

These are the "real cogs" of the system.

## CLI Layer

- `riskrank_cli/cli.py`: command router for `riskrank`
- `riskrank_cli/paths.py`: package-owned paths like prompt and config locations
- `riskrank_cli/PROMPT.md`: packaged prompt used by the LLM step

This layer is intentionally thin. It exists so users get one stable command, while the pipeline logic stays in the stage modules.

## Evaluation Tooling

- `evaluation/run_benchmark_suite.py`: runs RiskRank across many benchmark repos
- `evaluation/compute_metrics.py`: computes metrics from benchmark outputs
- `evaluation/benchmark_repos.json`: benchmark suite definition

Use this folder when doing experiments, thesis evaluation, or comparisons across many projects.

## Examples and Demo Targets

- `examples/`: vulnerable example applications or fixtures used for demos/testing

These are inputs to the tool, not part of the tool itself.

## Run Outputs

- `runs/`: saved single-project outputs

Typical contents of one run:

```text
runs/<run_id>/
├── fanin/
├── git_history/
├── vulnerabilities/
├── llm/
├── prioritization/
├── manifest.json
└── report.html
```

These are generated artifacts. They are useful for demos and user studies, but they are not source code.

## Optional UI

- `frontend/`: optional Nuxt frontend work

This is separate from the CLI and can be ignored if you only care about the pipeline.

## Supporting Material

- `docs/assets/`: diagrams and supporting images
- `skills-lock.json`: local tool/agent metadata for the development environment
- `bin/`: helper binaries like `bearer`
- `Makefile`: legacy wrapper for older flows

## Mental Model

If you are new to the repo, read it in this order:

1. `README.md`
2. `run_pipeline.py`
3. `generate_report.py`
4. the step modules (`fanin_rank.py`, `git_history_rank.py`, `vulnerability_scan.py`, `llm_reachability_scan.py`, `prioritize_targets.py`)
5. `evaluation/` only if you need benchmarks

## What Is Safe To Ignore

For most users, you can ignore:

- `frontend/`
- `evaluation/results/`
- `evaluation/repos/`
- old generated reports inside `runs/`
- `skills-lock.json`

The main path through the project is:

```text
riskrank CLI -> run_pipeline.py -> step outputs in runs/ -> generate_report.py
```
