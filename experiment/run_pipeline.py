#!/usr/bin/env python3
"""
Run experiment pipeline steps together.

Current steps:
1) fan-in ranking
2) git history frequency ranking
3) vulnerability signal scan
4) LLM reachability scan
5) human prioritization table
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List


SOURCE_EXTS = {".ts", ".js", ".tsx", ".jsx", ".py", ".php", ".phtml", ".vue"}

PR_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)(?:/.*)?$"
)


def run_cmd(cmd: List[str]) -> None:
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def fetch_pr_files(pr_url: str) -> List[str]:
    m = PR_URL_RE.match(pr_url.strip())
    if not m:
        raise SystemExit(
            "Invalid --pr-url. Expected format: https://github.com/<owner>/<repo>/pull/<number>"
        )

    endpoint = f"repos/{m.group('owner')}/{m.group('repo')}/pulls/{m.group('number')}/files"
    cmd = ["gh", "api", "--paginate", endpoint, "--jq", ".[].filename"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise SystemExit("GitHub CLI (gh) is not installed. Install gh to use --pr-url.") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise SystemExit(
            "Failed to fetch PR files via gh api. "
            f"Ensure 'gh auth login' is configured. Details: {stderr or 'unknown error'}"
        )

    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def normalize_pr_source_paths(project: Path, pr_files: List[str]) -> List[str]:
    project_dir_name = project.name
    out: set[str] = set()
    for raw in pr_files:
        raw_norm = raw.replace("\\", "/").lstrip("./")
        if Path(raw_norm).suffix.lower() not in SOURCE_EXTS:
            continue
        if "/" in raw_norm:
            prefix, rest = raw_norm.split("/", 1)
            if prefix == project_dir_name:
                out.add(rest)
                continue
        out.add(raw_norm)
    return sorted(out)


def filter_candidate_paths_by_prefix(
    candidate_paths: List[str], include_prefixes: List[str]
) -> List[str]:
    cleaned = [
        p.strip().strip("/") for p in include_prefixes if p and p.strip().strip("/")
    ]
    if not cleaned:
        return candidate_paths
    allowed = tuple(f"{p}/" for p in cleaned)
    return [p for p in candidate_paths if p in cleaned or p.startswith(allowed)]


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
        "--vuln-top",
        type=int,
        default=25,
        help="Top vulnerability findings in report",
    )
    parser.add_argument(
        "--vuln-max-findings",
        type=int,
        default=300,
        help="Max vulnerability findings retained",
    )
    parser.add_argument(
        "--vuln-engine",
        choices=["codeql", "bearer", "heuristic"],
        default="codeql",
        help="Vulnerability engine for step 3 (default: codeql, with fallback to bearer)",
    )
    parser.add_argument(
        "--skip-vuln",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip step 3 vulnerability scan",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai-compatible", "anthropic"],
        default="openai-compatible",
        help="Provider for step 4 LLM scan (default: openai-compatible)",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-5.3-codex",
        help="Model for step 4 LLM scan (default: gpt-5.3-codex)",
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
        help="Step 4 max files (<=0 means all)",
    )
    parser.add_argument(
        "--llm-max-chars",
        type=int,
        default=5000,
        help="Step 4 max chars per file (<=0 means full file)",
    )
    parser.add_argument(
        "--llm-max-tree",
        type=int,
        default=250,
        help="Step 4 max tree entries (<=0 means all)",
    )
    parser.add_argument(
        "--llm-use-tools",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable LLM tool calls in step 4 (default: enabled)",
    )
    parser.add_argument(
        "--llm-max-tool-steps",
        type=int,
        default=18,
        help="Max LLM tool-call iterations for step 4",
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=0.0,
        help="Step 4 LLM temperature (default: 0.0 for stable outputs)",
    )
    parser.add_argument(
        "--llm-top-p",
        type=float,
        default=1.0,
        help="Step 4 LLM top-p (default: 1.0)",
    )
    parser.add_argument(
        "--include-signals",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include fan-in/git/vulnerability summaries in step 4 payload (default: enabled)",
    )
    parser.add_argument(
        "--skip-llm",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip step 4 LLM scan",
    )
    parser.add_argument(
        "--prioritize-top",
        type=int,
        default=25,
        help="Top prioritized rows in step 5 output",
    )
    parser.add_argument(
        "--skip-prioritize",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip step 5 human prioritization table",
    )
    parser.add_argument(
        "--pr-url",
        default=None,
        help="GitHub PR URL — scopes LLM ranking to PR-changed files",
    )
    parser.add_argument(
        "--pr-context-files",
        type=int,
        default=30,
        help="Non-PR context files when --pr-url is set (default: 30)",
    )
    parser.add_argument(
        "--pr-include-prefix",
        action="append",
        default=[],
        help="Optional project-relative path prefix to keep when --pr-url is set. Can repeat.",
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
    vuln_dir = run_dir / "vulnerabilities"
    llm_dir = run_dir / "llm"
    prioritization_dir = run_dir / "prioritization"
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate_files_path = None
    if args.pr_url:
        pr_files = fetch_pr_files(str(args.pr_url))
        candidate_paths = normalize_pr_source_paths(project, pr_files)
        candidate_paths = filter_candidate_paths_by_prefix(
            candidate_paths, args.pr_include_prefix
        )
        if not candidate_paths:
            raise SystemExit(
                "PR does not contain source files under the selected project path."
            )
        candidate_files_path = run_dir / "pr_candidate_files.txt"
        candidate_files_path.write_text("\n".join(candidate_paths) + "\n", encoding="utf-8")
        print(f"[info] PR source candidates: {len(candidate_paths)}")

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
    if candidate_files_path:
        fanin_cmd.extend(["--candidate-files", str(candidate_files_path)])

    git_cmd = [
        sys.executable,
        str(here / "git_history_rank.py"),
        str(project),
        "--top",
        str(args.top),
        "--output-dir",
        str(git_dir),
    ]
    if candidate_files_path:
        git_cmd.extend(["--candidate-files", str(candidate_files_path)])

    vuln_cmd = [
        sys.executable,
        str(here / "vulnerability_scan.py"),
        str(project),
        "--engine",
        str(args.vuln_engine),
        "--top",
        str(args.vuln_top),
        "--max-findings",
        str(args.vuln_max_findings),
        "--output-dir",
        str(vuln_dir),
    ]
    if candidate_files_path:
        vuln_cmd.extend(["--candidate-files", str(candidate_files_path)])

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
        "--temperature",
        str(args.llm_temperature),
        "--top-p",
        str(args.llm_top_p),
        "--max-tool-steps",
        str(args.llm_max_tool_steps),
        "--output-dir",
        str(llm_dir),
    ]

    prioritize_cmd = [
        sys.executable,
        str(here / "prioritize_targets.py"),
        "--run-dir",
        str(run_dir),
        "--top",
        str(args.prioritize_top),
        "--output-dir",
        str(prioritization_dir),
    ]
    if candidate_files_path:
        prioritize_cmd.extend(["--candidate-files", str(candidate_files_path)])
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

    if args.pr_url:
        llm_cmd.extend(["--pr-url", str(args.pr_url)])
        llm_cmd.extend(["--pr-context-files", str(args.pr_context_files)])
    if candidate_files_path:
        llm_cmd.extend(["--candidate-files", str(candidate_files_path)])

    print("Running Step 1: fan-in ranking")
    run_cmd(fanin_cmd)

    print("\nRunning Step 2: git history ranking")
    run_cmd(git_cmd)

    if not args.skip_vuln:
        print("\nRunning Step 3: vulnerability signal scan")
        run_cmd(vuln_cmd)

    if not args.skip_llm:
        print("\nRunning Step 4: LLM reachability scan")
        run_cmd(llm_cmd)

    if not args.skip_prioritize:
        if args.skip_llm or args.skip_vuln:
            print(
                "\nSkipping Step 5: human prioritization table "
                "(requires both vulnerability and LLM steps)."
            )
        else:
            print("\nRunning Step 5: human prioritization table")
            run_cmd(prioritize_cmd)

    manifest = {
        "project": str(project),
        "run_dir": str(run_dir),
        "pr_url": args.pr_url,
        "candidate_files": str(candidate_files_path) if candidate_files_path else None,
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
    if not args.skip_vuln:
        manifest["steps"]["vulnerabilities"] = {
            "summary_json": str(vuln_dir / "summary.json"),
            "csv": str(vuln_dir / "findings.csv"),
            "report_md": str(vuln_dir / "report.md"),
        }
    if not args.skip_llm:
        manifest["steps"]["llm"] = {
            "ranking_json": str(llm_dir / "llm_reachability_ranking.json"),
            "raw_response": str(llm_dir / "raw_response.txt"),
            "request_context": str(llm_dir / "request_context.json"),
            "model": args.llm_model,
        }
    if not args.skip_prioritize and not args.skip_llm and not args.skip_vuln:
        manifest["steps"]["prioritization"] = {
            "summary_json": str(prioritization_dir / "summary.json"),
            "csv": str(prioritization_dir / "priorities.csv"),
            "report_md": str(prioritization_dir / "report.md"),
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
