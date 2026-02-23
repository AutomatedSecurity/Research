#!/usr/bin/env python3
"""
Git history frequency ranking (file-level) for prioritization.

For each source file, compute:
- commits_touched: number of distinct commits that modified file
- total_added / total_deleted
- churn: added + deleted
- last_commit_unix

This is a lightweight proxy for maintenance and change frequency.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set


SOURCE_EXTS = {".ts", ".js", ".tsx", ".jsx", ".py"}
SKIP_DIRS = {
    "node_modules",
    ".git",
    ".nuxt",
    ".output",
    "dist",
    "build",
    "coverage",
    "venv",
    ".venv",
    "__pycache__",
}


@dataclass
class FileStats:
    commits: Set[str] = field(default_factory=set)
    total_added: int = 0
    total_deleted: int = 0
    last_commit_unix: int = 0

    @property
    def commits_touched(self) -> int:
        return len(self.commits)

    @property
    def churn(self) -> int:
        return self.total_added + self.total_deleted


def should_include(rel_path: str) -> bool:
    p = Path(rel_path)
    if p.suffix not in SOURCE_EXTS:
        return False
    if any(part in SKIP_DIRS for part in p.parts):
        return False
    return True


def ensure_git_repo(root: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        raise SystemExit(f"Not a git repository: {root}")


def collect_history(root: Path) -> Dict[str, FileStats]:
    cmd = [
        "git",
        "-C",
        str(root),
        "log",
        "--pretty=format:__COMMIT__%H|%ct",
        "--numstat",
        "--no-renames",
        "--",
        ".",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "Failed to read git history")

    stats: Dict[str, FileStats] = defaultdict(FileStats)

    current_hash = ""
    current_ts = 0

    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip("\n")
        if not line:
            continue

        if line.startswith("__COMMIT__"):
            payload = line[len("__COMMIT__") :]
            parts = payload.split("|", 1)
            if len(parts) != 2:
                current_hash = ""
                current_ts = 0
                continue
            current_hash = parts[0]
            try:
                current_ts = int(parts[1])
            except ValueError:
                current_ts = 0
            continue

        cols = line.split("\t")
        if len(cols) < 3:
            continue

        add_s, del_s, path_s = cols[0], cols[1], cols[2]
        if not current_hash or not should_include(path_s):
            continue

        try:
            added = int(add_s) if add_s.isdigit() else 0
            deleted = int(del_s) if del_s.isdigit() else 0
        except ValueError:
            added, deleted = 0, 0

        fs = stats[path_s]
        fs.commits.add(current_hash)
        fs.total_added += added
        fs.total_deleted += deleted
        if current_ts > fs.last_commit_unix:
            fs.last_commit_unix = current_ts

    return stats


def write_outputs(
    root: Path, stats: Dict[str, FileStats], out_dir: Path, top_n: int
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(
        stats.items(),
        key=lambda kv: (-kv[1].commits_touched, -kv[1].churn, kv[0]),
    )

    csv_path = out_dir / "git_history_frequency.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "rank",
                "file",
                "commits_touched",
                "total_added",
                "total_deleted",
                "churn",
                "last_commit_unix",
            ]
        )
        for i, (path_s, fs) in enumerate(ranked, start=1):
            w.writerow(
                [
                    i,
                    path_s,
                    fs.commits_touched,
                    fs.total_added,
                    fs.total_deleted,
                    fs.churn,
                    fs.last_commit_unix,
                ]
            )

    summary = {
        "project_root": str(root),
        "files_ranked": len(ranked),
        "top_n": top_n,
        "top_files": [
            {
                "rank": i,
                "file": path_s,
                "commits_touched": fs.commits_touched,
                "total_added": fs.total_added,
                "total_deleted": fs.total_deleted,
                "churn": fs.churn,
                "last_commit_unix": fs.last_commit_unix,
            }
            for i, (path_s, fs) in enumerate(ranked[:top_n], start=1)
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    md_lines: List[str] = [
        "# Git History Frequency Ranking",
        "",
        f"- Project: `{root}`",
        f"- Files ranked: `{len(ranked)}`",
        "",
        "## Top Files",
        "",
        "| Rank | File | Commits Touched | Churn |",
        "|---:|---|---:|---:|",
    ]
    for i, (path_s, fs) in enumerate(ranked[:top_n], start=1):
        md_lines.append(f"| {i} | `{path_s}` | {fs.commits_touched} | {fs.churn} |")
    md_lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Frequency is based on git commit touch count per file.",
            "- Churn is total lines added + deleted over history.",
            "- This is file-level, used as a maintenance/change proxy signal.",
        ]
    )
    (out_dir / "report.md").write_text("\n".join(md_lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute git history frequency ranking for a project"
    )
    parser.add_argument("project_path", help="Absolute or relative project path")
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="How many top rows to include in summary/report",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Default: Research/experiment/git_history_outputs/<project>_<timestamp>",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.project_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Project path does not exist or is not a directory: {root}")

    ensure_git_repo(root)
    stats = collect_history(root)

    script_dir = Path(__file__).resolve().parent
    if args.output_dir:
        out_dir = Path(args.output_dir).expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = script_dir / "git_history_outputs" / f"{root.name}_{stamp}"

    write_outputs(root, stats, out_dir, top_n=args.top)

    ranked = sorted(
        stats.items(), key=lambda kv: (-kv[1].commits_touched, -kv[1].churn, kv[0])
    )
    print(f"Project: {root}")
    print(f"Files ranked: {len(ranked)}")
    print(f"Output directory: {out_dir}")
    print("")
    print(f"Top {min(args.top, len(ranked))} files by commit touch frequency:")
    for i, (path_s, fs) in enumerate(ranked[: args.top], start=1):
        print(f"{i:>2}. {path_s} (commits={fs.commits_touched}, churn={fs.churn})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
