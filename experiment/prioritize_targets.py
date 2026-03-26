#!/usr/bin/env python3
"""
Build a human-priority table from vulnerability and LLM reachability signals.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


NON_RUNTIME_SUFFIXES = {".md", ".markdown", ".txt", ".sql"}


CVSS_METRIC_VALUES = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "C": {"N": 0.0, "L": 0.22, "H": 0.56},
    "I": {"N": 0.0, "L": 0.22, "H": 0.56},
    "A": {"N": 0.0, "L": 0.22, "H": 0.56},
}

CVSS_RULE_VECTORS = {
    "command_injection_tainted": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "file_inclusion_tainted_path": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "sql_injection_tainted_query": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "sql_injection_unescaped_args": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "sql_dynamic_interpolation": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "stored_input_to_database": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N",
    "path_traversal_tainted_path": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:L",
    "xss_reflected_short_echo": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
    "xss_reflected_tainted_output": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
    "xss_unsanitized_data_output": "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N",
    "idor_unprotected_object_lookup": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:N",
    "idor_parameterized_object_lookup": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N",
    "predictable_session_token": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    "discount_reapplication_logic": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N",
    "weak_default_credentials": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L",
    "weak_hash_md5_sha1": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N",
}

CATEGORY_DEFAULT_VECTORS = {
    "command_injection": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "file_inclusion": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "injection": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "path_traversal": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:L",
    "xss": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
    "access_control": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N",
    "session": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    "business_logic": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N",
    "authentication": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L",
    "crypto": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prioritize targets from vulnerability and LLM reachability signals"
    )
    parser.add_argument("--run-dir", default=None, help="Pipeline run directory")
    parser.add_argument("--llm-ranking", default=None, help="Path to LLM ranking JSON")
    parser.add_argument(
        "--vuln-findings", default=None, help="Path to vulnerability findings CSV"
    )
    parser.add_argument(
        "--fanin-summary", default=None, help="Path to fan-in summary.json"
    )
    parser.add_argument(
        "--git-summary", default=None, help="Path to git history summary.json"
    )
    parser.add_argument(
        "--include-non-runtime",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include docs/non-runtime files like README.md in output",
    )
    parser.add_argument("--top", type=int, default=25, help="Top rows to include")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    return parser.parse_args()


def load_json(path: Path) -> Optional[dict]:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def round_up_1_decimal(x: float) -> float:
    return math.ceil(x * 10.0) / 10.0


def parse_cvss_vector(vector: str) -> Optional[Dict[str, str]]:
    if not vector or not vector.startswith("CVSS:3.1/"):
        return None
    items = vector.split("/")[1:]
    out: Dict[str, str] = {}
    for item in items:
        if ":" not in item:
            return None
        k, v = item.split(":", 1)
        out[k] = v
    required = {"AV", "AC", "PR", "UI", "S", "C", "I", "A"}
    if not required.issubset(set(out.keys())):
        return None
    return out


def pr_value(pr: str, scope: str) -> float:
    if scope == "U":
        return {"N": 0.85, "L": 0.62, "H": 0.27}[pr]
    return {"N": 0.85, "L": 0.68, "H": 0.5}[pr]


def cvss31_base_score(vector: str) -> float:
    m = parse_cvss_vector(vector)
    if not m:
        return 0.0

    av = CVSS_METRIC_VALUES["AV"][m["AV"]]
    ac = CVSS_METRIC_VALUES["AC"][m["AC"]]
    pr = pr_value(m["PR"], m["S"])
    ui = CVSS_METRIC_VALUES["UI"][m["UI"]]
    c = CVSS_METRIC_VALUES["C"][m["C"]]
    i = CVSS_METRIC_VALUES["I"][m["I"]]
    a = CVSS_METRIC_VALUES["A"][m["A"]]

    exploitability = 8.22 * av * ac * pr * ui
    iss = 1.0 - (1.0 - c) * (1.0 - i) * (1.0 - a)

    if m["S"] == "U":
        impact = 6.42 * iss
        total = impact + exploitability
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
        total = 1.08 * (impact + exploitability)

    if impact <= 0:
        return 0.0
    return round_up_1_decimal(clamp(total, 0.0, 10.0))


def vector_for_row(row: Dict[str, str]) -> str:
    explicit = (row.get("cvss_vector") or "").strip()
    if explicit.startswith("CVSS:3.1/"):
        return explicit
    rule_id = (row.get("rule_id") or "").strip()
    if rule_id in CVSS_RULE_VECTORS:
        return CVSS_RULE_VECTORS[rule_id]
    category = (row.get("category") or "").strip().lower()
    return CATEGORY_DEFAULT_VECTORS.get(
        category, "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N"
    )


def vuln_priority(max_cvss: float, findings_count: int) -> float:
    return clamp(max_cvss * 10.0 + min(findings_count, 10) * 3.0, 0.0, 100.0)


def priority_tier(score: float) -> str:
    if score >= 75:
        return "P1"
    if score >= 55:
        return "P2"
    return "P3"


def main() -> int:
    args = parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None

    llm_path = (
        Path(args.llm_ranking).expanduser().resolve()
        if args.llm_ranking
        else (run_dir / "llm" / "llm_reachability_ranking.json" if run_dir else None)
    )
    vuln_csv_path = (
        Path(args.vuln_findings).expanduser().resolve()
        if args.vuln_findings
        else (run_dir / "vulnerabilities" / "findings.csv" if run_dir else None)
    )
    fanin_path = (
        Path(args.fanin_summary).expanduser().resolve()
        if args.fanin_summary
        else (run_dir / "fanin" / "summary.json" if run_dir else None)
    )
    git_path = (
        Path(args.git_summary).expanduser().resolve()
        if args.git_summary
        else (run_dir / "git_history" / "summary.json" if run_dir else None)
    )

    if not llm_path or not llm_path.exists():
        raise SystemExit(
            "Missing LLM ranking JSON. Run LLM step first or pass --llm-ranking."
        )
    if not vuln_csv_path or not vuln_csv_path.exists():
        raise SystemExit(
            "Missing vulnerability findings CSV. Run vulnerability step first or pass --vuln-findings."
        )

    llm_data = load_json(llm_path)
    if not llm_data:
        raise SystemExit(f"Invalid LLM ranking JSON: {llm_path}")

    ranked_targets = llm_data.get("ranked_targets")
    if not isinstance(ranked_targets, list):
        raise SystemExit("LLM ranking JSON missing ranked_targets array")

    fanin_data = load_json(fanin_path) if fanin_path else None
    git_data = load_json(git_path) if git_path else None

    fanin_by_path: Dict[str, Dict[str, Any]] = {}
    if fanin_data and isinstance(fanin_data.get("top_modules"), list):
        for m in fanin_data["top_modules"]:
            if not isinstance(m, dict):
                continue
            module = str(m.get("module") or "").strip()
            if not module:
                continue
            fanin_by_path[module] = {
                "fan_in": int(m.get("fan_in") or 0),
                "fanin_rank": int(m.get("rank") or 0),
            }

    git_by_path: Dict[str, Dict[str, Any]] = {}
    if git_data and isinstance(git_data.get("top_files"), list):
        for g in git_data["top_files"]:
            if not isinstance(g, dict):
                continue
            file_path = str(g.get("file") or "").strip()
            if not file_path:
                continue
            git_by_path[file_path] = {
                "git_commits_touched": int(g.get("commits_touched") or 0),
                "git_churn": int(g.get("churn") or 0),
                "git_rank": int(g.get("rank") or 0),
            }

    vuln_by_path: Dict[str, Dict[str, Any]] = {}
    with vuln_csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            path = (row.get("path") or "").strip()
            if not path:
                continue
            cvss_vector = vector_for_row(row)
            cvss = cvss31_base_score(cvss_vector)
            finding = {
                "line": int((row.get("line") or "0").strip() or 0),
                "rule_id": (row.get("rule_id") or "").strip(),
                "category": (row.get("category") or "").strip(),
                "severity": (row.get("severity") or "").strip(),
                "confidence": (row.get("confidence") or "").strip(),
                "cvss_base": cvss,
                "cvss_vector": cvss_vector,
                "source": (row.get("source") or "").strip(),
                "sink": (row.get("sink") or "").strip(),
                "description": (row.get("description") or "").strip(),
                "snippet": (row.get("snippet") or "").strip(),
            }
            item = vuln_by_path.setdefault(
                path,
                {
                    "path": path,
                    "findings_count": 0,
                    "max_cvss": 0.0,
                    "max_cvss_vector": "",
                    "avg_cvss_sum": 0.0,
                    "high_findings": 0,
                    "findings": [],
                },
            )
            item["findings_count"] += 1
            item["avg_cvss_sum"] += cvss
            if cvss >= float(item["max_cvss"]):
                item["max_cvss"] = cvss
                item["max_cvss_vector"] = cvss_vector
            if (row.get("severity") or "").strip().lower() == "high":
                item["high_findings"] += 1
            item["findings"].append(finding)

    for item in vuln_by_path.values():
        count = int(item["findings_count"])
        item["avg_cvss"] = (
            round(float(item["avg_cvss_sum"]) / count, 2) if count else 0.0
        )
        item["vuln_priority"] = round(vuln_priority(float(item["max_cvss"]), count), 2)
        item["findings"] = sorted(
            item["findings"],
            key=lambda f: (-float(f.get("cvss_base", 0.0)), int(f.get("line", 0))),
        )

    llm_by_path: Dict[str, Dict[str, Any]] = {}
    for t in ranked_targets:
        if not isinstance(t, dict):
            continue
        target = t.get("target") or {}
        if not isinstance(target, dict):
            continue
        path = str(target.get("path") or "").strip()
        if not path:
            continue
        llm_by_path[path] = {
            "path": path,
            "target_type": str(target.get("target_type") or "module"),
            "llm_score": float(t.get("score") or 0),
            "llm_rank": int(t.get("rank") or 0),
            "llm_confidence": str(t.get("confidence") or "low"),
        }

    rows: List[Dict[str, Any]] = []
    # Only prioritize files present in baseline vulnerability findings.
    # This guarantees every ranked row has a vulnerability-derived baseline signal.
    all_paths = set(vuln_by_path.keys())
    for path in sorted(all_paths):
        if (
            not args.include_non_runtime
            and Path(path).suffix.lower() in NON_RUNTIME_SUFFIXES
        ):
            continue

        llm = llm_by_path.get(path)
        vuln = vuln_by_path.get(path)
        if not vuln:
            continue
        if float(vuln.get("max_cvss", 0.0)) <= 0.0:
            continue
        fanin = fanin_by_path.get(path, {})
        git = git_by_path.get(path, {})

        llm_score = float(llm["llm_score"]) if llm else 35.0
        vp = float(vuln.get("vuln_priority", 0.0))
        score = round(0.6 * vp + 0.4 * llm_score, 2)

        reason = []
        if vuln:
            reason.append(
                f"cvss {float(vuln['max_cvss']):.1f} ({str(vuln.get('max_cvss_vector') or '')}), findings={int(vuln['findings_count'])}"
            )
        if llm:
            reason.append(f"llm reachability score={llm_score:.0f}")
        else:
            reason.append("no llm coverage for this path")
        if not reason:
            reason.append("insufficient evidence")

        rows.append(
            {
                "path": path,
                "target_type": (llm.get("target_type") if llm else "module"),
                "has_llm_coverage": bool(llm),
                "llm_score": round(llm_score, 2),
                "llm_rank": llm.get("llm_rank") if llm else None,
                "llm_confidence": llm.get("llm_confidence") if llm else None,
                "fan_in": int(fanin.get("fan_in", 0)),
                "fanin_rank": fanin.get("fanin_rank"),
                "git_commits_touched": int(git.get("git_commits_touched", 0)),
                "git_churn": int(git.get("git_churn", 0)),
                "git_rank": git.get("git_rank"),
                "max_cvss": round(float(vuln.get("max_cvss", 0.0)) if vuln else 0.0, 2),
                "max_cvss_vector": str(vuln.get("max_cvss_vector", "")) if vuln else "",
                "avg_cvss": round(float(vuln.get("avg_cvss", 0.0)) if vuln else 0.0, 2),
                "vuln_findings": int(vuln.get("findings_count", 0)) if vuln else 0,
                "high_findings": int(vuln.get("high_findings", 0)) if vuln else 0,
                "vuln_evidence": (vuln.get("findings", [])[:5] if vuln else []),
                "priority_score": score,
                "priority_tier": priority_tier(score),
                "why": "; ".join(reason),
            }
        )

    rows.sort(
        key=lambda r: (
            -float(r["priority_score"]),
            -float(r["max_cvss"]),
            -int(r["vuln_findings"]),
            str(r["path"]),
        )
    )

    top = rows[: args.top] if args.top > 0 else rows
    for i, r in enumerate(top, start=1):
        r["rank"] = i
        evidence = r.get("vuln_evidence") or []
        primary = evidence[0] if evidence else {}
        r["primary_vuln_line"] = int(primary.get("line", 0)) if primary else None
        r["primary_vuln_rule"] = str(primary.get("rule_id", "")) if primary else ""
        r["primary_vuln_category"] = str(primary.get("category", "")) if primary else ""
        r["primary_vuln_severity"] = str(primary.get("severity", "")) if primary else ""
        r["primary_vuln_cvss"] = (
            float(primary.get("cvss_base", 0.0)) if primary else 0.0
        )
        r["primary_vuln_snippet"] = str(primary.get("snippet", "")) if primary else ""

    if args.output_dir:
        out_dir = Path(args.output_dir).expanduser().resolve()
    elif run_dir:
        out_dir = run_dir / "prioritization"
    else:
        out_dir = Path(__file__).resolve().parent / "prioritization_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "llm_ranking": str(llm_path),
        "vuln_findings": str(vuln_csv_path),
        "rows_total": len(rows),
        "top_n": args.top,
        "top_priorities": top,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    with (out_dir / "priorities.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "rank",
                "path",
                "target_type",
                "priority_tier",
                "priority_score",
                "has_llm_coverage",
                "llm_score",
                "llm_rank",
                "llm_confidence",
                "fan_in",
                "fanin_rank",
                "git_commits_touched",
                "git_churn",
                "git_rank",
                "max_cvss",
                "max_cvss_vector",
                "avg_cvss",
                "vuln_findings",
                "high_findings",
                "primary_vuln_line",
                "primary_vuln_rule",
                "primary_vuln_category",
                "primary_vuln_severity",
                "primary_vuln_cvss",
                "primary_vuln_snippet",
                "vuln_evidence_json",
                "why",
            ]
        )
        for r in top:
            w.writerow(
                [
                    r.get("rank"),
                    r["path"],
                    r["target_type"],
                    r["priority_tier"],
                    r["priority_score"],
                    r["has_llm_coverage"],
                    r["llm_score"],
                    r["llm_rank"],
                    r["llm_confidence"],
                    r["fan_in"],
                    r["fanin_rank"],
                    r["git_commits_touched"],
                    r["git_churn"],
                    r["git_rank"],
                    r["max_cvss"],
                    r["max_cvss_vector"],
                    r["avg_cvss"],
                    r["vuln_findings"],
                    r["high_findings"],
                    r["primary_vuln_line"],
                    r["primary_vuln_rule"],
                    r["primary_vuln_category"],
                    r["primary_vuln_severity"],
                    r["primary_vuln_cvss"],
                    r["primary_vuln_snippet"],
                    json.dumps(r.get("vuln_evidence", []), ensure_ascii=True),
                    r["why"],
                ]
            )

    md = [
        "# Human Prioritization Table",
        "",
        "Combined priority from CVSS v3.1 base score (vector-mapped) and LLM reachability.",
        "",
        "| Rank | Target | Tier | Priority | LLM | Max CVSS | Primary Vuln | Line |",
        "|---:|---|---|---:|---:|---:|---|---:|",
    ]
    for r in top:
        md.append(
            f"| {r['rank']} | `{r['path']}` | {r['priority_tier']} | {r['priority_score']:.2f} | {r['llm_score']:.0f} | {r['max_cvss']:.1f} | `{r.get('primary_vuln_rule') or ''}` | {r.get('primary_vuln_line') or ''} |"
        )
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")

    print("Prioritization complete")
    print(f"Output directory: {out_dir}")
    print(f"Top table: {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
