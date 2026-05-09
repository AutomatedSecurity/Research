#!/usr/bin/env python3
"""
Compute per-repo and cross-repo evaluation metrics from benchmark outputs.

Supports:
- Ranking metrics: Precision@K, Recall@K, NDCG@K, MRR, MAP
- Classification metrics: Precision, Recall, F1, Accuracy

Ground-truth labels can come from:
- proxy label rules over prioritization output (default), or
- explicit labels CSV provided by the user.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class ScoredItem:
    path: str
    score: float
    relevant: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute ranking/classification metrics for benchmark suite"
    )
    parser.add_argument("--suite-dir", required=True, help="Path to suite_<timestamp> dir")
    parser.add_argument(
        "--k-values",
        default="5,10,20",
        help="Comma-separated K values for @K metrics",
    )
    parser.add_argument(
        "--label-mode",
        choices=["cvss9", "cvss7", "high_any", "labels-file"],
        default="cvss9",
        help="Ground truth labeling mode",
    )
    parser.add_argument(
        "--labels-file",
        default=None,
        help="CSV with columns: repo,path,label (required when --label-mode labels-file)",
    )
    parser.add_argument(
        "--output-prefix",
        default="metrics",
        help="Prefix for generated output files",
    )
    return parser.parse_args()


def parse_k_values(raw: str) -> List[int]:
    values: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        k = int(part)
        if k > 0:
            values.append(k)
    if not values:
        raise SystemExit("No valid K values provided")
    return sorted(set(values))


def load_suite_rows(suite_dir: Path) -> List[dict]:
    p = suite_dir / "evaluation_results.json"
    if not p.exists():
        raise SystemExit(f"Missing suite results file: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SystemExit("Invalid suite results JSON: rows missing")
    return [r for r in rows if isinstance(r, dict) and r.get("status") == "ok"]


def read_priorities_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_float(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def to_int(v: str, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def load_explicit_labels(labels_file: Path) -> Dict[Tuple[str, str], int]:
    if not labels_file.exists():
        raise SystemExit(f"Labels file not found: {labels_file}")
    out: Dict[Tuple[str, str], int] = {}
    with labels_file.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            repo = str(row.get("repo") or "").strip()
            item_path = str(row.get("path") or "").strip()
            label = to_int(str(row.get("label") or "0"), 0)
            if repo and item_path:
                out[(repo, item_path)] = 1 if label else 0
    return out


def label_for_row(row: dict, label_mode: str, repo: str, explicit: Dict[Tuple[str, str], int]) -> int:
    path = str(row.get("path") or "").strip()
    if label_mode == "labels-file":
        return int(explicit.get((repo, path), 0))

    max_cvss = to_float(str(row.get("max_cvss") or "0"), 0.0)
    high_findings = to_int(str(row.get("high_findings") or "0"), 0)
    if label_mode == "cvss9":
        return 1 if max_cvss >= 9.0 else 0
    if label_mode == "cvss7":
        return 1 if max_cvss >= 7.0 else 0
    if label_mode == "high_any":
        return 1 if high_findings > 0 else 0
    return 0


def build_method_items(repo: str, rows: List[dict], label_mode: str, explicit: Dict[Tuple[str, str], int]) -> Dict[str, List[ScoredItem]]:
    out: Dict[str, List[ScoredItem]] = {
        "full_priority": [],
        "vuln_priority": [],
        "cvss_only": [],
        "llm_only": [],
    }

    for row in rows:
        path = str(row.get("path") or "").strip()
        if not path:
            continue
        rel = label_for_row(row, label_mode, repo, explicit)
        max_cvss = to_float(str(row.get("max_cvss") or "0"), 0.0)
        vuln_findings = to_int(str(row.get("vuln_findings") or "0"), 0)
        llm_score = to_float(str(row.get("llm_score") or "0"), 0.0)
        has_llm = str(row.get("has_llm_coverage") or "").strip().lower() == "true"
        vuln_priority = max_cvss * 10.0 + min(vuln_findings, 10) * 3.0

        out["full_priority"].append(
            ScoredItem(path=path, score=to_float(str(row.get("priority_score") or "0"), 0.0), relevant=rel)
        )
        out["vuln_priority"].append(ScoredItem(path=path, score=vuln_priority, relevant=rel))
        out["cvss_only"].append(ScoredItem(path=path, score=max_cvss, relevant=rel))
        out["llm_only"].append(ScoredItem(path=path, score=(llm_score if has_llm else 0.0), relevant=rel))

    for method in out:
        out[method] = sorted(out[method], key=lambda x: (-x.score, x.path))
    return out


def precision_at_k(items: List[ScoredItem], k: int) -> float:
    if k <= 0:
        return 0.0
    top = items[:k]
    if not top:
        return 0.0
    rel = sum(x.relevant for x in top)
    return rel / float(k)


def recall_at_k(items: List[ScoredItem], k: int, total_rel: int) -> float:
    if total_rel <= 0:
        return 0.0
    rel = sum(x.relevant for x in items[:k])
    return rel / float(total_rel)


def ndcg_at_k(items: List[ScoredItem], k: int) -> float:
    top = items[:k]
    if not top:
        return 0.0
    dcg = 0.0
    for idx, x in enumerate(top, start=1):
        if x.relevant:
            dcg += 1.0 / math.log2(idx + 1)

    rel_total = sum(x.relevant for x in items)
    ideal_hits = min(k, rel_total)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def mrr(items: List[ScoredItem]) -> float:
    for idx, x in enumerate(items, start=1):
        if x.relevant:
            return 1.0 / float(idx)
    return 0.0


def average_precision(items: List[ScoredItem], total_rel: int) -> float:
    if total_rel <= 0:
        return 0.0
    hit_count = 0
    sum_prec = 0.0
    for idx, x in enumerate(items, start=1):
        if x.relevant:
            hit_count += 1
            sum_prec += hit_count / float(idx)
    return sum_prec / float(total_rel)


def classification_metrics(items: List[ScoredItem], total_rel: int) -> Dict[str, float]:
    n = len(items)
    if n == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "accuracy": 0.0}

    m = min(max(total_rel, 0), n)
    pred_positive = {i for i in range(m)}

    tp = fp = tn = fn = 0
    for i, item in enumerate(items):
        pred = 1 if i in pred_positive else 0
        truth = 1 if item.relevant else 0
        if pred == 1 and truth == 1:
            tp += 1
        elif pred == 1 and truth == 0:
            fp += 1
        elif pred == 0 and truth == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / float(tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / float(tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / float(n) if n > 0 else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
    }


def mean_std(vals: List[float]) -> Tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    if len(vals) == 1:
        return vals[0], 0.0
    return statistics.mean(vals), statistics.stdev(vals)


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def format_markdown(
    k_values: List[int],
    label_mode: str,
    per_repo_rows: List[dict],
    macro_rows: List[dict],
) -> str:
    methods = sorted({str(r.get("method") or "") for r in macro_rows})
    lines: List[str] = []
    lines.append("# Metrics Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("")
    lines.append(f"- Label mode: `{label_mode}`")
    lines.append(f"- K values: `{','.join(str(k) for k in k_values)}`")
    lines.append(f"- Repositories evaluated: `{len({str(r.get('repo')) for r in per_repo_rows})}`")
    lines.append("")
    lines.append("## Macro Results")
    lines.append("")
    lines.append("| Method | F1 (mean+-sd) | MAP (mean+-sd) | MRR (mean+-sd) |")
    lines.append("|---|---:|---:|---:|")
    for m in methods:
        row = next((x for x in macro_rows if str(x.get("method")) == m), None)
        if not row:
            continue
        lines.append(
            f"| {m} | {float(row.get('f1_mean', 0.0)):.4f} +- {float(row.get('f1_std', 0.0)):.4f} "
            f"| {float(row.get('map_mean', 0.0)):.4f} +- {float(row.get('map_std', 0.0)):.4f} "
            f"| {float(row.get('mrr_mean', 0.0)):.4f} +- {float(row.get('mrr_std', 0.0)):.4f} |"
        )

    lines.append("")
    lines.append("## Thesis-Ready Text (Draft)")
    lines.append("")
    lines.append(
        "We report repository-level metrics first and aggregate with macro averages across repositories "
        "to reduce size-driven bias. Primary metrics are ranking-oriented (Precision@K, Recall@K, NDCG@K, "
        "MRR, and MAP), while classification metrics (Precision, Recall, F1, Accuracy) are reported secondarily."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    suite_dir = Path(args.suite_dir).expanduser().resolve()
    k_values = parse_k_values(args.k_values)

    explicit_labels: Dict[Tuple[str, str], int] = {}
    if args.label_mode == "labels-file":
        if not args.labels_file:
            raise SystemExit("--labels-file is required when --label-mode labels-file")
        explicit_labels = load_explicit_labels(Path(args.labels_file).expanduser().resolve())

    suite_rows = load_suite_rows(suite_dir)
    if not suite_rows:
        raise SystemExit("No successful repository runs found in suite")

    per_repo_method_rows: List[dict] = []
    metrics_by_method: Dict[str, Dict[str, List[float]]] = {}

    for suite_row in suite_rows:
        repo = str(suite_row.get("slug") or suite_row.get("repo") or "")
        run_dir = Path(str(suite_row.get("run_dir") or "")).expanduser().resolve()
        priorities = read_priorities_csv(run_dir / "prioritization" / "priorities.csv")
        if not priorities:
            continue

        by_method = build_method_items(repo, priorities, args.label_mode, explicit_labels)
        for method, items in by_method.items():
            total_rel = sum(x.relevant for x in items)
            class_m = classification_metrics(items, total_rel)
            row = {
                "repo": repo,
                "method": method,
                "items": len(items),
                "relevant": total_rel,
                "mrr": mrr(items),
                "map": average_precision(items, total_rel),
                "precision": class_m["precision"],
                "recall": class_m["recall"],
                "f1": class_m["f1"],
                "accuracy": class_m["accuracy"],
            }
            for k in k_values:
                row[f"p@{k}"] = precision_at_k(items, k)
                row[f"r@{k}"] = recall_at_k(items, k, total_rel)
                row[f"ndcg@{k}"] = ndcg_at_k(items, k)

            per_repo_method_rows.append(row)

            agg = metrics_by_method.setdefault(method, {})
            for key, value in row.items():
                if key in {"repo", "method"}:
                    continue
                if isinstance(value, (int, float)):
                    agg.setdefault(key, []).append(float(value))

    if not per_repo_method_rows:
        raise SystemExit("No per-repo metrics were computed")

    macro_rows: List[dict] = []
    for method, mvals in sorted(metrics_by_method.items()):
        out = {"method": method}
        for metric_key, vals in sorted(mvals.items()):
            mean_v, std_v = mean_std(vals)
            out[f"{metric_key}_mean"] = mean_v
            out[f"{metric_key}_std"] = std_v
        macro_rows.append(out)

    prefix = args.output_prefix
    per_repo_csv = suite_dir / f"{prefix}_per_repo.csv"
    macro_csv = suite_dir / f"{prefix}_macro.csv"
    md_path = suite_dir / f"{prefix}_summary.md"
    json_path = suite_dir / f"{prefix}.json"

    per_repo_fields = [
        "repo",
        "method",
        "items",
        "relevant",
        *[f"p@{k}" for k in k_values],
        *[f"r@{k}" for k in k_values],
        *[f"ndcg@{k}" for k in k_values],
        "mrr",
        "map",
        "precision",
        "recall",
        "f1",
        "accuracy",
    ]
    write_csv(per_repo_csv, per_repo_method_rows, per_repo_fields)

    macro_fields = ["method"]
    numeric_keys = sorted({k for row in macro_rows for k in row.keys() if k != "method"})
    macro_fields.extend(numeric_keys)
    write_csv(macro_csv, macro_rows, macro_fields)

    md_path.write_text(
        format_markdown(k_values, args.label_mode, per_repo_method_rows, macro_rows),
        encoding="utf-8",
    )

    payload = {
        "suite_dir": str(suite_dir),
        "label_mode": args.label_mode,
        "k_values": k_values,
        "per_repo": per_repo_method_rows,
        "macro": macro_rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Metrics computed")
    print(f"Per-repo CSV: {per_repo_csv}")
    print(f"Macro CSV: {macro_csv}")
    print(f"Summary MD: {md_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
