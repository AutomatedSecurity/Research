# Benchmark Evaluation Runner

This folder contains a reproducible benchmark suite for the thesis evaluation section.

## Benchmark Repositories

The suite definition lives in `benchmark_repos.json` and currently includes 5 public, security-focused repos:

1. NodeGoat
2. DVNA
3. DVWA
4. XVWA
5. Juice Shop

## Run

From `Research/experiment`:

```bash
python3 evaluation/run_benchmark_suite.py --max-repos 5 --top 10
```

This runs fan-in + git-history + vulnerability scanning on each repo (LLM disabled by default).

To include the LLM ranking + prioritization step:

```bash
python3 evaluation/run_benchmark_suite.py --max-repos 5 --with-llm --llm-auth-profile openai-default
```

## Output

Each suite run creates:

- `evaluation/results/suite_<timestamp>/evaluation_results.json`
- `evaluation/results/suite_<timestamp>/evaluation_results.csv`
- `evaluation/results/suite_<timestamp>/evaluation_section.md`
- `evaluation/results/suite_<timestamp>/runs/<repo>/...` (raw pipeline artifacts)

Use `evaluation_section.md` directly as a draft block for your thesis evaluation section.

## Compute Metrics

After a suite run completes, compute macro/per-repo metrics from generated `priorities.csv` files:

```bash
python3 evaluation/compute_metrics.py \
  --suite-dir evaluation/results/suite_<timestamp> \
  --k-values 5,10,20 \
  --label-mode cvss9
```

Outputs in the same suite folder:

- `metrics_per_repo.csv`
- `metrics_macro.csv`
- `metrics_summary.md`
- `metrics.json`

For manual labels, use:

```bash
python3 evaluation/compute_metrics.py \
  --suite-dir evaluation/results/suite_<timestamp> \
  --label-mode labels-file \
  --labels-file /path/to/labels.csv
```

Expected labels CSV columns: `repo,path,label` (label is `0` or `1`).
