# Experiment Pipeline (PoC)

This folder contains a simple pipeline for the thesis prioritization prototype:

1. Fan-in ranking (static reachability proxy)
2. Git history frequency table
3. Vulnerability signal scan (static regex heuristics)
4. LLM-based semantic analysis
5. Human prioritization table (vuln + LLM reachability)
6. LLM orchestrator final prioritization report (later)

## Run Full Pipeline (Step 1 + 2 + 3 + 4 + 5)

Script: `run_pipeline.py`

```bash
python3 run_pipeline.py /path/to/project --entry-prefix server/api --top 25
```

For Inkuis:

```bash
python3 run_pipeline.py /Users/matar/WORK/inkuis --entry-prefix server/api --top 20
```

Or using Make:

```bash
make test PROJECT_PATH=/Users/matar/WORK/inkuis ENTRY_PREFIX=server/api TOP=20
```

Connect a provider profile first (interactive):

```bash
make connect
```

This creates a single run folder under `runs/` with:

- `fanin/` outputs
- `git_history/` outputs
- `vulnerabilities/` outputs
- `llm/` outputs
- `prioritization/` outputs
- `manifest.json` pointing to all generated artifacts

## Step 5: Human prioritization table

Script: `prioritize_targets.py`

```bash
python3 prioritize_targets.py --run-dir /path/to/runs/<run_id>
```

This step builds a ranked table that combines:

- Vulnerability severity (CVSS-estimated from scanner findings)
- LLM reachability score

Outputs:

- `prioritization/report.md`
- `prioritization/priorities.csv`
- `prioritization/summary.json`

## Step 3: Vulnerability signal scan

Script: `vulnerability_scan.py`

```bash
python3 vulnerability_scan.py /path/to/project
```

Notes:

- Default engine is `codeql`; when CodeQL is unavailable for the project language, it falls back to `bearer`.
- You can force Bearer with `--engine bearer`.
- Outputs: `findings.csv`, `summary.json`, `report.md`, `baseline_ranking.json`.

## Step 3 (manual): LLM reachability scan

Script: `llm_reachability_scan.py`

```bash
python3 llm_reachability_scan.py /path/to/project
```

Optional provider flag (currently implemented engine path is `openai-compatible`):

```bash
python3 llm_reachability_scan.py /path/to/project --provider openai-compatible --model gpt-5.3-codex
```

Rank only files changed in a GitHub PR while still giving the LLM broader project context:

```bash
python3 llm_reachability_scan.py /path/to/project --pr-url https://github.com/<owner>/<repo>/pull/<number>
```

Optional PR controls:

- `--max-files`: limit PR candidate files considered for ranking.
- `--pr-context-files`: include additional non-PR files as context only (default: 30).

Notes for PR mode:

- Requires `gh` CLI and an authenticated session (`gh auth login`).
- Final ranking output is restricted to PR files only.
- The LLM still receives broader codebase context (selected context files + optional signals).

### Connect-style credential profiles

Script: `connect_provider.py`

```bash
python3 connect_provider.py login
python3 connect_provider.py list
```

Use a saved profile in the scan:

```bash
python3 llm_reachability_scan.py /path/to/project --auth-profile openai-default
```

Notes:

- Profiles are stored in `credentials.json` by default.
- This is API-key based (stable for automation).
- Browser OAuth with consumer subscription sessions is intentionally not implemented.

Include fan-in + git-history context from a pipeline run:

```bash
python3 llm_reachability_scan.py /path/to/project --run-dir /path/to/runs/<run_id>
```

To send maximum context (all files + full contents + full selected tree):

```bash
python3 llm_reachability_scan.py /path/to/project --max-files 0 --max-chars 0 --max-tree 0
```

Disable tool calls if needed:

```bash
python3 llm_reachability_scan.py /path/to/project --no-use-tools
```

Notes:

- The script auto-loads `Research/experiment/.env` by default.
- Set `OPENAI_API_KEY` in `.env`.
- Default model is `gpt-5.3-codex`.
- Default base URL is `https://api.openai.com/v1`.
- Default output path is `runs/<project>/llm`.
- Fan-in, git-history, and vulnerability signals are injected when `--run-dir` is provided (or direct summary paths are passed).
- Context selection is prioritized for API/middleware/model/service/auth files.
- Tool-calls are enabled by default (`list_files`, `read_file`, `search_code`).
- For more repeatable outputs across runs, use `--temperature 0 --top-p 1`.

To disable fan-in/git context injection:

```bash
python3 llm_reachability_scan.py /path/to/project --no-include-signals
```

## Step 1: Fan-in ranking

Script: `fanin_rank.py`

Default engine is `codeql`.

### Run

```bash
python3 fanin_rank.py /path/to/project --entry-prefix server/api --top 25
```

For Inkuis:

```bash
python3 fanin_rank.py /Users/matar/WORK/inkuis --entry-prefix server/api --top 20
```

Use heuristic fallback if CodeQL is unavailable:

```bash
python3 fanin_rank.py /path/to/project --engine heuristic --entry-prefix server/api --top 25
```

### Output

Creates a timestamped folder under `fanin_outputs/`:

- `report.md` - quick top-table summary
- `summary.json` - structured output for later orchestration
- `fanin_ranking.csv` - full ranking table

## Step 2: Git history frequency ranking

Script: `git_history_rank.py`

### Run

```bash
python3 git_history_rank.py /path/to/project --top 25
```

For Inkuis:

```bash
python3 git_history_rank.py /Users/matar/WORK/inkuis --top 20
```

### Output

Creates a timestamped folder under `git_history_outputs/`:

- `report.md` - quick top-table summary
- `summary.json` - structured output for later orchestration
- `git_history_frequency.csv` - full file ranking

### Notes

- Frequency = number of distinct commits that touched each file.
- Churn = lines added + deleted over git history.
- This is a maintenance/change-frequency proxy signal.

### Notes

- This PoC uses a file-level import graph.
- Fan-in = number of distinct entrypoint files that can reach a module through import edges.
- `codeql` engine uses CodeQL import resolution from a CodeQL database.
- `heuristic` engine is a regex-parser fallback.
- Source scanning supports JS/TS, Python, and PHP (`.php`, `.phtml`).
- If `codeql` is requested for a non-JS/TS project, fan-in auto-falls back to `heuristic`.
