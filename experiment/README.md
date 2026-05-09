# RiskRank

Risk-based code prioritization for security review.

RiskRank combines:

1. Fan-in ranking
2. Git history frequency ranking
3. Vulnerability signal scanning
4. LLM-based reachability analysis
5. Final prioritization

## Start Here

Install locally:

```bash
pip install -e .
```

Main CLI:

```bash
riskrank --help
```

Run the full pipeline:

```bash
riskrank run /path/to/project --entry-prefix server/api --top 25
```

Generate an HTML report for a run:

```bash
riskrank report /path/to/runs/<run_id>
```

## Repo Layout

```text
.
├── README.md                  # Main entrypoint and quickstart
├── pyproject.toml             # Package metadata and CLI entrypoint
├── riskrank_cli/              # Installed CLI package
├── run_pipeline.py            # Orchestrates the end-to-end workflow
├── fanin_rank.py              # Step 1: structural fan-in analysis
├── git_history_rank.py        # Step 2: git activity analysis
├── vulnerability_scan.py      # Step 3: vulnerability baseline
├── llm_reachability_scan.py   # Step 4: LLM reachability ranking
├── prioritize_targets.py      # Step 5: final score fusion
├── generate_report.py         # HTML report generator
├── connect_provider.py        # Saved auth profiles for LLM providers
├── evaluation/                # Multi-repo benchmark and metrics tooling
├── examples/                  # Example vulnerable apps / fixtures
├── runs/                      # Saved pipeline outputs and reports
├── frontend/                  # Optional Nuxt frontend
├── docs/                      # Architecture notes and diagrams
└── bin/                       # External helper binaries like bearer
```

More detail: `docs/REPO_STRUCTURE.md`

## Command Map

- `riskrank run` - full pipeline
- `riskrank fanin` - fan-in ranking only
- `riskrank git-history` - git history ranking only
- `riskrank vuln-scan` - vulnerability scan only
- `riskrank llm-scan` - LLM reachability scan only
- `riskrank prioritize` - combine LLM and vulnerability signals
- `riskrank report` - generate an HTML report from a run directory
- `riskrank connect` - manage saved provider credentials
- `riskrank benchmark` - run the benchmark suite
- `riskrank metrics` - compute metrics for a benchmark suite

Pass `--help` after any subcommand to inspect its flags.

## Important Folders

`riskrank_cli/`
- The packaged CLI layer.
- This is what exposes the `riskrank` command.

Top-level Python modules
- These are the actual pipeline stages.
- They are kept at the top level right now because the CLI dispatches directly into them.

`runs/`
- Generated per-project outputs.
- Each run typically contains `fanin/`, `git_history/`, `vulnerabilities/`, `llm/`, `prioritization/`, and `report.html`.

`evaluation/`
- Batch experiments across multiple repositories.
- Use this for benchmark suites and metrics, not normal single-project usage.

`examples/`
- Example targets you can use for demos or testing.

`frontend/`
- Optional UI work.
- Not required for the Python CLI.

## External Tools

Some modes depend on external tools:

- `git` for git-history analysis
- `gh` for PR-scoped LLM analysis
- `codeql` for CodeQL-backed fan-in and vulnerability scanning
- `bearer` for the bearer fallback engine

The CLI still works without all of them installed, but some modes fall back or become unavailable.

## Notes

- `skills-lock.json` is local agent-skill metadata, not part of the core pipeline.
- `docs/assets/` contains supporting diagrams for architecture discussions.
- `Makefile` is a legacy convenience wrapper; the supported interface is the `riskrank` CLI.
