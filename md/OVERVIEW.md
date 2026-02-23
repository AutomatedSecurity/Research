# Project Overview (Simple)

This file is a quick guide for anyone new to the project.

## What problem are we solving?

Security tools in CI/CD often produce too many alerts.

- Many alerts are duplicates
- Severity labels differ between tools
- Teams do not know what to fix first

We want a better way to prioritize findings so developers can focus on the most important issues first.

## Main idea

We do **not** run the code to estimate importance.

Instead, we combine 3 signals:

1. **Fan-in reachability** (from entry points)
   - Which code areas are reached from more routes/endpoints
2. **Git history activity**
   - Which files change often (commit frequency + churn)
3. **LLM semantic ranking**
   - Which code areas look most business-critical from context

Then an LLM orchestration layer can merge these signals with scanner findings into a final prioritized report.

## Current thesis focus

Current focus is:

- LLM-based aggregation, analysis, and prioritization of multi-tool findings in CI/CD

We are **not** currently focusing on full head-to-head benchmarking of LLM vulnerability detection vs static tools.

## What has been built so far?

A working prototype pipeline in `Research/experiment`:

- Step 1: `fanin_rank.py` (CodeQL-backed by default)
- Step 2: `git_history_rank.py`
- Step 3: `llm_reachability_scan.py`
- Orchestration runner: `run_pipeline.py`
- Make targets: `Makefile`

## Where outputs go

Each run creates a folder under `Research/experiment/runs/<run_name>/`:

- `fanin/` → fan-in ranking files
- `git_history/` → git ranking files
- `llm/` → LLM ranking files
- `manifest.json` → pointers to all outputs

## Typical command

From `Research/experiment`:

```bash
make test PROJECT_PATH=/path/to/project FANIN_ENGINE=codeql ENTRY_PREFIX=server/api TOP=20
```

## Key files to read first

1. `Research/md/OVERVIEW.md` (this file)
2. `Research/md/README.md` (research scope and RQ)
3. `Research/md/abstract.md` (current abstract draft)
4. `Research/md/2026-02-15.md` (latest checkpoint)
5. `Research/experiment/README.md` (implementation and run details)
