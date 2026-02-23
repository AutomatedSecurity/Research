#!/usr/bin/env python3
"""
Run experiment pipeline steps together.

Current steps:
1) fan-in ranking
2) git history frequency ranking
3) LLM reachability scan
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List


def run_cmd(cmd: List[str]) -> None:
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fan-in + git-history pipeline")
    parser.add_argument(
        "project_path", help="Absolute or relative path to target project"
    )
    parser.add_argument(
        "--entry-prefix",
        action="append",
        default=[],
        help="Entrypoint prefix, can repeat",
    )
    parser.add_argument("--top", type=int, default=25, help="Top rows for reports")
    parser.add_argument(
        "--fanin-engine",
        choices=["codeql", "heuristic"],
        default="codeql",
        help="Fan-in engine (default: codeql)",
    )
    parser.add_argument(
        "--codeql-db-dir",
        default=None,
        help="Optional persistent CodeQL DB dir for step 1",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai-compatible", "anthropic"],
        default="openai-compatible",
        help="Provider for step 3 LLM scan (default: openai-compatible)",
    )
    parser.add_argument(
        "--llm-model",
        default="glm-4.6",
        help="Model for step 3 LLM scan (default: glm-4.6)",
    )
    parser.add_argument(
        "--llm-auth-file",
        default=None,
        help="Optional credentials file created by connect_provider.py",
    )
    parser.add_argument(
        "--llm-auth-profile",
        default=None,
        help="Optional auth profile name from credentials file",
    )
    parser.add_argument(
        "--llm-max-files",
        type=int,
        default=80,
        help="Step 3 max files (<=0 means all)",
    )
    parser.add_argument(
        "--llm-max-chars",
        type=int,
        default=5000,
        help="Step 3 max chars per file (<=0 means full file)",
    )
    parser.add_argument(
        "--llm-max-tree",
        type=int,
        default=250,
        help="Step 3 max tree entries (<=0 means all)",
    )
    parser.add_argument(
        "--llm-use-tools",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable LLM tool calls in step 3 (default: enabled)",
    )
    parser.add_argument(
        "--llm-max-tool-steps",
        type=int,
        default=18,
        help="Max LLM tool-call iterations for step 3",
    )
    parser.add_argument(
        "--include-signals",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include fan-in/git summaries in step 3 payload (default: enabled)",
    )
    parser.add_argument(
        "--skip-llm",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip step 3 LLM scan",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output run dir. Default: Research/experiment/runs/<project>_<timestamp>",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = Path(args.project_path).expanduser().resolve()
    if not project.exists() or not project.is_dir():
        raise SystemExit(
            f"Project path does not exist or is not a directory: {project}"
        )

    here = Path(__file__).resolve().parent
    if args.output_dir:
        run_dir = Path(args.output_dir).expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = here / "runs" / f"{project.name}_{stamp}"

    fanin_dir = run_dir / "fanin"
    git_dir = run_dir / "git_history"
    llm_dir = run_dir / "llm"
    run_dir.mkdir(parents=True, exist_ok=True)

    fanin_cmd = [
        sys.executable,
        str(here / "fanin_rank.py"),
        str(project),
        "--engine",
        str(args.fanin_engine),
        "--top",
        str(args.top),
        "--output-dir",
        str(fanin_dir),
    ]
    if args.codeql_db_dir:
        fanin_cmd.extend(
            ["--codeql-db-dir", str(Path(args.codeql_db_dir).expanduser().resolve())]
        )
    for prefix in args.entry_prefix:
        fanin_cmd.extend(["--entry-prefix", prefix])

    git_cmd = [
        sys.executable,
        str(here / "git_history_rank.py"),
        str(project),
        "--top",
        str(args.top),
        "--output-dir",
        str(git_dir),
    ]

    llm_cmd = [
        sys.executable,
        str(here / "llm_reachability_scan.py"),
        str(project),
        "--provider",
        str(args.llm_provider),
        "--model",
        str(args.llm_model),
        "--run-dir",
        str(run_dir),
        "--max-files",
        str(args.llm_max_files),
        "--max-chars",
        str(args.llm_max_chars),
        "--max-tree",
        str(args.llm_max_tree),
        "--max-tool-steps",
        str(args.llm_max_tool_steps),
        "--output-dir",
        str(llm_dir),
    ]
    if args.llm_auth_file:
        llm_cmd.extend(
            ["--auth-file", str(Path(args.llm_auth_file).expanduser().resolve())]
        )
    if args.llm_auth_profile:
        llm_cmd.extend(["--auth-profile", str(args.llm_auth_profile)])
    if args.llm_use_tools:
        llm_cmd.append("--use-tools")
    else:
        llm_cmd.append("--no-use-tools")

    if args.include_signals:
        llm_cmd.append("--include-signals")
    else:
        llm_cmd.append("--no-include-signals")

    print("Running Step 1: fan-in ranking")
    run_cmd(fanin_cmd)

    print("\nRunning Step 2: git history ranking")
    run_cmd(git_cmd)

    if not args.skip_llm:
        print("\nRunning Step 3: LLM reachability scan")
        run_cmd(llm_cmd)

    manifest = {
        "project": str(project),
        "run_dir": str(run_dir),
        "steps": {
            "fanin": {
                "engine": args.fanin_engine,
                "summary_json": str(fanin_dir / "summary.json"),
                "csv": str(fanin_dir / "fanin_ranking.csv"),
                "report_md": str(fanin_dir / "report.md"),
            },
            "git_history": {
                "summary_json": str(git_dir / "summary.json"),
                "csv": str(git_dir / "git_history_frequency.csv"),
                "report_md": str(git_dir / "report.md"),
            },
        },
    }
    if not args.skip_llm:
        manifest["steps"]["llm"] = {
            "ranking_json": str(llm_dir / "llm_reachability_ranking.json"),
            "raw_response": str(llm_dir / "raw_response.txt"),
            "request_context": str(llm_dir / "request_context.json"),
            "model": args.llm_model,
        }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("\nPipeline complete")
    print(f"Run directory: {run_dir}")
    print(f"Manifest: {run_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
