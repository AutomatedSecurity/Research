#!/usr/bin/env python3
"""
Run the thesis prioritization platform on a fixed 5-repo benchmark suite.

This script:
1) clones or updates benchmark repositories
2) runs run_pipeline.py for each repository
3) collects artifacts into a compact evaluation summary
4) writes thesis-friendly markdown/csv/json outputs
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    experiment_root = here.parent
    default_repos_dir = here / "repos"
    default_results_root = here / "results"

    parser = argparse.ArgumentParser(
        description="Run multi-repo benchmark and generate evaluation-ready outputs"
    )
    parser.add_argument(
        "--repos-file",
        default=str(here / "benchmark_repos.json"),
        help="Path to benchmark repository list JSON",
    )
    parser.add_argument(
        "--repos-dir",
        default=str(default_repos_dir),
        help="Directory where benchmark repos are cloned",
    )
    parser.add_argument(
        "--results-root",
        default=str(default_results_root),
        help="Directory where benchmark outputs are written",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=5,
        help="Maximum repositories to run from repos-file",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Top N rows for pipeline reports",
    )
    parser.add_argument(
        "--with-llm",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run LLM + prioritization steps (default: disabled)",
    )
    parser.add_argument(
        "--llm-provider",
        default="openai-compatible",
        choices=["openai-compatible", "anthropic"],
        help="LLM provider to pass to run_pipeline.py",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-5.3-codex",
        help="LLM model to pass to run_pipeline.py",
    )
    parser.add_argument(
        "--llm-auth-file",
        default=None,
        help="Optional auth file for run_pipeline.py --llm-auth-file",
    )
    parser.add_argument(
        "--llm-auth-profile",
        default=None,
        help="Optional auth profile for run_pipeline.py --llm-auth-profile",
    )
    parser.add_argument(
        "--clone-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only clone/update repos, do not run pipelines",
    )
    parser.add_argument(
        "--refresh",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pull latest if repo already exists (default: enabled)",
    )
    parser.add_argument(
        "--fanin-engine",
        default="heuristic",
        choices=["codeql", "heuristic"],
        help="Fan-in engine (default: heuristic for portability)",
    )
    parser.add_argument(
        "--vuln-engine",
        default="heuristic",
        choices=["codeql", "bearer", "heuristic"],
        help="Vulnerability engine (default: heuristic for portability)",
    )
    parser.add_argument(
        "--python-bin",
        default="python3",
        help="Python executable used to run run_pipeline.py",
    )
    parser.add_argument(
        "--experiment-root",
        default=str(experiment_root),
        help="Directory containing run_pipeline.py",
    )
    return parser.parse_args()


def load_repos(repos_file: Path, max_repos: int) -> List[Dict[str, Any]]:
    data = json.loads(repos_file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Invalid repos file (must be JSON array): {repos_file}")
    repos: List[Dict[str, Any]] = []
    for item in data[: max(0, max_repos)]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        slug = str(item.get("slug") or "").strip()
        name = str(item.get("name") or slug or url).strip()
        if not url or not slug:
            continue
        repos.append(
            {
                "name": name,
                "slug": slug,
                "url": url,
                "language": str(item.get("language") or "unknown"),
                "entry_prefixes": [
                    str(x) for x in (item.get("entry_prefixes") or []) if str(x).strip()
                ],
            }
        )
    return repos


def run_checked(cmd: List[str], cwd: Path, log_path: Path) -> int:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"$ {' '.join(cmd)}",
        "",
        "[stdout]",
        proc.stdout or "",
        "",
        "[stderr]",
        proc.stderr or "",
        "",
        f"exit_code={proc.returncode}",
    ]
    log_path.write_text("\n".join(body), encoding="utf-8")
    return int(proc.returncode)


def ensure_repo(local_dir: Path, url: str, refresh: bool, log_dir: Path) -> None:
    if not local_dir.exists():
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        code = run_checked(
            ["git", "clone", "--depth", "1", url, str(local_dir)],
            cwd=local_dir.parent,
            log_path=log_dir / "clone.log",
        )
        if code != 0:
            raise SystemExit(f"Failed to clone {url}. See {log_dir / 'clone.log'}")
        return

    if refresh:
        code = run_checked(
            ["git", "pull", "--ff-only"],
            cwd=local_dir,
            log_path=log_dir / "pull.log",
        )
        if code != 0:
            raise SystemExit(
                f"Failed to update existing repo {local_dir}. See {log_dir / 'pull.log'}"
            )


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def summarize_run(run_dir: Path) -> Dict[str, Any]:
    manifest = read_json(run_dir / "manifest.json")
    vuln_summary = read_json(run_dir / "vulnerabilities" / "summary.json")
    llm_summary = read_json(run_dir / "llm" / "llm_reachability_ranking.json")
    pri_summary = read_json(run_dir / "prioritization" / "summary.json")

    top_priorities = pri_summary.get("top_priorities")
    top_item = top_priorities[0] if isinstance(top_priorities, list) and top_priorities else {}
    top_findings = vuln_summary.get("top_findings")
    top_finding = top_findings[0] if isinstance(top_findings, list) and top_findings else {}
    llm_targets = llm_summary.get("ranked_targets")
    llm_target_count = len(llm_targets) if isinstance(llm_targets, list) else 0

    out = {
        "manifest_present": bool(manifest),
        "findings_count": int(vuln_summary.get("findings_count") or 0),
        "files_scanned": int(vuln_summary.get("files_scanned") or 0),
        "rules_count": int(vuln_summary.get("rules_count") or 0),
        "llm_targets": int(llm_target_count),
        "top_priority_path": str(top_item.get("path") or ""),
        "top_priority_score": float(top_item.get("priority_score") or 0.0),
        "top_priority_tier": str(top_item.get("priority_tier") or ""),
        "top_vuln_path": str(top_finding.get("path") or ""),
        "top_vuln_cvss": float(top_finding.get("cvss_base") or 0.0),
        "rows_total": int(pri_summary.get("rows_total") or 0),
    }
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fields = [
        "repo",
        "slug",
        "language",
        "status",
        "duration_sec",
        "findings_count",
        "files_scanned",
        "rules_count",
        "llm_targets",
        "rows_total",
        "top_priority_tier",
        "top_priority_score",
        "top_priority_path",
        "top_vuln_cvss",
        "top_vuln_path",
        "run_dir",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def format_markdown(
    rows: List[Dict[str, Any]],
    started_at: str,
    with_llm: bool,
    top_n: int,
    fanin_engine: str,
    vuln_engine: str,
) -> str:
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    findings = [int(r.get("findings_count") or 0) for r in ok_rows]
    llm_targets = [int(r.get("llm_targets") or 0) for r in ok_rows]

    mean_findings = statistics.mean(findings) if findings else 0.0
    median_findings = statistics.median(findings) if findings else 0.0
    mean_llm = statistics.mean(llm_targets) if llm_targets else 0.0

    lines: List[str] = []
    lines.append("# Benchmark Evaluation Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("")
    lines.append(f"- Run timestamp (UTC): `{started_at}`")
    lines.append(f"- Repositories attempted: `{len(rows)}`")
    lines.append(f"- Successful runs: `{len(ok_rows)}`")
    lines.append(f"- Fan-in engine: `{fanin_engine}`")
    lines.append(f"- Vulnerability engine: `{vuln_engine}`")
    lines.append(f"- LLM step enabled: `{with_llm}`")
    lines.append(f"- Top-N report size: `{top_n}`")
    lines.append("")
    lines.append("## Per-Repository Results")
    lines.append("")
    lines.append("| Repo | Status | Findings | LLM Targets | Top Priority (Tier/Score) | Best Baseline Vuln (CVSS) |")
    lines.append("|---|---|---:|---:|---|---|")
    for r in rows:
        tier = str(r.get("top_priority_tier") or "")
        score = float(r.get("top_priority_score") or 0.0)
        tier_score = f"{tier} / {score:.2f}" if tier else "-"
        vuln_path = str(r.get("top_vuln_path") or "")
        vuln_cvss = float(r.get("top_vuln_cvss") or 0.0)
        vuln_col = f"`{vuln_path}` ({vuln_cvss:.1f})" if vuln_path else "-"
        lines.append(
            "| "
            + str(r.get("repo") or "")
            + " | "
            + str(r.get("status") or "")
            + " | "
            + str(int(r.get("findings_count") or 0))
            + " | "
            + str(int(r.get("llm_targets") or 0))
            + " | "
            + tier_score
            + " | "
            + vuln_col
            + " |"
        )

    lines.append("")
    lines.append("## Aggregate Snapshot")
    lines.append("")
    lines.append(f"- Mean findings/repo: `{mean_findings:.2f}`")
    lines.append(f"- Median findings/repo: `{median_findings:.2f}`")
    if with_llm:
        lines.append(f"- Mean LLM ranked targets/repo: `{mean_llm:.2f}`")
    lines.append("")
    lines.append("## Thesis-Ready Text (Draft)")
    lines.append("")
    lines.append(
        "We evaluated the prioritization pipeline on five public, security-focused repositories. "
        "For each repository, we executed a consistent pipeline configuration and recorded vulnerability "
        "signal coverage, LLM ranking coverage, and top-priority recommendations. "
        "To reduce repository-size bias, repository-level outcomes should be reported individually and "
        "then aggregated using macro averages in the final evaluation tables."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repos_file = Path(args.repos_file).expanduser().resolve()
    repos_dir = Path(args.repos_dir).expanduser().resolve()
    results_root = Path(args.results_root).expanduser().resolve()
    experiment_root = Path(args.experiment_root).expanduser().resolve()
    pipeline_script = experiment_root / "run_pipeline.py"

    if not repos_file.exists():
        raise SystemExit(f"Repos file not found: {repos_file}")
    if not pipeline_script.exists():
        raise SystemExit(f"run_pipeline.py not found: {pipeline_script}")

    repos = load_repos(repos_file, args.max_repos)
    if not repos:
        raise SystemExit("No valid repositories found in repos file")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suite_dir = results_root / f"suite_{stamp}"
    logs_dir = suite_dir / "logs"
    runs_dir = suite_dir / "runs"
    suite_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    started_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for repo in repos:
        slug = repo["slug"]
        repo_name = repo["name"]
        repo_url = repo["url"]
        repo_lang = repo["language"]
        entry_prefixes = repo["entry_prefixes"]

        local_repo = repos_dir / slug
        repo_log_dir = logs_dir / slug
        repo_log_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n==> Preparing repo: {repo_name} ({repo_url})")
        ensure_repo(local_repo, repo_url, args.refresh, repo_log_dir)

        row: Dict[str, Any] = {
            "repo": repo_name,
            "slug": slug,
            "language": repo_lang,
            "status": "skipped",
            "duration_sec": 0.0,
            "findings_count": 0,
            "files_scanned": 0,
            "rules_count": 0,
            "llm_targets": 0,
            "rows_total": 0,
            "top_priority_tier": "",
            "top_priority_score": 0.0,
            "top_priority_path": "",
            "top_vuln_cvss": 0.0,
            "top_vuln_path": "",
            "run_dir": "",
        }

        if args.clone_only:
            rows.append(row)
            continue

        run_dir = runs_dir / slug
        cmd = [
            args.python_bin,
            str(pipeline_script),
            str(local_repo),
            "--fanin-engine",
            args.fanin_engine,
            "--vuln-engine",
            args.vuln_engine,
            "--top",
            str(args.top),
            "--vuln-top",
            str(args.top),
            "--prioritize-top",
            str(args.top),
            "--output-dir",
            str(run_dir),
        ]
        for ep in entry_prefixes:
            cmd.extend(["--entry-prefix", ep])

        if args.with_llm:
            cmd.extend(["--llm-provider", args.llm_provider, "--llm-model", args.llm_model])
            if args.llm_auth_file:
                cmd.extend(["--llm-auth-file", str(args.llm_auth_file)])
            if args.llm_auth_profile:
                cmd.extend(["--llm-auth-profile", str(args.llm_auth_profile)])
        else:
            cmd.extend(["--skip-llm", "--skip-prioritize"])

        print(f"==> Running pipeline for: {repo_name}")
        started = time.time()
        exit_code = run_checked(cmd, cwd=experiment_root, log_path=repo_log_dir / "pipeline.log")
        elapsed = time.time() - started

        row["duration_sec"] = round(elapsed, 2)
        row["run_dir"] = str(run_dir)

        if exit_code != 0:
            row["status"] = "failed"
            rows.append(row)
            print(f"   failed ({elapsed:.1f}s): see {repo_log_dir / 'pipeline.log'}")
            continue

        summary = summarize_run(run_dir)
        row.update(summary)
        row["status"] = "ok"
        rows.append(row)
        print(f"   done ({elapsed:.1f}s)")

    results_json = suite_dir / "evaluation_results.json"
    results_csv = suite_dir / "evaluation_results.csv"
    results_md = suite_dir / "evaluation_section.md"

    payload = {
        "generated_at": started_iso,
        "suite_dir": str(suite_dir),
        "repos_file": str(repos_file),
        "with_llm": bool(args.with_llm),
        "top": int(args.top),
        "fanin_engine": args.fanin_engine,
        "vuln_engine": args.vuln_engine,
        "rows": rows,
    }
    results_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(results_csv, rows)
    results_md.write_text(
        format_markdown(
            rows=rows,
            started_at=started_iso,
            with_llm=bool(args.with_llm),
            top_n=int(args.top),
            fanin_engine=args.fanin_engine,
            vuln_engine=args.vuln_engine,
        ),
        encoding="utf-8",
    )

    print("\nBenchmark suite complete")
    print(f"Suite directory: {suite_dir}")
    print(f"JSON: {results_json}")
    print(f"CSV: {results_csv}")
    print(f"Markdown: {results_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
