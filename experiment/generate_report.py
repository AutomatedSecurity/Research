#!/usr/bin/env python3
"""
Generate a self-contained HTML report from pipeline run artifacts.
Usage: python3 generate_report.py <run_dir> [output.html]
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def esc(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "-"


def fmt_float(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "-"


def file_link(path: str | None) -> str:
    if not path:
        return '<span class="muted">not available</span>'
    p = Path(path)
    label = p.name or str(p)
    href = p.resolve().as_uri() if p.exists() else "#"
    extra = "" if p.exists() else ' class="muted"'
    return f'<a href="{esc(href)}"{extra}><code>{esc(label)}</code></a>'


def artifact_list(step_data: dict[str, Any] | None) -> str:
    if not isinstance(step_data, dict) or not step_data:
        return '<li><span class="muted">No artifacts recorded</span></li>'
    items: list[str] = []
    for key, value in step_data.items():
        if isinstance(value, str) and ("/" in value or value.endswith((".json", ".csv", ".md", ".txt"))):
            items.append(f"<li><strong>{esc(key)}</strong>: {file_link(value)}</li>")
        else:
            items.append(f"<li><strong>{esc(key)}</strong>: <code>{esc(value)}</code></li>")
    return "".join(items)


def cvss_class(cvss: float | None) -> str:
    if cvss is None:
        return "cvss-none"
    if cvss >= 9:
        return "cvss-critical"
    if cvss >= 7:
        return "cvss-high"
    if cvss >= 4:
        return "cvss-medium"
    if cvss > 0:
        return "cvss-low"
    return "cvss-none"


def tier_class(tier: str) -> str:
    t = tier.upper()
    if t in ("P0", "P1"):
        return "tier-critical"
    if t == "P2":
        return "tier-high"
    if t == "P3":
        return "tier-medium"
    return "tier-low"


def tier_label(tier: Any) -> str:
    t = str(tier or "").upper()
    labels = {
        "P0": "P0 Immediate",
        "P1": "P1 Critical",
        "P2": "P2 High",
        "P3": "P3 Medium",
        "P4": "P4 Low",
    }
    return labels.get(t, t or "-")


def severity_class(sev: str) -> str:
    s = sev.lower()
    if s == "high":
        return "sev-high"
    if s == "medium":
        return "sev-medium"
    return "sev-low"


def confidence_class(conf: str) -> str:
    c = conf.lower()
    if c == "high":
        return "conf-high"
    if c == "medium":
        return "conf-medium"
    return "conf-low"


def compact_snippet(text: Any, limit: int = 160) -> str:
    raw = str(text or "").replace("\n", " ").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3].rstrip() + "..."


def help_th(label: str, description: str) -> str:
    return (
        f'<th><button class="th-label" type="button" data-tooltip="{esc(description)}">'
        f'<span>{esc(label)}</span><span class="th-help" aria-hidden="true">?</span>'
        f'<span class="tooltip-bubble" role="tooltip">{esc(description)}</span>'
        f"</button></th>"
    )


def details_list(items: list[str]) -> str:
    if not items:
        return '<p class="muted">No additional evidence recorded.</p>'
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def render_cvss_details(score: Any, vector: Any, extra_lines: list[str] | None = None) -> str:
    lines = [] if extra_lines is None else list(extra_lines)
    if vector:
        lines.insert(0, f"<strong>Vector:</strong> <code>{esc(vector)}</code>")
    lines.insert(0, f"<strong>Base score:</strong> {esc(fmt_float(score))}")
    body = details_list(lines)
    return (
        f'<details class="inline-details cvss-details">'
        f'<summary><span class="cvss-pill {cvss_class(score)}">{fmt_float(score)}</span></summary>'
        f'<div class="inline-panel">{body}</div>'
        f"</details>"
    )


def render_target_details(label: str, detail_items: list[str]) -> str:
    return (
        '<details class="inline-details target-details">'
        f'<summary><code>{esc(label)}</code></summary>'
        f'<div class="inline-panel">{details_list(detail_items)}</div>'
        '</details>'
    )


def render_raw_json(value: Any) -> str:
    return esc(json.dumps(value, indent=2, ensure_ascii=False))


def slugify_path(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip("/").lower()).strip("-")
    return slug or "item"


def detail_link(label_html: str, href: str, kind: str) -> str:
    return (
        f'<a class="detail-trigger detail-trigger-{kind}" href="{esc(href)}">{label_html}'
        '<span class="trigger-chevron" aria-hidden="true">›</span></a>'
    )


def build_step_card(
    number: str,
    title: str,
    description: str,
    metrics: list[tuple[str, str]],
    artifacts_html: str,
) -> str:
    metric_html = "".join(
        f'<div class="mini-metric"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div></div>'
        for label, value in metrics
    )
    return f"""
    <section class="panel step-card">
      <div class="step-head">
        <div class="step-number">Step {esc(number)}</div>
        <div>
          <h2>{esc(title)}</h2>
          <p class="muted">{esc(description)}</p>
        </div>
      </div>
      <div class="mini-metrics">{metric_html}</div>
      <details>
        <summary>Generated artifacts</summary>
        <ul class="artifact-list">{artifacts_html}</ul>
      </details>
    </section>
    """


def build_step_chip(
    number: str, title: str, metric: str, detail: str, artifacts_html: str
) -> str:
    return f"""
    <div class="step-chip">
      <div class="step-chip-num">{esc(number)}</div>
      <div class="step-chip-body">
        <div class="step-chip-title">{esc(title)}</div>
        <div class="step-chip-metric">{esc(metric)}</div>
        <div class="step-chip-detail">{esc(detail)}</div>
        <details class="step-chip-details">
          <summary>Artifacts</summary>
          <ul class="artifact-list">{artifacts_html}</ul>
        </details>
      </div>
    </div>
    """


def generate(run_dir: Path) -> tuple[str, dict[str, str]]:
    manifest = load_json(run_dir / "manifest.json") or {}
    vuln = load_json(run_dir / "vulnerabilities" / "summary.json") or {}
    llm = load_json(run_dir / "llm" / "llm_reachability_ranking.json") or {}
    prio = load_json(run_dir / "prioritization" / "summary.json") or {}
    fanin = load_json(run_dir / "fanin" / "summary.json") or {}
    git = load_json(run_dir / "git_history" / "summary.json") or {}

    project = manifest.get("project", "unknown")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    steps = manifest.get("steps", {}) if isinstance(manifest.get("steps"), dict) else {}

    vuln_top_findings = vuln.get("top_findings", []) if isinstance(vuln.get("top_findings"), list) else []
    vuln_top_files = vuln.get("top_files", []) if isinstance(vuln.get("top_files"), list) else []
    llm_targets = llm.get("ranked_targets", []) if isinstance(llm.get("ranked_targets"), list) else []
    prio_rows = prio.get("top_priorities", []) if isinstance(prio.get("top_priorities"), list) else []
    fanin_modules = fanin.get("top_modules", []) if isinstance(fanin.get("top_modules"), list) else []
    git_files = git.get("top_files", []) if isinstance(git.get("top_files"), list) else []

    vuln_count = int(vuln.get("findings_count") or 0)
    llm_count = len(llm_targets)
    prio_count = len(prio_rows)
    fanin_count = int(fanin.get("modules_ranked") or 0)
    git_count = int(git.get("files_ranked") or 0)

    vuln_findings_by_path: dict[str, list[dict[str, Any]]] = {}
    for finding in vuln_top_findings:
        if not isinstance(finding, dict):
            continue
        path = str(finding.get("path") or "").strip()
        if not path:
            continue
        vuln_findings_by_path.setdefault(path, []).append(finding)

    detail_paths: set[str] = set()
    for item in vuln_top_files:
        path = str(item.get("file") or "").strip()
        if path:
            detail_paths.add(path)
    for item in prio_rows:
        path = str(item.get("path") or "").strip()
        if path:
            detail_paths.add(path)
    for item in llm_targets:
        path = str(item.get("target", {}).get("path") or "").strip()
        if path:
            detail_paths.add(path)
    for item in fanin_modules:
        path = str(item.get("module") or "").strip()
        if path:
            detail_paths.add(path)
    for item in git_files:
        path = str(item.get("file") or "").strip()
        if path:
            detail_paths.add(path)

    detail_hrefs = {path: f"details/{slugify_path(path)}.html" for path in sorted(detail_paths)}

    drawer_templates: list[str] = []
    drawer_seq = 0

    def register_drawer(
        summary_html: str,
        title: str,
        subtitle: str,
        body_html: str,
        raw_obj: Any,
        *,
        kind: str,
    ) -> str:
        nonlocal drawer_seq
        drawer_seq += 1
        drawer_id = f"drawer-{drawer_seq}"
        raw_section = ""
        if raw_obj is not None:
            raw_section = (
                '<details class="raw-json"><summary>Raw JSON</summary>'
                f'<pre>{render_raw_json(raw_obj)}</pre></details>'
            )
        drawer_templates.append(
            f'''<template id="{drawer_id}">
                <div class="drawer-fragment">
                  <div class="drawer-heading">
                    <div class="eyebrow">Evidence View</div>
                    <h3>{esc(title)}</h3>
                    <p class="drawer-subtitle">{esc(subtitle)}</p>
                  </div>
                  <div class="drawer-rich">{body_html}</div>
                  {raw_section}
                </div>
            </template>'''
        )
        return (
            f'<button class="detail-trigger detail-trigger-{kind}" type="button" '
            f'data-drawer-target="{drawer_id}">{summary_html}'
            '<span class="trigger-chevron" aria-hidden="true">›</span></button>'
        )

    # Before vs after comparison rows.
    before_after_rows: list[str] = []
    sorted_vuln_top_files = sorted(
        vuln_top_files,
        key=lambda item: (
            -float(item.get("max_cvss") or 0.0),
            -int(item.get("findings") or 0),
            -int(item.get("risk_score") or 0),
            str(item.get("file") or ""),
        ),
    )
    baseline_by_path = {
        str(item.get("file") or "").strip(): {"baseline_rank": idx, **item}
        for idx, item in enumerate(sorted_vuln_top_files, start=1)
        if str(item.get("file") or "").strip()
    }

    before_candidates: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(sorted_vuln_top_files, start=1):
        path = str(item.get("file") or "").strip()
        if path:
            before_candidates[path] = {
                "baseline_rank": idx,
                "findings": item.get("findings"),
                "risk_score": item.get("risk_score"),
                "max_cvss": item.get("max_cvss"),
            }
    for item in prio_rows:
        path = str(item.get("path") or "").strip()
        if path and path not in before_candidates:
            before_candidates[path] = {
                "baseline_rank": None,
                "findings": item.get("vuln_findings"),
                "risk_score": None,
                "max_cvss": item.get("max_cvss"),
            }

    prio_by_path = {str(item.get("path") or ""): item for item in prio_rows}
    llm_by_path = {str(item.get("target", {}).get("path") or ""): item for item in llm_targets}

    ordered_paths = sorted(
        before_candidates.keys(),
        key=lambda path: (
            before_candidates[path].get("baseline_rank") is None,
            before_candidates[path].get("baseline_rank") or 9999,
            prio_by_path.get(path, {}).get("rank") or 9999,
            path,
        ),
    )

    for path in ordered_paths[:20]:
        base = before_candidates[path]
        final = prio_by_path.get(path, {})
        llm_item = llm_by_path.get(path, {})
        final_rank = final.get("rank")
        baseline_rank = base.get("baseline_rank")
        rank_delta = "new"
        if isinstance(baseline_rank, int) and isinstance(final_rank, int):
            delta = baseline_rank - final_rank
            rank_delta = f"{delta:+d}"
        elif isinstance(final_rank, int):
            rank_delta = "added"
        before_after_rows.append(
            f"""<tr>
              <td><code>{esc(path)}</code></td>
              <td>{esc(baseline_rank if baseline_rank is not None else '-')}</td>
              <td><span class=\"cvss-pill {cvss_class(base.get('max_cvss'))}\">{fmt_float(base.get('max_cvss'))}</span></td>
              <td>{fmt_int(base.get('findings'))}</td>
              <td>{esc(llm_item.get('rank', '-'))}</td>
              <td>{fmt_float(llm_item.get('score'), 0)}</td>
              <td>{esc(final_rank if final_rank is not None else '-')}</td>
              <td>{fmt_float(final.get('priority_score'))}</td>
              <td>{esc(rank_delta)}</td>
            </tr>"""
        )

    # Baseline pane rows.
    baseline_row_parts: list[str] = []
    for idx, item in enumerate(sorted_vuln_top_files[:10], start=1):
        file_path = str(item.get("file", "?"))
        matched_findings = vuln_findings_by_path.get(file_path, [])[:8]
        href = detail_hrefs.get(file_path, "#")
        target_button = detail_link(f"<code>{esc(file_path)}</code>", href, "target")
        cvss_button = detail_link(
            f'<span class="cvss-pill {cvss_class(item.get("max_cvss"))}">{fmt_float(item.get("max_cvss"))}</span>',
            href + "#vulnerability-evidence",
            "cvss",
        )
        baseline_row_parts.append(
            f"""<tr>
          <td>{idx}</td>
          <td>{target_button}</td>
          <td>{fmt_int(item.get('findings'))}</td>
          <td>{fmt_int(item.get('risk_score'))}</td>
          <td>{cvss_button}</td>
        </tr>"""
        )
    baseline_rows = "".join(baseline_row_parts)

    # Final pane rows.
    final_row_parts: list[str] = []
    for item in prio_rows[:10]:
        baseline_match = next(
            (
                baseline
                for baseline in sorted_vuln_top_files
                if str(baseline.get("file") or "") == str(item.get("path") or "")
            ),
            None,
        )
        baseline_rank = (
            sorted_vuln_top_files.index(baseline_match) + 1 if baseline_match in sorted_vuln_top_files else None
        )
        path = str(item.get("path", "?"))
        href = detail_hrefs.get(path, "#")
        target_button = detail_link(f"<code>{esc(path)}</code>", href, "target")
        cvss_button = detail_link(
            f'<span class="cvss-pill {cvss_class(item.get("max_cvss"))}">{fmt_float(item.get("max_cvss"))}</span>',
            href + "#vulnerability-evidence",
            "cvss",
        )
        final_row_parts.append(
            f"""<tr>
          <td>{fmt_int(item.get('rank'))}</td>
          <td>{target_button}</td>
          <td>{fmt_float(item.get('priority_score'))}</td>
          <td>{fmt_float(item.get('llm_score'), 0)}</td>
          <td>{cvss_button}</td>
        </tr>"""
        )
    final_rows = "".join(final_row_parts)

    # Detailed tables.
    vuln_findings_parts: list[str] = []
    for item in vuln_top_findings[:25]:
        path = str(item.get("path", "?"))
        href = detail_hrefs.get(path, "#")
        target_button = detail_link(f"<code>{esc(path)}</code>", href, "target")
        cvss_button = detail_link(
            f'<span class="cvss-pill {cvss_class(item.get("cvss_base"))}">{fmt_float(item.get("cvss_base"))}</span>',
            href + "#vulnerability-evidence",
            "cvss",
        )
        vuln_findings_parts.append(
            f"""<tr>
          <td>{fmt_int(item.get('rank'))}</td>
          <td>{target_button}</td>
          <td>{fmt_int(item.get('line'))}</td>
          <td><span class="sev-pill {severity_class(str(item.get('severity', '')))}">{esc(item.get('severity', '?'))}</span></td>
          <td>{cvss_button}</td>
          <td><code>{esc(item.get('rule_id', '?'))}</code></td>
          <td class="desc-cell">{esc(compact_snippet(item.get('description')))}</td>
        </tr>"""
        )
    vuln_findings_rows = "".join(vuln_findings_parts)

    llm_rows = "".join(
        f"""<tr>
          <td>{fmt_int(item.get('rank'))}</td>
          <td>{detail_link(f'<code>{esc(str(item.get("target", {}).get("path", "?")))}</code>', detail_hrefs.get(str(item.get('target', {}).get('path', '?')), '#'), 'target')}</td>
          <td>{fmt_float(item.get('score'), 0)}</td>
          <td><span class="conf-pill {confidence_class(str(item.get('confidence', '')))}">{esc(item.get('confidence', '?'))}</span></td>
          <td>{esc(item.get('signals', {}).get('entrypoint_exposure', '-'))}</td>
          <td>{esc(item.get('signals', {}).get('fanin_signal', '-'))}</td>
          <td>{esc(item.get('signals', {}).get('git_activity_signal', '-'))}</td>
          <td>{esc(item.get('signals', {}).get('business_criticality', '-'))}</td>
          <td class="desc-cell">{esc(compact_snippet(item.get('why')))}</td>
        </tr>"""
        for item in llm_targets[:25]
    )

    prioritization_parts: list[str] = []
    for item in prio_rows[:25]:
        path = str(item.get("path", "?"))
        href = detail_hrefs.get(path, "#")
        target_button = detail_link(f"<code>{esc(path)}</code>", href, "target")
        cvss_button = detail_link(
            f'<span class="cvss-pill {cvss_class(item.get("max_cvss"))}">{fmt_float(item.get("max_cvss"))}</span>',
            href + "#vulnerability-evidence",
            "cvss",
        )
        prioritization_parts.append(
            f"""<tr>
          <td>{fmt_int(item.get('rank'))}</td>
          <td>{target_button}</td>
          <td><span class="tier-pill {tier_class(str(item.get('priority_tier') or ''))}" title="Priority band, not a unique rank">{esc(tier_label(item.get('priority_tier')))}</span></td>
          <td>{fmt_float(item.get('priority_score'))}</td>
          <td>{fmt_float(item.get('llm_score'), 0)}</td>
          <td>{esc(item.get('llm_rank') if isinstance(item.get('llm_rank'), int) else '-')}</td>
          <td>{cvss_button}</td>
          <td>{fmt_int(item.get('vuln_findings'))}</td>
          <td>{fmt_int(item.get('fan_in'))}</td>
          <td>{fmt_int(item.get('git_commits_touched'))}</td>
          <td class="desc-cell">{esc(compact_snippet(item.get('why')))}</td>
        </tr>"""
        )
    prioritization_rows = "".join(prioritization_parts)

    fanin_rows = "".join(
        f"""<tr>
          <td>{fmt_int(item.get('rank'))}</td>
          <td><code>{esc(item.get('module', '?'))}</code></td>
          <td>{fmt_int(item.get('fan_in'))}</td>
          <td class="desc-cell">{esc(', '.join(item.get('entrypoints_reaching', [])[:6]))}</td>
        </tr>"""
        for item in fanin_modules[:15]
    )

    git_rows = "".join(
        f"""<tr>
          <td>{fmt_int(item.get('rank'))}</td>
          <td><code>{esc(item.get('file', '?'))}</code></td>
          <td>{fmt_int(item.get('commits_touched'))}</td>
          <td>{fmt_int(item.get('total_added'))}</td>
          <td>{fmt_int(item.get('total_deleted'))}</td>
          <td>{fmt_int(item.get('churn'))}</td>
        </tr>"""
        for item in git_files[:15]
    )

    llm_observations = llm.get("global_observations", []) if isinstance(llm.get("global_observations"), list) else []
    llm_limitations = llm.get("limitations", []) if isinstance(llm.get("limitations"), list) else []

    baseline_file_count = len(vuln_top_files)
    suspicious_prio_rows = [
        item
        for item in prio_rows
        if float(item.get("max_cvss") or 0.0) <= 0.0
        or int(item.get("vuln_findings") or 0) <= 0
    ]
    consistency_notes: list[str] = []
    if suspicious_prio_rows:
        consistency_notes.append(
            "Final prioritization contains rows without vulnerability-backed evidence. This usually means the prioritization artifact was generated with an older algorithm or stale run outputs."
        )
    if baseline_file_count and prio_count and baseline_file_count != prio_count:
        consistency_notes.append(
            f"Baseline vulnerability files: {baseline_file_count}. Final prioritized rows: {prio_count}. A mismatch can be valid in older runs, but current RiskRank behavior is to keep only vulnerability-backed rows in final prioritization."
        )
    consistency_html = ""
    if consistency_notes:
        consistency_html = (
            '<section class="panel warning-panel"><h2>Consistency Check</h2><ul>'
            + "".join(f"<li>{esc(note)}</li>" for note in consistency_notes)
            + "</ul></section>"
        )

    detail_pages: dict[str, str] = {}

    for path in sorted(detail_paths):
        baseline = baseline_by_path.get(path)
        prio = prio_by_path.get(path)
        llm_item = llm_by_path.get(path)
        fanin_item = next((item for item in fanin_modules if str(item.get("module") or "") == path), None)
        git_item = next((item for item in git_files if str(item.get("file") or "") == path), None)
        findings = vuln_findings_by_path.get(path, [])

        summary_cards = [
            ("Baseline Rank", esc(baseline.get("baseline_rank") if baseline else "-")),
            ("Baseline Max CVSS", fmt_float(baseline.get("max_cvss") if baseline else None)),
            ("Final Rank", esc(prio.get("rank") if prio else "-")),
            ("Priority Score", fmt_float(prio.get("priority_score") if prio else None)),
            ("LLM Score", fmt_float((prio or {}).get("llm_score") or (llm_item or {}).get("score"), 0)),
            ("Vuln Findings", fmt_int((prio or {}).get("vuln_findings") or (baseline or {}).get("findings"))),
            ("Fan-in", fmt_int((prio or {}).get("fan_in") or (fanin_item or {}).get("fan_in"))),
            ("Git Commits", fmt_int((prio or {}).get("git_commits_touched") or (git_item or {}).get("commits_touched"))),
        ]
        summary_cards_html = "".join(
            f'<div class="metric-card"><div class="label">{label}</div><div class="value">{value}</div></div>'
            for label, value in summary_cards
        )

        baseline_block = (
            '<div class="detail-block"><h3>Before LLM Prioritization</h3>'
            + (
                "<ul>"
                + f"<li><strong>Rank:</strong> {esc(baseline.get('baseline_rank'))}</li>"
                + f"<li><strong>Findings:</strong> {fmt_int(baseline.get('findings'))}</li>"
                + f"<li><strong>Risk score:</strong> {fmt_int(baseline.get('risk_score'))}</li>"
                + f"<li><strong>Max CVSS:</strong> {fmt_float(baseline.get('max_cvss'))}</li>"
                + "</ul>"
                if baseline
                else '<p class="muted">No baseline vulnerability ranking for this path.</p>'
            )
            + '</div>'
        )
        after_block = (
            '<div class="detail-block"><h3>After RiskRank Prioritization</h3>'
            + (
                "<ul>"
                + f"<li><strong>Final rank:</strong> {esc(prio.get('rank'))}</li>"
                + f"<li><strong>Priority score:</strong> {fmt_float(prio.get('priority_score'))}</li>"
                + f"<li><strong>Priority band:</strong> {esc(tier_label(prio.get('priority_tier')))}</li>"
                + f"<li><strong>LLM score:</strong> {fmt_float(prio.get('llm_score'), 0)}</li>"
                + f"<li><strong>Why:</strong> {esc(prio.get('why'))}</li>"
                + "</ul>"
                if prio
                else '<p class="muted">This path did not make the final prioritized review list.</p>'
            )
            + '</div>'
        )

        finding_rows = "".join(
            f"<tr><td>{fmt_int(idx)}</td><td>{fmt_int(f.get('line'))}</td><td><code>{esc(f.get('rule_id', '?'))}</code></td><td>{esc(f.get('severity', '?'))}</td><td>{fmt_float(f.get('cvss_base'))}</td><td>{esc(f.get('description'))}</td></tr>"
            for idx, f in enumerate(findings, start=1)
        )
        findings_section = (
            '<section class="panel" id="vulnerability-evidence"><h2>Vulnerability Evidence</h2>'
            + (
                '<div class="table-wrap"><table><thead><tr><th>#</th><th>Line</th><th>Rule</th><th>Severity</th><th>CVSS</th><th>Description</th></tr></thead><tbody>'
                + finding_rows
                + '</tbody></table></div>'
                + '<details class="raw-json"><summary>Raw findings JSON</summary><pre>'
                + render_raw_json(findings)
                + '</pre></details>'
                if findings
                else '<p class="muted">No raw vulnerability findings recorded for this path.</p>'
            )
            + '</section>'
        )

        llm_section = (
            '<section class="panel"><h2>LLM Reachability Context</h2>'
            + (
                '<ul>'
                + f"<li><strong>Rank:</strong> {esc(llm_item.get('rank'))}</li>"
                + f"<li><strong>Score:</strong> {fmt_float(llm_item.get('score'), 0)}</li>"
                + f"<li><strong>Confidence:</strong> {esc(llm_item.get('confidence', '-'))}</li>"
                + f"<li><strong>Why:</strong> {esc(llm_item.get('why', '-'))}</li>"
                + '</ul>'
                + '<details class="raw-json"><summary>Raw LLM JSON</summary><pre>'
                + render_raw_json(llm_item)
                + '</pre></details>'
                if llm_item
                else '<p class="muted">No LLM reachability ranking recorded for this path.</p>'
            )
            + '</section>'
        )

        structural_section = (
            '<section class="panel"><h2>Structural and History Signals</h2><div class="two-up">'
            + '<div class="detail-block"><h3>Fan-in</h3>'
            + (
                '<ul>'
                + f"<li><strong>Rank:</strong> {fmt_int(fanin_item.get('rank'))}</li>"
                + f"<li><strong>Fan-in:</strong> {fmt_int(fanin_item.get('fan_in'))}</li>"
                + f"<li><strong>Reached by:</strong> {esc(', '.join(fanin_item.get('entrypoints_reaching', [])[:8]))}</li>"
                + '</ul>'
                if fanin_item
                else '<p class="muted">No fan-in record for this path.</p>'
            )
            + '</div>'
            + '<div class="detail-block"><h3>Git History</h3>'
            + (
                '<ul>'
                + f"<li><strong>Rank:</strong> {fmt_int(git_item.get('rank'))}</li>"
                + f"<li><strong>Commits touched:</strong> {fmt_int(git_item.get('commits_touched'))}</li>"
                + f"<li><strong>Added:</strong> {fmt_int(git_item.get('total_added'))}</li>"
                + f"<li><strong>Deleted:</strong> {fmt_int(git_item.get('total_deleted'))}</li>"
                + f"<li><strong>Churn:</strong> {fmt_int(git_item.get('churn'))}</li>"
                + '</ul>'
                if git_item
                else '<p class="muted">No git-history record for this path.</p>'
            )
            + '</div></div></section>'
        )

        related_section = (
            '<section class="panel"><h2>Related Raw Objects</h2>'
            + '<details class="raw-json"><summary>Baseline summary JSON</summary><pre>'
            + render_raw_json(baseline)
            + '</pre></details>'
            + '<details class="raw-json"><summary>Final prioritization JSON</summary><pre>'
            + render_raw_json(prio)
            + '</pre></details>'
            + '<details class="raw-json"><summary>Fan-in JSON</summary><pre>'
            + render_raw_json(fanin_item)
            + '</pre></details>'
            + '<details class="raw-json"><summary>Git JSON</summary><pre>'
            + render_raw_json(git_item)
            + '</pre></details>'
            + '</section>'
        )

        detail_pages[path] = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{esc(path)} - RiskRank Detail</title>
<style>
body{{font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;background:#f5efe4;color:#182327;line-height:1.5;padding:24px}} .container{{max-width:1200px;margin:0 auto}} .panel{{background:rgba(255,252,248,.96);border:1px solid #d8c7af;border-radius:16px;padding:20px;margin-bottom:16px;box-shadow:0 12px 30px rgba(83,52,20,.08)}} h1,h2,h3{{font-family:"Source Serif 4",Georgia,serif}} h1{{font-size:2.2rem;margin-bottom:6px}} h2{{font-size:1.25rem;color:#2f6c60;margin-bottom:10px}} .muted{{color:#655647}} .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}} .metric-card{{border:1px solid #ddccb8;border-radius:12px;padding:12px;background:#fffdf9}} .metric-card .label{{font-size:11px;text-transform:uppercase;color:#655647}} .metric-card .value{{font-size:1.35rem;font-weight:700}} .two-up{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}} .detail-block{{border:1px solid #dfd0bf;border-radius:12px;padding:14px;background:#fffdf9}} table{{width:100%;border-collapse:collapse;font-size:.88rem}} th,td{{padding:10px 8px;border-bottom:1px solid #e7d8c7;text-align:left;vertical-align:top}} th{{background:#f4ece1;font-size:11px;text-transform:uppercase;color:#655647}} code{{background:rgba(0,0,0,.04);padding:1px 5px;border-radius:4px}} .back{{display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:#2f6c60;font-weight:700;margin-bottom:10px}} .raw-json pre{{margin-top:10px;padding:12px;border-radius:12px;background:#1a2429;color:#f8f2e8;overflow:auto;white-space:pre-wrap;word-break:break-word;font-size:12px}} @media(max-width:960px){{body{{padding:12px}} .two-up{{grid-template-columns:1fr}}}}
</style></head><body><div class="container">
<section class="panel"><a class="back" href="../report.html">‹ Back to main report</a><h1>{esc(path)}</h1><p class="muted">Full file dashboard with baseline vulnerability context, final prioritization state, reachability signals, and raw evidence.</p><div class="metrics">{summary_cards_html}</div></section>
<section class="panel"><h2>Before vs After</h2><div class="two-up">{baseline_block}{after_block}</div></section>
{findings_section}
{llm_section}
{structural_section}
{related_section}
</div></body></html>'''

    summary_steps = "".join(
        [
            build_step_chip(
                "1",
                "Fan-in",
                f"{fmt_int(fanin_count)} modules",
                "Structural reachability",
                artifact_list(steps.get("fanin") if isinstance(steps, dict) else None),
            ),
            build_step_chip(
                "2",
                "Git",
                f"{fmt_int(git_count)} files",
                "Change hot spots",
                artifact_list(steps.get("git_history") if isinstance(steps, dict) else None),
            ),
            build_step_chip(
                "3",
                "Vulns",
                f"{fmt_int(vuln_count)} findings",
                str(vuln.get("engine") or "Scanner baseline"),
                artifact_list(steps.get("vulnerabilities") if isinstance(steps, dict) else None),
            ),
            build_step_chip(
                "4",
                "LLM",
                f"{fmt_int(llm_count)} targets",
                str(llm.get("method", {}).get("model") or "Semantic ranking"),
                artifact_list(steps.get("llm") if isinstance(steps, dict) else None),
            ),
            build_step_chip(
                "5",
                "Priority",
                f"{fmt_int(prio_count)} rows",
                "Final review order",
                artifact_list(steps.get("prioritization") if isinstance(steps, dict) else None),
            ),
        ]
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RiskRank Report - {esc(project)}</title>
<style>
:root {{
  --bg: #f5efe4;
  --panel: rgba(255, 252, 248, 0.95);
  --border: #d8c7af;
  --text: #182327;
  --text-dim: #655647;
  --accent: #2f6c60;
  --accent-soft: #dff1eb;
  --ink-soft: #f3ede3;
  --critical: #c0392b;
  --high: #d35400;
  --medium: #e67e22;
  --low: #7f8c8d;
  --tier-p0: #c0392b;
  --tier-p1: #d35400;
  --tier-p2: #e67e22;
  --tier-p3: #7f8c8d;
  --shadow: 0 12px 30px rgba(83, 52, 20, 0.08);
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  background: radial-gradient(circle at 10% 0%, rgba(219,193,149,0.38), transparent 34%),
              radial-gradient(circle at 100% 10%, rgba(115,161,149,0.28), transparent 28%),
              linear-gradient(180deg, #f9f4eb 0%, #f5efe4 100%);
  color: var(--text);
  line-height: 1.5;
  padding: 24px;
}}
.container {{ max-width: 1500px; margin: 0 auto; }}
h1, h2, h3 {{ font-family: "Source Serif 4", Georgia, serif; letter-spacing: 0.2px; }}
h1 {{ font-size: 2.4rem; margin-bottom: 6px; }}
h2 {{ font-size: 1.28rem; margin-bottom: 10px; color: var(--accent); }}
h3 {{ font-size: 1rem; margin-bottom: 8px; }}
.muted {{ color: var(--text-dim); }}
.lede {{ color: var(--text-dim); max-width: 900px; margin-bottom: 18px; }}
.panel {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
}}
.hero {{ padding: 28px; position: relative; overflow: hidden; }}
.hero::before {{
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.26), rgba(255,255,255,0));
  pointer-events: none;
}}
.eyebrow {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.72rem;
  color: var(--accent);
  font-weight: 700;
  margin-bottom: 10px;
}}
.eyebrow::before {{
  content: "";
  width: 30px;
  height: 1px;
  background: currentColor;
}}
.meta {{ color: var(--text-dim); font-size: 0.95rem; margin-top: 6px; }}
.quicknav {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 18px; }}
.quicknav a {{
  text-decoration: none;
  color: var(--text);
  border: 1px solid var(--border);
  background: #fffdf9;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 0.9rem;
}}
.quicknav a:hover {{ background: #eef6f0; border-color: #b9cfbf; }}
.quicknav a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}}
.metric-card, .mini-metric {{
  border: 1px solid #ddccb8;
  border-radius: 12px;
  padding: 12px;
  background: #fffdf9;
}}
.metric-card .label, .mini-metric .label {{
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.metric-card .value, .mini-metric .value {{
  font-size: 1.4rem;
  font-weight: 700;
  margin-top: 2px;
}}
.metric-card {{ position: relative; overflow: hidden; }}
.metric-card::after {{
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 3px;
  background: linear-gradient(90deg, rgba(47,108,96,0.18), rgba(47,108,96,0.68));
}}
.summary-panel {{ padding: 18px 20px; }}
.summary-top {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}
.summary-copy p {{ color: var(--text-dim); max-width: 760px; }}
.summary-copy h2 {{ margin-bottom: 6px; }}
.summary-steps {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}}
.step-chip {{
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  border: 1px solid #dfd0bf;
  border-radius: 12px;
  background: #fffdf9;
}}
.step-chip-num {{
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: #eef6f0;
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.82rem;
  font-weight: 700;
}}
.step-chip-title {{ font-weight: 700; color: var(--text); }}
.step-chip-metric {{ font-size: 0.92rem; color: var(--accent); }}
.step-chip-detail {{ font-size: 0.82rem; color: var(--text-dim); }}
.step-chip-details {{ margin-top: 8px; }}
.step-chip-details summary {{
  cursor: pointer;
  color: var(--accent);
  font-size: 0.82rem;
  font-weight: 600;
}}
.step-chip-details .artifact-list {{ margin-top: 8px; margin-bottom: 0; }}
.two-up {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}}
.comparison-tag {{
  display: inline-block;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  margin-bottom: 10px;
}}
.tag-before {{ background: #fef3e2; color: var(--high); }}
.tag-after {{ background: #eef6f0; color: #2d6a4f; }}
.split-caption {{ margin-bottom: 12px; color: var(--text-dim); font-size: 0.92rem; }}
.comparison-pane-before {{ background: linear-gradient(180deg, rgba(254,243,226,0.78), rgba(255,252,248,0.94)); }}
.comparison-pane-after {{ background: linear-gradient(180deg, rgba(238,246,240,0.82), rgba(255,252,248,0.94)); }}
.comparison-pane-before, .comparison-pane-after {{ position: relative; }}
.comparison-pane-before::before, .comparison-pane-after::before {{
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 16px;
  pointer-events: none;
}}
.comparison-pane-before::before {{ box-shadow: inset 0 0 0 1px rgba(211,122,38,0.12); }}
.comparison-pane-after::before {{ box-shadow: inset 0 0 0 1px rgba(47,108,96,0.14); }}
.legend-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 14px;
  margin-bottom: 14px;
}}
.legend-card {{
  border: 1px solid #ddccb8;
  border-radius: 12px;
  padding: 12px;
  background: #fffdf9;
}}
.legend-card h3 {{ font-size: 0.95rem; margin-bottom: 8px; }}
.legend-card p, .legend-card li {{ color: var(--text-dim); font-size: 0.9rem; }}
.legend-inline {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
thead th {{
  background: #f4ece1;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--text-dim);
  padding: 10px 8px;
  text-align: left;
  border-bottom: 2px solid #ddccb8;
  position: sticky;
  top: 0;
}}
.th-label {{
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: help;
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  border-bottom: 1px dotted #b89e84;
  color: inherit;
  font: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
}}
.th-help {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #e6d8c7;
  color: #6b5b4a;
  font-size: 10px;
  font-weight: 700;
}}
.tooltip-bubble {{
  position: absolute;
  left: 0;
  top: auto;
  bottom: calc(100% + 10px);
  z-index: 30;
  width: min(280px, 45vw);
  padding: 10px 12px;
  border-radius: 10px;
  background: #182327;
  color: #f6f1e8;
  font-size: 12px;
  line-height: 1.45;
  text-transform: none;
  letter-spacing: normal;
  text-align: left;
  box-shadow: 0 14px 24px rgba(24,35,39,0.28);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  transition: opacity 140ms ease, transform 140ms ease;
}}
.tooltip-bubble::before {{
  content: "";
  position: absolute;
  left: 14px;
  top: auto;
  bottom: -6px;
  width: 12px;
  height: 12px;
  background: #182327;
  transform: rotate(45deg);
}}
.th-label:hover .tooltip-bubble,
.th-label:focus-visible .tooltip-bubble,
.th-label:active .tooltip-bubble {{
  opacity: 1;
  transform: translateY(0);
}}
.th-label:focus-visible {{ outline: 2px solid rgba(47,108,96,0.3); outline-offset: 4px; }}
tbody td {{
  padding: 8px;
  border-bottom: 1px solid #e7d8c7;
  vertical-align: top;
}}
tbody tr:hover {{ background: rgba(170,191,185,0.1); }}
.table-wrap {{ overflow: auto; margin-top: 10px; }}
.comparison-table-wrap {{ overflow: visible; }}
.comparison-table {{ table-layout: fixed; width: 100%; }}
.comparison-table th,
.comparison-table td {{ font-size: 0.8rem; }}
.comparison-table th:nth-child(1),
.comparison-table td:nth-child(1) {{ width: 10%; }}
.comparison-table th:nth-child(2),
.comparison-table td:nth-child(2) {{ width: 42%; }}
.comparison-table .detail-trigger {{ align-items: flex-start; white-space: normal; }}
.comparison-table .detail-trigger code {{ white-space: normal; word-break: break-word; }}
.comparison-table .trigger-chevron {{ margin-top: 2px; }}
.desc-cell {{ max-width: 340px; font-size: 0.92em; color: #364348; }}
.detail-trigger {{
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}}
.detail-trigger:hover .trigger-chevron,
.detail-trigger:focus-visible .trigger-chevron {{ transform: translateX(2px); color: var(--accent); }}
.detail-trigger:focus-visible {{ outline: 2px solid rgba(47,108,96,0.22); outline-offset: 4px; border-radius: 8px; }}
.detail-trigger code, .detail-trigger .cvss-pill {{ cursor: pointer; }}
.trigger-chevron {{
  flex: 0 0 auto;
  color: #9b846d;
  font-size: 18px;
  line-height: 1;
  transition: transform 140ms ease, color 140ms ease;
}}
.row-active td {{ background: rgba(223,241,235,0.42); }}
.drawer-shell[hidden] {{ display: none; }}
.drawer-shell {{ position: fixed; inset: 0; z-index: 1000; }}
.drawer-backdrop {{ position: absolute; inset: 0; background: rgba(24,35,39,0.38); backdrop-filter: blur(3px); }}
.drawer-panel {{
  position: absolute;
  top: 0;
  right: 0;
  width: min(620px, 92vw);
  height: 100%;
  background: linear-gradient(180deg, #fffdf9, #f7f1e8);
  border-left: 1px solid #d8c7af;
  box-shadow: -18px 0 40px rgba(24,35,39,0.18);
  display: flex;
  flex-direction: column;
}}
.drawer-topbar {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 22px 22px 12px;
  border-bottom: 1px solid #e3d6c7;
}}
.drawer-topbar h3 {{ font-size: 1.35rem; margin-bottom: 6px; }}
.drawer-subtitle {{ color: var(--text-dim); font-size: 0.92rem; }}
.drawer-close {{
  flex: 0 0 auto;
  border: 0;
  background: #efe3d4;
  color: var(--text);
  width: 36px;
  height: 36px;
  border-radius: 999px;
  font-size: 20px;
  cursor: pointer;
}}
.drawer-close:hover, .drawer-close:focus-visible {{ background: #e5d5c2; outline: none; }}
.drawer-body {{ padding: 18px 22px 28px; overflow: auto; }}
.drawer-rich ul {{ margin-top: 0; }}
.drawer-rich li {{ margin-bottom: 8px; }}
.drawer-rich code {{ white-space: pre-wrap; }}
.raw-json {{ margin-top: 18px; }}
.raw-json pre {{
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: #1a2429;
  color: #f8f2e8;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}}
code {{
  background: rgba(0,0,0,0.04);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.92em;
}}
details {{ margin: 4px 0; }}
summary {{
  cursor: pointer;
  font-weight: 600;
  color: var(--accent);
  font-size: 0.9rem;
  padding: 4px 0;
}}
ul {{ margin: 8px 0 4px 20px; }}
li {{ margin-bottom: 4px; }}
.pill, .sev-pill, .cvss-pill, .tier-pill, .conf-pill {{
  display: inline-block;
  min-width: 44px;
  text-align: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
}}
.sev-high {{ background: #fde8e0; color: var(--critical); }}
.sev-medium {{ background: #fef3e2; color: var(--medium); }}
.sev-low {{ background: #f0f0f0; color: var(--low); }}
.cvss-critical {{ background: #fde8e0; color: var(--critical); }}
.cvss-high {{ background: #fde8e0; color: var(--high); }}
.cvss-medium {{ background: #fef3e2; color: var(--medium); }}
.cvss-low {{ background: #eef6f0; color: var(--accent); }}
.cvss-none {{ background: #f0f0f0; color: var(--low); }}
.tier-critical {{ background: #fde8e0; color: var(--tier-p0); }}
.tier-high {{ background: #fde8e0; color: var(--tier-p1); }}
.tier-medium {{ background: #fef3e2; color: var(--tier-p2); }}
.tier-low {{ background: #f0f0f0; color: var(--tier-p3); }}
.conf-high {{ background: #eef6f0; color: #2d6a4f; }}
.conf-medium {{ background: #fef9e7; color: #936d29; }}
.conf-low {{ background: #f0f0f0; color: var(--low); }}
.callout {{
  border-left: 4px solid var(--accent);
  background: #fffdf9;
  padding: 12px 14px;
  border-radius: 10px;
  color: var(--text-dim);
}}
.comparison-callout {{ margin-top: 14px; }}
.warning-panel {{
  border-color: #e6c8a4;
  background: linear-gradient(180deg, rgba(255,247,236,0.95), rgba(255,252,248,0.95));
}}
.warning-panel h2 {{ color: #9a5d10; }}
section {{ scroll-margin-top: 16px; }}
footer {{ margin-top: 24px; font-size: 0.82rem; color: #9a8d7f; text-align: center; }}
@media (max-width: 960px) {{
  body {{ padding: 12px; }}
  .two-up {{ grid-template-columns: 1fr; }}
  table {{ font-size: 0.8rem; }}
  .comparison-table th:nth-child(2),
  .comparison-table td:nth-child(2) {{ width: auto; }}
  .tooltip-bubble {{ width: min(220px, 72vw); }}
}}
</style>
</head>
<body>
<div class="container">

<section class="panel hero">
  <div class="eyebrow">Security Review Decision Support</div>
  <h1>RiskRank Report</h1>
  <p class="lede">This report shows the full pipeline end-to-end: structural ranking, git activity, vulnerability findings, LLM reachability analysis, and the final merged prioritization. It is designed for demos and user studies, so each step exposes both its outputs and how later stages changed the ranking.</p>
  <p class="meta">
    <strong>Project:</strong> <code>{esc(project)}</code> &nbsp;|&nbsp;
    <strong>Run directory:</strong> <code>{esc(run_dir)}</code> &nbsp;|&nbsp;
    <strong>Generated:</strong> {generated_at}
  </p>
  <div class="quicknav">
    <a href="#comparison">Before / After</a>
    <a href="#rank-shifts">Rank Shifts</a>
    <a href="#final-prioritization-detail">Final Detail</a>
    <a href="#vuln-detail">Vulnerability Detail</a>
  </div>
</section>

<section class="panel summary-panel">
  <div class="summary-top">
    <div class="summary-copy">
      <h2>Summary</h2>
      <p>RiskRank starts with structural and vulnerability evidence, adds LLM reachability context, and ends with a tighter final review order. The snapshot and pipeline below give the full run context without forcing you to scroll through a large explainer section.</p>
      <div class="metrics">
        <div class="metric-card"><div class="label">Fan-in modules</div><div class="value">{fmt_int(fanin_count)}</div></div>
        <div class="metric-card"><div class="label">Git-ranked files</div><div class="value">{fmt_int(git_count)}</div></div>
        <div class="metric-card"><div class="label">Vulnerability findings</div><div class="value">{fmt_int(vuln_count)}</div></div>
        <div class="metric-card"><div class="label">LLM targets</div><div class="value">{fmt_int(llm_count)}</div></div>
        <div class="metric-card"><div class="label">Final priorities</div><div class="value">{fmt_int(prio_count)}</div></div>
      </div>
    </div>
    <div>
      <h2>Pipeline</h2>
      <div class="summary-steps">{summary_steps}</div>
    </div>
  </div>
</section>

{consistency_html}

<section class="panel" id="comparison">
  <h2>Before / After View</h2>
  <p class="split-caption">Left is the vulnerability-only baseline before LLM-aware prioritization. Right is the final merged ranking after RiskRank combines vulnerability severity with semantic reachability.</p>
  <div class="legend-grid">
    <div class="legend-card">
      <h3>How to read the split</h3>
      <p><strong>Before</strong> is a vulnerability-only baseline sorted by highest CVSS first, then by finding count. <strong>After</strong> is the final review order after adding LLM-based exposure and business-criticality context.</p>
    </div>
    <div class="legend-card">
      <h3>Priority bands moved</h3>
      <p>Priority bands still exist in the detailed prioritization tables below. They were removed from this split view to keep the comparison focused on rank, score, and vulnerability evidence.</p>
      <div class="legend-inline">
        <span class="tier-pill tier-critical">P1 Critical</span>
        <span class="tier-pill tier-high">P2 High</span>
        <span class="tier-pill tier-medium">P3 Medium</span>
        <span class="tier-pill tier-low">P4 Low</span>
      </div>
    </div>
  </div>
  <div class="two-up">
    <div class="panel comparison-pane-before" style="margin-bottom:0;">
      <div class="comparison-tag tag-before">Before LLM prioritization</div>
      <h3>Baseline Vulnerability Ranking</h3>
      <div class="table-wrap comparison-table-wrap">
        <table class="comparison-table">
          <thead><tr>{help_th("Rank", "Position in the vulnerability-only baseline list.")}{help_th("File", "The file that received vulnerability findings.")}{help_th("Findings", "How many findings landed in this file.")}{help_th("Risk Score", "The scanner's aggregated baseline risk score before LLM context.")}{help_th("Max CVSS", "Highest CVSS score among findings in this file.")}</tr></thead>
          <tbody>{baseline_rows or '<tr><td colspan="5" class="muted">No vulnerability baseline available.</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    <div class="panel comparison-pane-after" style="margin-bottom:0;">
      <div class="comparison-tag tag-after">After RiskRank prioritization</div>
      <h3>Final Review Order</h3>
      <div class="table-wrap comparison-table-wrap">
        <table class="comparison-table">
          <thead><tr>{help_th("Rank", "Final review order after merging vulnerability severity with LLM reachability.")}{help_th("Target", "File or route selected for review.")}{help_th("Priority Score", "Final merged numeric score used to sort the review order.")}{help_th("LLM Score", "The model's reachability/business-criticality score for this target.")}{help_th("Max CVSS", "Highest vulnerability CVSS associated with this target.")}</tr></thead>
          <tbody>{final_rows or '<tr><td colspan="5" class="muted">No prioritization output available.</td></tr>'}</tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<section class="panel" id="rank-shifts">
  <h2>Rank Shifts Across the Pipeline</h2>
  <p class="muted">This comparison shows how raw vulnerability ranking changes once LLM reachability and final prioritization are applied.</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          {help_th("Path", "File path being compared across stages.")}
          {help_th("Baseline Rank", "Position in the vulnerability-only baseline list.")}
          {help_th("Baseline CVSS", "Highest vulnerability CVSS before LLM reprioritization.")}
          {help_th("Findings", "Total vulnerability findings used in the baseline stage.")}
          {help_th("LLM Rank", "Position assigned by the LLM reachability stage.")}
          {help_th("LLM Score", "Reachability/business-criticality score from the model.")}
          {help_th("Final Rank", "Position in the final merged review order.")}
          {help_th("Priority Band", "Urgency grouping in the final output.")}
          {help_th("Priority Score", "Merged score after combining CVSS and LLM reachability.")}
          {help_th("Shift", "How much the final rank moved relative to the baseline.")}
        </tr>
      </thead>
      <tbody>{''.join(before_after_rows) or '<tr><td colspan="10" class="muted">Not enough data to compare stages.</td></tr>'}</tbody>
    </table>
  </div>
</section>

{'<section class="panel" id="final-prioritization-detail"><h2>Final Prioritization Detail</h2><div class="table-wrap"><table><thead><tr>' + help_th("Rank", "Final review order after all scoring.") + help_th("Target", "File or route selected for review.") + help_th("Priority Band", "Urgency grouping. Multiple items can share the same band.") + help_th("Priority Score", "Merged score used for final ordering.") + help_th("LLM Score", "Reachability/business-criticality score from the LLM.") + help_th("LLM Rank", "Position assigned by the LLM stage before final merging.") + help_th("Max CVSS", "Highest CVSS tied to this target.") + help_th("Findings", "Total vulnerability findings for this target.") + help_th("Fan-in", "Structural centrality score from step 1.") + help_th("Git Commits", "Commit-touch count from git history analysis.") + help_th("Why", "Human-readable summary of why this item ended up here.") + '</tr></thead><tbody>' + prioritization_rows + '</tbody></table></div></section>' if prioritization_rows else ''}

{'<section class="panel" id="llm-detail"><h2>LLM Reachability Detail</h2><div class="table-wrap"><table><thead><tr>' + help_th("Rank", "Order produced by the LLM-only stage.") + help_th("Target", "File or route the LLM considered important.") + help_th("Score", "Reachability/business-criticality score from 0-100.") + help_th("Confidence", "How confident the LLM was in this judgment.") + help_th("Exposure", "Estimated public or entrypoint-facing exposure.") + help_th("Fan-in", "How much fan-in evidence supported the target.") + help_th("Git", "How much git-history signal supported the target.") + help_th("Business", "Estimated business criticality of the target.") + help_th("Why", "Short explanation produced by the model.") + '</tr></thead><tbody>' + llm_rows + '</tbody></table></div></section>' if llm_rows else ''}

{'<section class="panel" id="vuln-detail"><h2>Vulnerability Findings Detail</h2><div class="table-wrap"><table><thead><tr>' + help_th("Rank", "Position among the top vulnerability findings.") + help_th("Path", "File where the finding was reported.") + help_th("Line", "Line number associated with the finding.") + help_th("Severity", "Scanner-reported qualitative severity.") + help_th("CVSS", "Quantitative severity score for the finding.") + help_th("Rule", "Rule or detector that produced the finding.") + help_th("Description", "Short summary of the issue.") + '</tr></thead><tbody>' + vuln_findings_rows + '</tbody></table></div></section>' if vuln_findings_rows else ''}

{'<section class="panel" id="fanin-detail"><h2>Fan-in Detail</h2><div class="table-wrap"><table><thead><tr>' + help_th("Rank", "Position by structural centrality.") + help_th("Module", "File or module ranked by reachable entrypoints.") + help_th("Fan-in", "How many distinct entrypoints can reach this module.") + help_th("Reached by", "Example entrypoints that flow into this module.") + '</tr></thead><tbody>' + fanin_rows + '</tbody></table></div></section>' if fanin_rows else ''}

{'<section class="panel" id="git-detail"><h2>Git History Detail</h2><div class="table-wrap"><table><thead><tr>' + help_th("Rank", "Position by git activity.") + help_th("File", "File tracked in the git-history analysis.") + help_th("Commits", "Number of commits touching the file.") + help_th("Added", "Total lines added across git history.") + help_th("Deleted", "Total lines deleted across git history.") + help_th("Churn", "Added plus deleted lines; a maintenance hot-spot proxy.") + '</tr></thead><tbody>' + git_rows + '</tbody></table></div></section>' if git_rows else ''}

<footer>
  Generated by RiskRank &middot; {generated_at}
</footer>

<div class="drawer-shell" id="evidence-drawer" hidden>
  <div class="drawer-backdrop" data-drawer-close></div>
  <aside class="drawer-panel" aria-modal="true" role="dialog" aria-labelledby="drawer-title">
    <div class="drawer-topbar">
      <div>
        <div class="eyebrow">Evidence Drawer</div>
        <h3 id="drawer-title">Evidence</h3>
        <p class="drawer-subtitle" id="drawer-subtitle">Context and raw artifact data</p>
      </div>
      <button class="drawer-close" type="button" aria-label="Close evidence drawer" data-drawer-close>&times;</button>
    </div>
    <div class="drawer-body" id="drawer-body"></div>
  </aside>
</div>

<div hidden>
{''.join(drawer_templates)}
</div>

<script>
(() => {{
  const drawer = document.getElementById('evidence-drawer');
  const drawerBody = document.getElementById('drawer-body');
  const drawerTitle = document.getElementById('drawer-title');
  const drawerSubtitle = document.getElementById('drawer-subtitle');
  let activeRow = null;
  let lastTrigger = null;

  const closeDrawer = () => {{
    drawer.hidden = true;
    drawerBody.innerHTML = '';
    if (activeRow) activeRow.classList.remove('row-active');
    if (lastTrigger) lastTrigger.focus();
    activeRow = null;
    lastTrigger = null;
  }};

  document.addEventListener('click', (event) => {{
    const trigger = event.target.closest('[data-drawer-target]');
    if (trigger) {{
      const template = document.getElementById(trigger.getAttribute('data-drawer-target'));
      if (!template) return;
      const fragment = template.content.firstElementChild.cloneNode(true);
      drawerBody.innerHTML = '';
      drawerBody.appendChild(fragment);
      drawerTitle.textContent = fragment.querySelector('h3')?.textContent || 'Evidence';
      drawerSubtitle.textContent = fragment.querySelector('.drawer-subtitle')?.textContent || 'Context and raw artifact data';
      drawer.hidden = false;
      if (activeRow) activeRow.classList.remove('row-active');
      activeRow = trigger.closest('tr');
      if (activeRow) activeRow.classList.add('row-active');
      lastTrigger = trigger;
      return;
    }}

    if (event.target.closest('[data-drawer-close]')) {{
      closeDrawer();
    }}
  }});

  document.addEventListener('keydown', (event) => {{
    if (event.key === 'Escape' && !drawer.hidden) {{
      closeDrawer();
    }}
  }});
}})();
</script>

</div>
</body>
</html>"""
    return html, detail_pages


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <run_dir> [output.html]", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"Not a directory: {run_dir}", file=sys.stderr)
        sys.exit(1)

    out_path = (
        Path(sys.argv[2]).expanduser().resolve()
        if len(sys.argv) > 2
        else run_dir / "report.html"
    )
    html, detail_pages = generate(run_dir)
    out_path.write_text(html, encoding="utf-8")
    detail_dir = out_path.parent / "details"
    detail_dir.mkdir(parents=True, exist_ok=True)
    for path, page_html in detail_pages.items():
        detail_path = detail_dir / f"{slugify_path(path)}.html"
        detail_path.write_text(page_html, encoding="utf-8")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
