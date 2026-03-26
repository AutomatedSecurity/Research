#!/usr/bin/env python3
"""
LLM-based reachability ranking (OpenAI-compatible API).

This script prepares project context, loads PROMPT.md instructions,
and requests a structured JSON ranking.

It is designed to generate artifacts for later orchestration.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: openai. Install with: pip install --upgrade 'openai>=1.0'"
    ) from exc


SOURCE_EXTS = {".ts", ".js", ".tsx", ".jsx", ".py", ".vue", ".php", ".phtml"}
DEFAULT_MODEL = "gpt-5.3-codex"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_FALLBACK_CHAT_MODEL = "gpt-4.1-mini"
DEFAULT_AUTH_FILE = Path(__file__).resolve().parent / "credentials.json"

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".nuxt",
    ".output",
    "dist",
    "build",
    "coverage",
    "venv",
    ".venv",
    "__pycache__",
}

HIGH_SIGNAL_PREFIXES = [
    "server/api/",
    "server/middleware/",
    "server/routes/",
    "server/models/",
    "server/services/",
    "server/validation/",
    "server/utils/",
    "pages/",
    "stores/",
    "utils/",
    "api/",
    "routes/",
    "app/",
    "src/",
    "website/",
    "public/",
    "web/",
]

PR_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)(?:/.*)?$"
)


def _safe_resolve(project_root: Path, rel_or_abs: str) -> Optional[Path]:
    p = Path(rel_or_abs)
    resolved = p.resolve() if p.is_absolute() else (project_root / p).resolve()
    if resolved == project_root or project_root in resolved.parents:
        return resolved
    return None


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def collect_source_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in SOURCE_EXTS and not _should_skip(p):
            files.append(p)
    return files


def parse_github_pr_url(pr_url: str) -> Optional[dict[str, str]]:
    m = PR_URL_RE.match(pr_url.strip())
    if not m:
        return None
    return {
        "owner": m.group("owner"),
        "repo": m.group("repo"),
        "number": m.group("number"),
    }


def fetch_pr_files(pr_url: str) -> List[str]:
    parts = parse_github_pr_url(pr_url)
    if not parts:
        raise SystemExit(
            "Invalid --pr-url. Expected format: https://github.com/<owner>/<repo>/pull/<number>"
        )

    endpoint = f"repos/{parts['owner']}/{parts['repo']}/pulls/{parts['number']}/files"
    cmd = ["gh", "api", "--paginate", endpoint, "--jq", ".[].filename"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise SystemExit(
            "GitHub CLI (gh) is not installed. Install gh to use --pr-url."
        ) from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise SystemExit(
            "Failed to fetch PR files via gh api. "
            f"Ensure 'gh auth login' is configured. Details: {stderr or 'unknown error'}"
        )

    files = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return sorted(set(files))


def prepare_temp_clone_for_pr(
    pr_url: str,
) -> Tuple[Path, tempfile.TemporaryDirectory[str]]:
    parts = parse_github_pr_url(pr_url)
    if not parts:
        raise SystemExit(
            "Invalid --pr-url. Expected format: https://github.com/<owner>/<repo>/pull/<number>"
        )

    tmp = tempfile.TemporaryDirectory(prefix="pr_scan_")
    clone_root = Path(tmp.name) / parts["repo"]
    repo_slug = f"{parts['owner']}/{parts['repo']}"

    clone_cmd = ["gh", "repo", "clone", repo_slug, str(clone_root)]
    try:
        clone_proc = subprocess.run(
            clone_cmd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        tmp.cleanup()
        raise SystemExit(
            "GitHub CLI (gh) is not installed. Install gh to use --pr-url without project_path."
        ) from exc

    if clone_proc.returncode != 0:
        tmp.cleanup()
        stderr = (clone_proc.stderr or "").strip()
        raise SystemExit(
            "Failed to clone repository via gh. "
            f"Ensure 'gh auth login' is configured. Details: {stderr or 'unknown error'}"
        )

    fetch_pr_ref_cmd = [
        "git",
        "fetch",
        "origin",
        f"pull/{parts['number']}/head:pr-{parts['number']}",
    ]
    fetch_proc = subprocess.run(
        fetch_pr_ref_cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(clone_root),
    )
    if fetch_proc.returncode != 0:
        tmp.cleanup()
        stderr = (fetch_proc.stderr or "").strip()
        raise SystemExit(
            "Failed to fetch PR head ref from origin. "
            f"Details: {stderr or 'unknown error'}"
        )

    checkout_cmd = ["git", "checkout", f"pr-{parts['number']}"]
    checkout_proc = subprocess.run(
        checkout_cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(clone_root),
    )
    if checkout_proc.returncode != 0:
        tmp.cleanup()
        stderr = (checkout_proc.stderr or "").strip()
        raise SystemExit(
            "Failed to checkout PR head branch in temporary clone. "
            f"Details: {stderr or 'unknown error'}"
        )

    return clone_root, tmp


def _file_priority(rel_path: str) -> int:
    score = 0

    for i, prefix in enumerate(HIGH_SIGNAL_PREFIXES):
        if rel_path.startswith(prefix):
            score += (len(HIGH_SIGNAL_PREFIXES) - i) * 10
            break

    if rel_path.startswith("server/api/"):
        score += 80
    if "/auth/" in rel_path or "auth." in rel_path:
        score += 25
    if "/events/" in rel_path or "event" in rel_path.lower():
        score += 20
    if rel_path.endswith("index.ts") or rel_path.endswith("index.post.ts"):
        score += 10
    if rel_path in {"nuxt.config.ts", "app.py", "main.py"}:
        score += 30

    return score


def select_focus_files(root: Path, files: List[Path], max_files: int) -> List[Path]:
    rel_map = {f: f.relative_to(root).as_posix() for f in files}

    if max_files <= 0:
        return files

    mandatory: List[Path] = []
    for f, rel in rel_map.items():
        if any(rel.startswith(prefix) for prefix in HIGH_SIGNAL_PREFIXES[:7]):
            mandatory.append(f)

    mandatory = sorted(set(mandatory), key=lambda p: rel_map[p])

    if len(mandatory) >= max_files:
        ranked_mandatory = sorted(
            mandatory,
            key=lambda p: (-_file_priority(rel_map[p]), rel_map[p]),
        )
        return ranked_mandatory[:max_files]

    remaining = [f for f in files if f not in set(mandatory)]
    ranked_remaining = sorted(
        remaining,
        key=lambda p: (-_file_priority(rel_map[p]), rel_map[p]),
    )

    selected = mandatory + ranked_remaining[: max_files - len(mandatory)]
    return selected


def collect_tree_from_selected(
    root: Path, selected_files: List[Path], max_items: int = 250
) -> List[str]:
    dirs = set()
    files = []
    for p in selected_files:
        rel = p.relative_to(root).as_posix()
        files.append(rel)
        parent = p.parent
        while parent != root and root in parent.parents:
            dirs.add(parent.relative_to(root).as_posix() + "/")
            parent = parent.parent

    ordered = sorted(dirs) + sorted(files)
    if max_items <= 0:
        return ordered
    return ordered[:max_items]


def collect_source_snippets(
    root: Path,
    selected: List[Path],
    max_chars_per_file: int = 5000,
) -> Dict[str, str]:
    snippets: Dict[str, str] = {}
    for p in selected:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if max_chars_per_file <= 0:
            snippets[p.relative_to(root).as_posix()] = content
        else:
            snippets[p.relative_to(root).as_posix()] = content[:max_chars_per_file]
    return snippets


def load_json_if_exists(path: Optional[Path]) -> Optional[dict]:
    if not path:
        return None
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_auth_profile(auth_file: Path, profile_name: str) -> Optional[dict]:
    if not auth_file.exists() or not auth_file.is_file():
        return None
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return None
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        return None
    return profile


def compact_fanin_summary(data: Optional[dict], top_n: int = 30) -> Optional[dict]:
    if not data:
        return None
    top_modules = data.get("top_modules", [])
    return {
        "entrypoints_count": data.get("entrypoints_count"),
        "modules_ranked": data.get("modules_ranked"),
        "top_modules": top_modules[:top_n],
    }


def compact_git_summary(data: Optional[dict], top_n: int = 30) -> Optional[dict]:
    if not data:
        return None
    top_files = data.get("top_files", [])
    return {
        "files_ranked": data.get("files_ranked"),
        "top_files": top_files[:top_n],
    }


def compact_vulnerability_summary(
    data: Optional[dict], top_n: int = 30
) -> Optional[dict]:
    if not data:
        return None
    return {
        "files_scanned": data.get("files_scanned"),
        "rules_count": data.get("rules_count"),
        "findings_count": data.get("findings_count"),
        "top_findings": (data.get("top_findings") or [])[:top_n],
        "top_files": (data.get("top_files") or [])[:top_n],
    }


def build_user_payload(
    project_root: Path,
    tree_entries: List[str],
    snippets: Dict[str, str],
    selected_files: List[str],
    candidate_files: Optional[List[str]],
    analysis_scope: str,
    pr_url: Optional[str],
    model_name: str,
    fanin_summary: Optional[dict],
    git_summary: Optional[dict],
    vulnerability_summary: Optional[dict],
) -> dict:
    return {
        "project": {
            "name": project_root.name,
            "root": str(project_root),
            "language_hint": "mixed",
        },
        "request": {
            "task": "estimate contextual code reachability importance",
            "model_requested": model_name,
            "analysis_scope": analysis_scope,
            "must_return": "strict json matching PROMPT.md schema",
        },
        "inputs": {
            "selected_files": selected_files,
            "candidate_files": candidate_files,
            "pr_url": pr_url,
            "tree_entries": tree_entries,
            "source_snippets": snippets,
            "fanin_summary": fanin_summary,
            "git_history_summary": git_summary,
            "vulnerability_summary": vulnerability_summary,
        },
    }


def extract_json_best_effort(text: str) -> Optional[dict]:
    text = text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
    return None


def tool_list_files(
    project_root: Path,
    path: str,
    recursive: bool,
    include_glob: str,
    max_entries: int,
) -> dict:
    resolved = _safe_resolve(project_root, path)
    if not resolved or not resolved.exists() or not resolved.is_dir():
        return {"error": "invalid_directory", "path": path}

    out: List[str] = []
    iterator = resolved.rglob("*") if recursive else resolved.glob("*")
    for p in sorted(iterator):
        if _should_skip(p):
            continue
        rel = p.relative_to(project_root).as_posix()
        name = p.name + ("/" if p.is_dir() else "")
        if not fnmatch.fnmatch(name, include_glob) and not fnmatch.fnmatch(
            rel, include_glob
        ):
            continue
        out.append(rel + ("/" if p.is_dir() and not rel.endswith("/") else ""))
        if len(out) >= max_entries:
            break
    return {"path": resolved.relative_to(project_root).as_posix(), "entries": out}


def tool_read_file(
    project_root: Path, path: str, start_line: int, max_lines: int
) -> dict:
    resolved = _safe_resolve(project_root, path)
    if not resolved or not resolved.exists() or not resolved.is_file():
        return {"error": "invalid_file", "path": path}

    try:
        text = resolved.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {"error": "read_failed", "path": path}

    lines = text.splitlines()
    s = max(1, start_line)
    e = s + max(1, max_lines) - 1
    chunk = lines[s - 1 : e]
    return {
        "path": resolved.relative_to(project_root).as_posix(),
        "start_line": s,
        "end_line": s + len(chunk) - 1,
        "content": "\n".join(f"{i}: {line}" for i, line in enumerate(chunk, start=s)),
    }


def tool_search_code(
    project_root: Path,
    pattern: str,
    include_glob: str,
    max_hits: int,
) -> dict:
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return {"error": "invalid_regex", "message": str(exc), "pattern": pattern}

    hits: List[dict] = []
    for p in collect_source_files(project_root):
        rel = p.relative_to(project_root).as_posix()
        if include_glob and not fnmatch.fnmatch(rel, include_glob):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append({"path": rel, "line": i, "match": line[:400]})
                if len(hits) >= max_hits:
                    return {"pattern": pattern, "hits": hits}
    return {"pattern": pattern, "hits": hits}


def execute_tool_call(project_root: Path, name: str, args: dict) -> dict:
    if name == "list_files":
        return tool_list_files(
            project_root=project_root,
            path=str(args.get("path", ".")),
            recursive=bool(args.get("recursive", False)),
            include_glob=str(args.get("include_glob", "*")),
            max_entries=int(args.get("max_entries", 300)),
        )
    if name == "read_file":
        return tool_read_file(
            project_root=project_root,
            path=str(args.get("path", "")),
            start_line=int(args.get("start_line", 1)),
            max_lines=int(args.get("max_lines", 250)),
        )
    if name == "search_code":
        return tool_search_code(
            project_root=project_root,
            pattern=str(args.get("pattern", "")),
            include_glob=str(args.get("include_glob", "*.ts")),
            max_hits=int(args.get("max_hits", 200)),
        )
    return {"error": "unknown_tool", "tool": name}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-based reachability scanner using OpenAI-compatible API"
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        help=(
            "Absolute or relative project path. Optional when --pr-url is set "
            "(repository will be cloned to a temporary folder)."
        ),
    )
    parser.add_argument(
        "--prompt-file",
        default=str(Path(__file__).resolve().parent / "PROMPT.md"),
        help="Prompt instruction markdown file",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--provider",
        choices=["openai-compatible", "anthropic"],
        default="openai-compatible",
        help="LLM provider (default: openai-compatible)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OpenAI-compatible base URL",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable name that stores API key",
    )
    parser.add_argument(
        "--auth-file",
        default=str(DEFAULT_AUTH_FILE),
        help="Credentials JSON created by connect_provider.py",
    )
    parser.add_argument(
        "--auth-profile",
        default=None,
        help="Optional profile name from credentials JSON",
    )
    parser.add_argument(
        "--env-file",
        default=str(Path(__file__).resolve().parent / ".env"),
        help="Optional .env file to load before reading API key",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=80,
        help=(
            "Max source files for ranking candidates (<=0 means all). "
            "With --pr-url, this limits PR candidate files only."
        ),
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=5000,
        help="Max chars per source file snippet (<=0 means full file content)",
    )
    parser.add_argument(
        "--max-tree",
        type=int,
        default=250,
        help="Max tree entries (<=0 means include all selected tree entries)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Default: Research/experiment/runs/<project>/llm",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Optional pipeline run dir containing fanin/git_history/vulnerabilities summaries",
    )
    parser.add_argument(
        "--fanin-summary",
        default=None,
        help="Optional direct path to fanin summary.json",
    )
    parser.add_argument(
        "--git-summary",
        default=None,
        help="Optional direct path to git history summary.json",
    )
    parser.add_argument(
        "--vuln-summary",
        default=None,
        help="Optional direct path to vulnerability summary.json",
    )
    parser.add_argument(
        "--include-signals",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include fan-in, git-history, and vulnerability context in LLM payload (default: enabled)",
    )
    parser.add_argument(
        "--use-tools",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable model tool-calls for project exploration (default: enabled)",
    )
    parser.add_argument(
        "--max-tool-steps",
        type=int,
        default=18,
        help="Maximum tool-calling iterations before final answer",
    )
    parser.add_argument(
        "--pr-url",
        default=None,
        help="GitHub PR URL. If set, rank PR files only while keeping project context.",
    )
    parser.add_argument(
        "--pr-context-files",
        type=int,
        default=30,
        help="Additional non-PR files to include as context when --pr-url is set",
    )
    parser.add_argument(
        "--fallback-chat-model",
        default=DEFAULT_FALLBACK_CHAT_MODEL,
        help=(
            "Fallback model used when the selected model is unsupported by "
            "chat/completions (default: gpt-4.1-mini)"
        ),
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for LLM calls (default: 0.0 for stability)",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=1.0,
        help="Nucleus sampling parameter for LLM calls (default: 1.0)",
    )
    return parser.parse_args()


def load_dotenv_file(env_file: Path) -> None:
    if not env_file.exists() or not env_file.is_file():
        return

    try:
        lines = env_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    args = parse_args()

    env_file = Path(args.env_file).expanduser().resolve()
    load_dotenv_file(env_file)

    temp_clone: Optional[tempfile.TemporaryDirectory[str]] = None
    using_temp_clone = False
    if args.project_path:
        project_root = Path(args.project_path).expanduser().resolve()
    elif args.pr_url:
        print(
            "[info] No project_path provided. Cloning PR repository to temporary directory..."
        )
        project_root, temp_clone = prepare_temp_clone_for_pr(str(args.pr_url))
        using_temp_clone = True
        print(f"[info] Temporary clone ready: {project_root}")
    else:
        raise SystemExit("Either project_path or --pr-url must be provided.")

    if not project_root.exists() or not project_root.is_dir():
        raise SystemExit(
            f"Project path does not exist or is not a directory: {project_root}"
        )

    try:
        prompt_file = Path(args.prompt_file).expanduser().resolve()
        if not prompt_file.exists() or not prompt_file.is_file():
            raise SystemExit(f"Prompt file not found: {prompt_file}")
        prompt_instructions = prompt_file.read_text(encoding="utf-8")

        all_files = collect_source_files(project_root)
        candidate_files: Optional[List[Path]] = None
        selected_files: List[Path]
        analysis_scope = "project"
        pr_files_from_url: Optional[List[str]] = None

        if args.pr_url:
            analysis_scope = "pr_only"
            pr_files_from_url = fetch_pr_files(str(args.pr_url))
            pr_source_paths = {
                p for p in pr_files_from_url if Path(p).suffix.lower() in SOURCE_EXTS
            }
            candidate_files = [
                f
                for f in all_files
                if f.relative_to(project_root).as_posix() in pr_source_paths
            ]
            candidate_files = sorted(
                candidate_files,
                key=lambda p: (
                    -_file_priority(p.relative_to(project_root).as_posix()),
                    p.relative_to(project_root).as_posix(),
                ),
            )
            if args.max_files > 0:
                candidate_files = candidate_files[: args.max_files]
            if not candidate_files:
                raise SystemExit(
                    "PR does not contain any source files present under the local checkout. "
                    "Check repository mapping or verify changed files are source files."
                )
            selected_files = list(candidate_files)
            if args.pr_context_files > 0:
                context_files = select_focus_files(
                    project_root, all_files, max_files=args.pr_context_files
                )
                candidate_set = set(candidate_files)
                for p in context_files:
                    if p in candidate_set:
                        continue
                    selected_files.append(p)
                    if (
                        len(selected_files)
                        >= len(candidate_files) + args.pr_context_files
                    ):
                        break
        else:
            selected_files = select_focus_files(
                project_root, all_files, max_files=args.max_files
            )

        tree_entries = collect_tree_from_selected(
            project_root, selected_files, max_items=args.max_tree
        )
        snippets = collect_source_snippets(
            project_root,
            selected=selected_files,
            max_chars_per_file=args.max_chars,
        )

        run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
        fanin_path: Optional[Path] = None
        git_path: Optional[Path] = None
        vuln_path: Optional[Path] = None
        if args.include_signals:
            if args.fanin_summary:
                fanin_path = Path(args.fanin_summary).expanduser().resolve()
            elif run_dir:
                candidate = run_dir / "fanin" / "summary.json"
                fanin_path = candidate if candidate.exists() else None
            if args.git_summary:
                git_path = Path(args.git_summary).expanduser().resolve()
            elif run_dir:
                candidate = run_dir / "git_history" / "summary.json"
                git_path = candidate if candidate.exists() else None
            if args.vuln_summary:
                vuln_path = Path(args.vuln_summary).expanduser().resolve()
            elif run_dir:
                candidate = run_dir / "vulnerabilities" / "summary.json"
                vuln_path = candidate if candidate.exists() else None

        fanin_summary = compact_fanin_summary(load_json_if_exists(fanin_path))
        git_summary = compact_git_summary(load_json_if_exists(git_path))
        vulnerability_summary = compact_vulnerability_summary(
            load_json_if_exists(vuln_path)
        )

        user_payload = build_user_payload(
            project_root=project_root,
            tree_entries=tree_entries,
            snippets=snippets,
            selected_files=[
                p.relative_to(project_root).as_posix() for p in selected_files
            ],
            candidate_files=(
                [p.relative_to(project_root).as_posix() for p in candidate_files]
                if candidate_files is not None
                else None
            ),
            analysis_scope=analysis_scope,
            pr_url=args.pr_url,
            model_name=args.model,
            fanin_summary=fanin_summary,
            git_summary=git_summary,
            vulnerability_summary=vulnerability_summary,
        )

        selected_provider = args.provider
        auth_profile_name = args.auth_profile
        auth_profile: Optional[dict] = None
        auth_file = Path(args.auth_file).expanduser().resolve()

        if auth_profile_name:
            auth_profile = load_auth_profile(auth_file, auth_profile_name)
            if auth_profile is None:
                raise SystemExit(
                    f"Auth profile '{auth_profile_name}' not found in {auth_file}. "
                    "Run connect_provider.py login first."
                )
            selected_provider = str(auth_profile.get("provider", selected_provider))
            if args.base_url == DEFAULT_BASE_URL and auth_profile.get("base_url"):
                args.base_url = str(auth_profile.get("base_url"))
            if args.model == DEFAULT_MODEL and auth_profile.get("model"):
                args.model = str(auth_profile.get("model"))

        if selected_provider != "openai-compatible":
            raise SystemExit(
                "Only provider 'openai-compatible' is currently supported by this script. "
                "For Anthropic, add a provider adapter in this script first."
            )

        api_key = None
        if auth_profile:
            auth_block = auth_profile.get("auth")
            if isinstance(auth_block, dict) and auth_block.get("type") == "api":
                api_key = auth_block.get("key")
        if not api_key:
            api_key = os.getenv(args.api_key_env)
        if not api_key:
            raise SystemExit(
                f"Missing API key in env var {args.api_key_env}. "
                f"Set it first, e.g. export {args.api_key_env}=<your-key>"
            )

        client = OpenAI(api_key=api_key, base_url=args.base_url)
        active_model = args.model

        def chat_create_with_fallback(**kwargs: Any) -> Any:
            nonlocal active_model
            try:
                return client.chat.completions.create(model=active_model, **kwargs)
            except Exception as exc:
                message = str(exc)
                unsupported_chat = (
                    "not a chat model" in message.lower()
                    or "v1/chat/completions" in message.lower()
                )
                if (
                    unsupported_chat
                    and args.fallback_chat_model
                    and active_model != args.fallback_chat_model
                ):
                    print(
                        f"[warn] Model '{active_model}' is not supported by chat/completions. "
                        f"Falling back to '{args.fallback_chat_model}'."
                    )
                    active_model = args.fallback_chat_model
                    return client.chat.completions.create(model=active_model, **kwargs)
                raise

        json_schema = {
            "name": "reachability_ranking",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "analysis_version": {"type": "string"},
                    "generated_at": {"type": "string"},
                    "method": {
                        "type": "object",
                        "properties": {
                            "model": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["model", "description"],
                        "additionalProperties": False,
                    },
                    "ranked_targets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rank": {"type": "integer"},
                                "target": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "symbol": {"type": ["string", "null"]},
                                        "target_type": {
                                            "type": "string",
                                            "enum": [
                                                "route",
                                                "module",
                                                "function",
                                                "middleware",
                                                "model",
                                                "service",
                                            ],
                                        },
                                    },
                                    "required": ["path", "symbol", "target_type"],
                                    "additionalProperties": False,
                                },
                                "score": {"type": "integer"},
                                "confidence": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                },
                                "why": {"type": "string"},
                                "signals": {
                                    "type": "object",
                                    "properties": {
                                        "entrypoint_exposure": {
                                            "type": "string",
                                            "enum": ["none", "low", "medium", "high"],
                                        },
                                        "fanin_signal": {
                                            "type": "string",
                                            "enum": ["none", "low", "medium", "high"],
                                        },
                                        "git_activity_signal": {
                                            "type": "string",
                                            "enum": ["none", "low", "medium", "high"],
                                        },
                                        "business_criticality": {
                                            "type": "string",
                                            "enum": ["none", "low", "medium", "high"],
                                        },
                                    },
                                    "required": [
                                        "entrypoint_exposure",
                                        "fanin_signal",
                                        "git_activity_signal",
                                        "business_criticality",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                            "required": [
                                "rank",
                                "target",
                                "score",
                                "confidence",
                                "why",
                                "signals",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "global_observations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "limitations": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "project",
                    "analysis_version",
                    "generated_at",
                    "method",
                    "ranked_targets",
                    "global_observations",
                    "limitations",
                ],
                "additionalProperties": False,
            },
        }

        messages: List[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a static code reachability analyst. "
                    "Return only strict JSON that matches the requested schema. "
                    "Do not output markdown or prose outside JSON."
                ),
            },
            {"role": "user", "content": prompt_instructions},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

        tools: List[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files/directories under a project path",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "recursive": {"type": "boolean"},
                            "include_glob": {"type": "string"},
                            "max_entries": {"type": "integer"},
                        },
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file chunk with line numbers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer"},
                            "max_lines": {"type": "integer"},
                        },
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Regex search across project source files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "include_glob": {"type": "string"},
                            "max_hits": {"type": "integer"},
                        },
                        "required": ["pattern"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

        if args.use_tools:
            for _ in range(max(1, args.max_tool_steps)):
                turn = chat_create_with_fallback(
                    messages=messages,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    tools=tools,
                    tool_choice="auto",
                )
                msg = turn.choices[0].message
                tool_calls = msg.tool_calls or []
                if not tool_calls:
                    break

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                }
                normalized_calls: List[dict[str, Any]] = []
                for tc in tool_calls:
                    fn = getattr(tc, "function", None)
                    if not fn:
                        continue
                    name = getattr(fn, "name", "")
                    if not name:
                        continue
                    normalized_calls.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": getattr(fn, "arguments", "{}"),
                            },
                        }
                    )
                if normalized_calls:
                    assistant_msg["tool_calls"] = normalized_calls
                messages.append(assistant_msg)

                for tc in tool_calls:
                    fn = getattr(tc, "function", None)
                    if not fn:
                        continue
                    name = getattr(fn, "name", "")
                    if not name:
                        continue
                    try:
                        tool_args = json.loads(getattr(fn, "arguments", "{}") or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}
                    result = execute_tool_call(project_root, name, tool_args)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

            messages.append(
                {
                    "role": "user",
                    "content": "Now return only the final JSON result matching the schema.",
                }
            )

        response_mode = "json_schema"
        response_mode_error = None
        try:
            final_response = chat_create_with_fallback(
                messages=messages,
                temperature=args.temperature,
                top_p=args.top_p,
                response_format={"type": "json_schema", "json_schema": json_schema},
            )
        except Exception as exc:
            response_mode = "json_object"
            response_mode_error = str(exc)
            final_response = chat_create_with_fallback(
                messages=messages,
                temperature=args.temperature,
                top_p=args.top_p,
                response_format={"type": "json_object"},
            )

        raw_content = final_response.choices[0].message.content or ""
        parsed: Optional[dict] = extract_json_best_effort(raw_content)
        if parsed is None:
            parsed = {"error": "model_response_not_json", "raw": raw_content}

        if candidate_files is not None and isinstance(parsed, dict):
            candidate_rel = {
                p.relative_to(project_root).as_posix() for p in candidate_files
            }
            ranked_targets = parsed.get("ranked_targets")
            if isinstance(ranked_targets, list):
                filtered = []
                for item in ranked_targets:
                    if not isinstance(item, dict):
                        continue
                    target = item.get("target")
                    if not isinstance(target, dict):
                        continue
                    path = str(target.get("path") or "").strip()
                    if path in candidate_rel:
                        filtered.append(item)
                filtered.sort(
                    key=lambda it: (
                        -int(it.get("score") or 0),
                        str((it.get("target") or {}).get("path") or ""),
                    )
                )
                for i, item in enumerate(filtered, start=1):
                    item["rank"] = i
                parsed["ranked_targets"] = filtered
                limitations = parsed.get("limitations")
                if not isinstance(limitations, list):
                    limitations = []
                dropped_count = len(ranked_targets) - len(filtered)
                if dropped_count > 0:
                    limitations.append(
                        f"Dropped {dropped_count} non-PR targets from final output due to pr_only scope."
                    )
                parsed["limitations"] = limitations

        script_dir = Path(__file__).resolve().parent
        if args.output_dir:
            out_dir = Path(args.output_dir).expanduser().resolve()
        else:
            out_dir = script_dir / "runs" / project_root.name / "llm"
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "llm_reachability_ranking.json").write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (out_dir / "raw_response.txt").write_text(raw_content, encoding="utf-8")

        request_context = {
            "project_root": str(project_root),
            "prompt_file": str(prompt_file),
            "analysis_scope": analysis_scope,
            "pr_url": args.pr_url,
            "pr_files_count": len(pr_files_from_url or []),
            "candidate_files": (
                [p.relative_to(project_root).as_posix() for p in candidate_files]
                if candidate_files is not None
                else None
            ),
            "candidate_files_count": len(candidate_files) if candidate_files else None,
            "pr_context_files": args.pr_context_files if args.pr_url else None,
            "provider": selected_provider,
            "model": active_model,
            "requested_model": args.model,
            "base_url": args.base_url,
            "auth_file": str(auth_file),
            "auth_profile": auth_profile_name,
            "max_files": args.max_files,
            "selected_files_count": len(selected_files),
            "max_chars": args.max_chars,
            "max_tree": args.max_tree,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "use_tools": args.use_tools,
            "max_tool_steps": args.max_tool_steps,
            "include_signals": args.include_signals,
            "fanin_summary_path": str(fanin_path) if fanin_path else None,
            "git_summary_path": str(git_path) if git_path else None,
            "vuln_summary_path": str(vuln_path) if vuln_path else None,
            "response_mode": response_mode,
            "response_mode_error": response_mode_error,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        (out_dir / "request_context.json").write_text(
            json.dumps(request_context, indent=2),
            encoding="utf-8",
        )

        print("LLM reachability scan complete")
        print(f"Output directory: {out_dir}")
        print(f"Ranking JSON: {out_dir / 'llm_reachability_ranking.json'}")
        print(f"Raw response: {out_dir / 'raw_response.txt'}")
        return 0
    finally:
        if using_temp_clone:
            print("[info] Cleaning up temporary clone")
        if temp_clone is not None:
            temp_clone.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
