#!/usr/bin/env python3
"""
Simple static fan-in ranking from entry points.

This script builds a lightweight file-level import graph and computes, for each
reachable module, how many distinct entry-point files can reach it.

PoC goal:
- Input: project path
- Output: ranked modules by fan-in (count of reaching entry points)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


SOURCE_EXTS = {".ts", ".js", ".tsx", ".jsx", ".py", ".php", ".phtml"}
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


TS_IMPORT_RE = re.compile(
    r"(?:import\s+(?:type\s+)?[\s\S]*?from\s+|export\s+[\s\S]*?from\s+)[\"']([^\"']+)[\"']"
)
TS_REQUIRE_RE = re.compile(r"require\(\s*[\"']([^\"']+)[\"']\s*\)")
PY_FROM_RE = re.compile(r"^\s*from\s+([\w\.]+)\s+import\s+", re.MULTILINE)
PY_IMPORT_RE = re.compile(r"^\s*import\s+([\w\.]+)", re.MULTILINE)
PHP_INCLUDE_RE = re.compile(
    r"(?:include|include_once|require|require_once)\s*\(?\s*[\"']([^\"']+)[\"']\s*\)?",
    re.IGNORECASE,
)


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def list_source_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in SOURCE_EXTS and not should_skip(p):
            files.append(p)
    return files


def detect_entry_points(
    root: Path, files: Iterable[Path], explicit_prefixes: List[str]
) -> List[Path]:
    rel_files = [f.relative_to(root) for f in files]

    if explicit_prefixes:
        entries = []
        for rf in rel_files:
            rf_posix = rf.as_posix()
            if any(
                rf_posix.startswith(prefix.rstrip("/") + "/")
                for prefix in explicit_prefixes
            ):
                entries.append(root / rf)
        if entries:
            return sorted(set(entries))

    # Auto-detect common API entrypoint folders
    common_prefixes = [
        "server/api/",  # Nuxt/Nitro
        "api/",  # generic
        "routes/",  # express/flask-like folder names
        "app/api/",  # next.js style
        "website/",  # common PHP app root
        "public/",
        "web/",
        "src/",
    ]
    entries = []
    for rf in rel_files:
        rf_posix = rf.as_posix()
        if any(rf_posix.startswith(prefix) for prefix in common_prefixes):
            entries.append(root / rf)

    # Fallback: Python Flask route decorators
    if not entries:
        route_markers = ("@app.route", "Blueprint(", "APIRouter(", "router =")
        for f in files:
            if f.suffix != ".py":
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(m in txt for m in route_markers):
                entries.append(f)

    # Fallback: PHP route/controller hints
    if not entries:
        php_markers = (
            "->get(",
            "->post(",
            "->put(",
            "->delete(",
            "Route::",
            "addRoute(",
            "$_GET",
            "$_POST",
        )
        for f in files:
            if f.suffix not in {".php", ".phtml"}:
                continue
            rel_path = f.relative_to(root).as_posix().lower()
            if any(
                part in rel_path
                for part in (
                    "/controller",
                    "/controllers/",
                    "/route",
                    "/routes/",
                    "/api/",
                )
            ):
                entries.append(f)
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(m in txt for m in php_markers):
                entries.append(f)

    # Last resort: pick likely bootstrap files by name/depth.
    if not entries:
        priority_names = {
            "index",
            "main",
            "app",
            "server",
            "bootstrap",
            "routes",
            "api",
        }
        ranked = sorted(
            files,
            key=lambda f: (
                0 if f.stem.lower() in priority_names else 1,
                len(f.relative_to(root).parts),
                f.relative_to(root).as_posix(),
            ),
        )
        entries = ranked[: min(30, len(ranked))]

    return sorted(set(entries))


def resolve_module_path(spec: str, importer: Path, root: Path) -> Optional[Path]:
    """Resolve a local/internal import specifier to an actual file path.

    We intentionally ignore external packages.
    """
    is_relative = spec.startswith(".")
    is_alias_root = spec.startswith("~/") or spec.startswith("@/")
    is_absolute_internal = re.match(r"^[a-zA-Z_][\w\-/]*$", spec) is not None

    base_candidates: List[Path] = []

    if is_relative:
        base_candidates.append((importer.parent / spec).resolve())
    elif is_alias_root:
        base_candidates.append((root / spec[2:]).resolve())
    elif is_absolute_internal:
        # Heuristic for path aliases like server/*, utils/*, components/*
        base_candidates.append((root / spec).resolve())
    else:
        return None

    suffix_candidates = ["", ".ts", ".tsx", ".js", ".jsx", ".py", ".php", ".phtml"]
    index_candidates = [
        "index.ts",
        "index.tsx",
        "index.js",
        "index.jsx",
        "__init__.py",
        "index.php",
    ]

    for base in base_candidates:
        for sfx in suffix_candidates:
            candidate = Path(str(base) + sfx)
            if candidate.exists() and candidate.is_file() and root in candidate.parents:
                return candidate
        if base.exists() and base.is_dir() and root in base.parents:
            for idx in index_candidates:
                candidate = base / idx
                if candidate.exists() and candidate.is_file():
                    return candidate
    return None


def extract_import_specs(file_path: Path) -> List[str]:
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    specs: List[str] = []
    if file_path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
        specs.extend(TS_IMPORT_RE.findall(text))
        specs.extend(TS_REQUIRE_RE.findall(text))
    elif file_path.suffix == ".py":
        specs.extend(PY_FROM_RE.findall(text))
        specs.extend(PY_IMPORT_RE.findall(text))
    elif file_path.suffix in {".php", ".phtml"}:
        specs.extend(PHP_INCLUDE_RE.findall(text))

    return specs


def build_import_graph(root: Path, files: List[Path]) -> Dict[Path, Set[Path]]:
    graph: Dict[Path, Set[Path]] = defaultdict(set)
    file_set = set(files)
    for f in files:
        specs = extract_import_specs(f)
        for spec in specs:
            resolved = resolve_module_path(spec, importer=f, root=root)
            if resolved and resolved in file_set and resolved != f:
                graph[f].add(resolved)
    return graph


def reachable_from_entry(graph: Dict[Path, Set[Path]], entry: Path) -> Set[Path]:
    seen: Set[Path] = set()
    q: deque[Path] = deque([entry])
    while q:
        node = q.popleft()
        if node in seen:
            continue
        seen.add(node)
        for nxt in graph.get(node, set()):
            if nxt not in seen:
                q.append(nxt)
    return seen


def compute_fan_in(
    root: Path,
    entries: List[Path],
    graph: Dict[Path, Set[Path]],
) -> Tuple[Dict[Path, int], Dict[Path, Set[Path]]]:
    fan_in: Dict[Path, int] = defaultdict(int)
    reached_by: Dict[Path, Set[Path]] = defaultdict(set)

    for e in entries:
        reached = reachable_from_entry(graph, e)
        for mod in reached:
            reached_by[mod].add(e)

    for mod, eps in reached_by.items():
        fan_in[mod] = len(eps)

    return fan_in, reached_by


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def write_outputs(
    out_dir: Path,
    root: Path,
    entries: List[Path],
    fan_in: Dict[Path, int],
    reached_by: Dict[Path, Set[Path]],
    top_n: int,
    engine: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(fan_in.items(), key=lambda kv: (-kv[1], rel(kv[0], root)))

    csv_path = out_dir / "fanin_ranking.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "module", "fan_in", "entrypoints_reaching"])
        for i, (mod, score) in enumerate(ranked, start=1):
            eps = sorted(rel(e, root) for e in reached_by.get(mod, set()))
            w.writerow([i, rel(mod, root), score, "; ".join(eps)])

    summary = {
        "project_root": str(root),
        "engine": engine,
        "entrypoints_count": len(entries),
        "entrypoints": [rel(e, root) for e in entries],
        "modules_ranked": len(ranked),
        "top_n": top_n,
        "top_modules": [
            {
                "rank": i,
                "module": rel(mod, root),
                "fan_in": score,
                "entrypoints_reaching": sorted(
                    rel(e, root) for e in reached_by.get(mod, set())
                ),
            }
            for i, (mod, score) in enumerate(ranked[:top_n], start=1)
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    md_lines = [
        "# Fan-in Ranking",
        "",
        f"- Project: `{root}`",
        f"- Engine: `{engine}`",
        f"- Entry points detected: `{len(entries)}`",
        f"- Modules ranked: `{len(ranked)}`",
        "",
        "## Top Modules",
        "",
        "| Rank | Module | Fan-in |",
        "|---:|---|---:|",
    ]
    for i, (mod, score) in enumerate(ranked[:top_n], start=1):
        md_lines.append(f"| {i} | `{rel(mod, root)}` | {score} |")
    md_lines.append("")
    md_lines.append("## Notes")
    md_lines.append("")
    md_lines.append(
        "- Fan-in is file-level: number of distinct entrypoint files that can reach a module through import edges."
    )
    if engine == "codeql":
        md_lines.append(
            "- Reachability edges were extracted via CodeQL import resolution on a CodeQL database."
        )
    else:
        md_lines.append(
            "- Reachability edges were extracted with a local regex import parser (heuristic mode)."
        )
    (out_dir / "report.md").write_text("\n".join(md_lines), encoding="utf-8")


def detect_project_language(files: List[Path]) -> str:
    js_like = sum(1 for f in files if f.suffix in {".ts", ".tsx", ".js", ".jsx"})
    py_like = sum(1 for f in files if f.suffix == ".py")
    php_like = sum(1 for f in files if f.suffix in {".php", ".phtml"})
    if js_like >= py_like and js_like >= php_like:
        return "javascript"
    if py_like >= php_like:
        return "python"
    return "php"


def ensure_codeql_available() -> str:
    codeql_bin = shutil.which("codeql")
    if not codeql_bin:
        raise SystemExit(
            "CodeQL CLI not found in PATH. Install CodeQL CLI or run with --engine heuristic."
        )
    return codeql_bin


def ql_regex_from_prefixes(prefixes: List[str]) -> str:
    active = prefixes or ["server/api", "api", "routes", "app/api"]
    escaped = [re.escape(p.strip("/")) for p in active if p.strip("/")]
    if not escaped:
        escaped = ["server/api", "api", "routes", "app/api"]
    return "^(" + "|".join(f"{p}/" for p in escaped) + ").*"


def build_codeql_query_text(prefixes: List[str]) -> str:
    _ = ql_regex_from_prefixes(prefixes)
    return """/**
 * @name Import edges for fan-in
 * @description Extract importer file and imported path string.
 * @kind table
 */
import javascript

from Import imp
where exists(imp.getImportedPathString())
select imp.getFile().getRelativePath(), imp.getImportedPathString()
"""


def run_cmd(command: str, workdir: Path, description: str) -> None:
    proc = subprocess.run(
        command,
        cwd=str(workdir),
        shell=True,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"{description} failed.\nCommand: {command}\n{err}")


def init_temp_query_pack(tmp_dir: Path) -> None:
    qlpack = tmp_dir / "qlpack.yml"
    qlpack.write_text(
        "\n".join(
            [
                "name: local/fanin-query",
                "version: 0.0.0",
                "dependencies:",
                "  codeql/javascript-all: '*'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_cmd("codeql pack install", workdir=tmp_dir, description="CodeQL pack install")


def compute_fan_in_codeql(
    root: Path,
    files: List[Path],
    entries: List[Path],
    explicit_prefixes: List[str],
    codeql_db_dir: Optional[Path],
) -> Tuple[Dict[Path, int], Dict[Path, Set[Path]]]:
    ensure_codeql_available()

    with tempfile.TemporaryDirectory(prefix="fanin_codeql_") as tmp:
        tmp_dir = Path(tmp)
        query_file = tmp_dir / "entry_import_reachability.ql"
        bqrs_file = tmp_dir / "reachability.bqrs"
        decoded_csv = tmp_dir / "reachability.csv"

        init_temp_query_pack(tmp_dir)

        if codeql_db_dir:
            db_dir = codeql_db_dir
            db_dir.mkdir(parents=True, exist_ok=True)
        else:
            db_dir = tmp_dir / "codeql-db"

        query_file.write_text(
            build_codeql_query_text(explicit_prefixes), encoding="utf-8"
        )

        language = detect_project_language(files)
        if language != "javascript":
            raise SystemExit(
                f"CodeQL fan-in currently supports JavaScript/TypeScript projects. Detected language: {language}."
            )

        run_cmd(
            f'codeql database create "{db_dir}" --overwrite --language=javascript --source-root "{root}"',
            workdir=root,
            description="CodeQL database create",
        )

        run_cmd(
            f'codeql query run "{query_file}" --database "{db_dir}" --output "{bqrs_file}"',
            workdir=tmp_dir,
            description="CodeQL query run",
        )

        run_cmd(
            f'codeql bqrs decode "{bqrs_file}" --format=csv --output "{decoded_csv}"',
            workdir=root,
            description="CodeQL bqrs decode",
        )

        graph: Dict[Path, Set[Path]] = defaultdict(set)
        file_set = set(files)

        with decoded_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                importer_rel, spec = row[0].strip(), row[1].strip()
                if not importer_rel or not spec:
                    continue
                importer = (root / importer_rel).resolve()
                if importer not in file_set:
                    continue
                resolved = resolve_module_path(spec, importer=importer, root=root)
                if resolved and resolved in file_set and resolved != importer:
                    graph[importer].add(resolved)

        return compute_fan_in(root, entries, graph)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute simple fan-in ranking from project path"
    )
    parser.add_argument("project_path", help="Absolute or relative project path")
    parser.add_argument(
        "--engine",
        choices=["codeql", "heuristic"],
        default="codeql",
        help="Reachability engine to use (default: codeql)",
    )
    parser.add_argument(
        "--entry-prefix",
        action="append",
        default=[],
        help="Path prefix (relative to project root) to treat as entry points. Can be passed multiple times.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="How many top rows to print and include in report",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Default: Research/experiment/fanin_outputs/<project>_<timestamp>",
    )
    parser.add_argument(
        "--codeql-db-dir",
        default=None,
        help="Optional persistent CodeQL database dir (only used in codeql engine)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = Path(args.project_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Project path does not exist or is not a directory: {root}")

    files = list_source_files(root)
    entries = detect_entry_points(root, files, explicit_prefixes=args.entry_prefix)
    if not entries:
        raise SystemExit(
            "No entry points found. Pass --entry-prefix (e.g. --entry-prefix server/api) for your project layout."
        )

    if args.engine == "codeql":
        detected_language = detect_project_language(files)
        if detected_language != "javascript":
            print(
                f"[warn] CodeQL engine currently supports JavaScript/TypeScript only. "
                f"Detected language: {detected_language}. Falling back to heuristic engine."
            )
            args.engine = "heuristic"

    if args.engine == "codeql":
        db_dir = (
            Path(args.codeql_db_dir).expanduser().resolve()
            if args.codeql_db_dir
            else None
        )
        fan_in, reached_by = compute_fan_in_codeql(
            root=root,
            files=files,
            entries=entries,
            explicit_prefixes=args.entry_prefix,
            codeql_db_dir=db_dir,
        )
    else:
        graph = build_import_graph(root, files)
        fan_in, reached_by = compute_fan_in(root, entries, graph)

    script_dir = Path(__file__).resolve().parent
    if args.output_dir:
        out_dir = Path(args.output_dir).expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = script_dir / "fanin_outputs" / f"{root.name}_{stamp}"

    write_outputs(
        out_dir,
        root,
        entries,
        fan_in,
        reached_by,
        top_n=args.top,
        engine=args.engine,
    )

    ranked = sorted(fan_in.items(), key=lambda kv: (-kv[1], rel(kv[0], root)))
    print(f"Project: {root}")
    print(f"Detected source files: {len(files)}")
    print(f"Engine: {args.engine}")
    print(f"Detected entry points: {len(entries)}")
    print(f"Ranked modules: {len(ranked)}")
    print(f"Output directory: {out_dir}")
    print("")
    print(f"Top {min(args.top, len(ranked))} modules by fan-in:")
    for i, (mod, score) in enumerate(ranked[: args.top], start=1):
        print(f"{i:>2}. {rel(mod, root)} (fan-in={score})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
