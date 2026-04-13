#!/usr/bin/env python3
"""
Generate a self-contained HTML report from pipeline run artifacts.
Usage: python3 generate_report.py <run_dir> [output.html]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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


def severity_class(sev: str) -> str:
    s = sev.lower()
    if s == "high":
        return "sev-high"
    if s == "medium":
        return "sev-medium"
    return "sev-low"


def generate(run_dir: Path) -> str:
    manifest = load_json(run_dir / "manifest.json") or {}
    vuln = load_json(run_dir / "vulnerabilities" / "summary.json")
    llm = load_json(run_dir / "llm" / "llm_reachability_ranking.json")
    prio = load_json(run_dir / "prioritization" / "summary.json")
    fanin = load_json(run_dir / "fanin" / "summary.json")
    git = load_json(run_dir / "git_history" / "summary.json")

    project = manifest.get("project", "unknown")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # --- Vulnerability rows ---
    vuln_rows = ""
    vuln_count = 0
    vuln_engine = ""
    if vuln:
        vuln_count = vuln.get("findings_count", 0)
        vuln_engine = vuln.get("engine", "?")
        for f in vuln.get("top_findings", []):
            path = esc(f.get("path", "?"))
            line = f.get("line", "?")
            sev = f.get("severity", "?")
            cvss = f.get("cvss_base")
            rule = esc(f.get("rule_id", "?"))
            desc = esc(f.get("description", "").split("\n")[0][:200])
            cvss_str = f"{cvss:.1f}" if isinstance(cvss, (int, float)) else "-"
            vuln_rows += f"""<tr>
              <td><code>{path}</code></td>
              <td>{line}</td>
              <td><span class="sev-pill {severity_class(sev)}">{sev}</span></td>
              <td><span class="cvss-pill {cvss_class(cvss)}">{cvss_str}</span></td>
              <td><code>{rule}</code></td>
              <td class="desc-cell">{desc}</td>
            </tr>"""

    # --- LLM rows ---
    llm_rows = ""
    llm_model = ""
    llm_count = 0
    if llm:
        llm_model = llm.get("method", {}).get("model", "?")
        targets = llm.get("ranked_targets", [])
        llm_count = len(targets)
        for t in targets:
            tgt = t.get("target", {})
            path = esc(tgt.get("path", "?"))
            score = t.get("score", "?")
            conf = t.get("confidence", "?")
            why = esc(t.get("why", "")[:200])
            sigs = t.get("signals", {})
            exp = sigs.get("entrypoint_exposure", "-")
            biz = sigs.get("business_criticality", "-")
            git_s = sigs.get("git_activity_signal", "-")
            llm_rows += f"""<tr>
              <td>{t['rank']}</td>
              <td><code>{path}</code></td>
              <td>{score}</td>
              <td><span class="conf-pill conf-{conf}">{conf}</span></td>
              <td>{exp}</td>
              <td>{biz}</td>
              <td>{git_s}</td>
              <td class="desc-cell">{why}</td>
            </tr>"""
        obs = llm.get("global_observations", [])
        if obs:
            llm_rows += f"""<tr class="obs-row"><td colspan="8">
              <details><summary>Observations ({len(obs)})</summary>
              <ul>{"".join(f"<li>{esc(o)}</li>" for o in obs)}</ul>
              </details></td></tr>"""

    # --- Prioritization rows ---
    prio_rows = ""
    prio_count = 0
    if prio:
        rows = prio.get("top_priorities", [])
        prio_count = len(rows)
        for r in rows:
            path = esc(r.get("path", "?"))
            tier = r.get("priority_tier", "?")
            ps = r.get("priority_score")
            llm_s = r.get("llm_score")
            cvss = r.get("max_cvss")
            n_vuln = r.get("vuln_findings", 0)
            rule = esc(r.get("primary_vuln_rule", "-"))
            why = esc(r.get("why", "")[:200])
            ps_str = f"{ps:.1f}" if isinstance(ps, (int, float)) else "-"
            cvss_str = f"{cvss:.1f}" if isinstance(cvss, (int, float)) else "-"
            llm_str = f"{llm_s:.0f}" if isinstance(llm_s, (int, float)) else "-"
            prio_rows += f"""<tr>
              <td>{r['rank']}</td>
              <td><code>{path}</code></td>
              <td><span class="tier-pill {tier_class(tier)}">{tier}</span></td>
              <td>{ps_str}</td>
              <td>{llm_str}</td>
              <td><span class="cvss-pill {cvss_class(cvss)}">{cvss_str}</span></td>
              <td>{n_vuln}</td>
              <td><code>{rule}</code></td>
              <td class="desc-cell">{why}</td>
            </tr>"""
            # Evidence sub-rows
            ev = r.get("vuln_evidence", [])
            if ev:
                ev_html = ""
                for e in ev:
                    eline = e.get("line", "?")
                    erule = esc(e.get("rule_id", "?"))
                    edesc = esc(e.get("description", "").split("\n")[0][:200])
                    esev = e.get("severity", "?")
                    ev_html += f"<li><strong>L{eline}</strong> <code>{erule}</code> [{esev}] — {edesc}</li>"
                prio_rows += f"""<tr class="ev-row"><td colspan="9">
                  <details><summary>Vulnerability evidence</summary>
                  <ul>{ev_html}</ul></details></td></tr>"""

    # --- Fan-in rows ---
    fanin_rows = ""
    fanin_count = 0
    fanin_engine = ""
    if fanin:
        fanin_engine = fanin.get("engine", "?")
        fanin_count = fanin.get("modules_ranked", 0)
        for m in fanin.get("top_modules", []):
            mod = esc(m.get("module", "?"))
            fi = m.get("fan_in", "?")
            eps = ", ".join(m.get("entrypoints_reaching", []))
            fanin_rows += f"<tr><td>{m['rank']}</td><td><code>{mod}</code></td><td>{fi}</td><td><code>{esc(eps)}</code></td></tr>"

    # --- Git history rows ---
    git_rows = ""
    git_count = 0
    if git:
        git_count = git.get("files_ranked", 0)
        for f in git.get("top_files", []):
            fp = esc(f.get("file", "?"))
            commits = f.get("commits_touched", "?")
            churn = f.get("churn", "?")
            added = f.get("total_added", 0)
            deleted = f.get("total_deleted", 0)
            git_rows += f"<tr><td>{f['rank']}</td><td><code>{fp}</code></td><td>{commits}</td><td>{added}</td><td>{deleted}</td><td>{churn}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scan Report — {esc(project)}</title>
<style>
:root {{
  --bg: #f8f4ee;
  --panel: rgba(255, 252, 248, 0.9);
  --border: #decfbd;
  --text: #1f2d2f;
  --text-dim: #6b5b4a;
  --accent: #5a7d6e;
  --critical: #c0392b;
  --high: #d35400;
  --medium: #e67e22;
  --low: #7f8c8d;
  --tier-p0: #c0392b;
  --tier-p1: #d35400;
  --tier-p2: #e67e22;
  --tier-p3: #7f8c8d;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  background: radial-gradient(circle at 15% 0%, rgba(246,223,188,0.35), transparent 42%),
              radial-gradient(circle at 90% 10%, rgba(138,175,164,0.3), transparent 34%),
              var(--bg);
  color: var(--text);
  line-height: 1.5;
  padding: 24px;
}}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1, h2 {{
  font-family: "Source Serif 4", Georgia, serif;
  letter-spacing: 0.2px;
}}
h1 {{
  font-size: 1.6em;
  margin-bottom: 4px;
}}
h2 {{
  font-size: 1.15em;
  margin-bottom: 12px;
  color: var(--accent);
}}
.meta {{ color: var(--text-dim); font-size: 0.9em; margin-bottom: 20px; }}
.panel {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 6px 16px rgba(83,52,20,0.05);
}}
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}}
.metric-card {{
  border: 1px solid #ddccb8;
  border-radius: 10px;
  padding: 12px;
  background: #fffdf9;
}}
.metric-card .label {{ font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }}
.metric-card .value {{ font-size: 1.4em; font-weight: 700; margin-top: 2px; }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85em;
}}
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
tbody td {{
  padding: 8px;
  border-bottom: 1px solid #e7d8c7;
  vertical-align: top;
}}
tbody tr:hover {{ background: rgba(170,191,185,0.1); }}
.desc-cell {{ max-width: 300px; font-size: 0.9em; color: #364348; }}
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
  font-size: 0.85em;
  padding: 4px 0;
}}
summary:hover {{ text-decoration: underline; }}
ul {{ margin: 8px 0 4px 20px; font-size: 0.88em; }}
li {{ margin-bottom: 4px; }}
.ev-row td, .obs-row td {{
  background: rgba(247,240,231,0.7);
  padding: 10px;
}}
.pill {{
  display: inline-block;
  min-width: 44px;
  text-align: center;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 600;
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
section {{ scroll-margin-top: 16px; }}
@media (max-width: 900px) {{
  body {{ padding: 12px; }}
  table {{ font-size: 0.8em; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>Scan Report</h1>
<p class="meta">
  <strong>Project:</strong> <code>{esc(project)}</code> &nbsp;|&nbsp;
  <strong>Generated:</strong> {generated_at}
</p>

<!-- Metrics -->
<div class="metrics">
  <div class="metric-card">
    <div class="label">Vulnerabilities</div>
    <div class="value">{vuln_count}</div>
  </div>
  <div class="metric-card">
    <div class="label">LLM targets</div>
    <div class="value">{llm_count}</div>
  </div>
  <div class="metric-card">
    <div class="label">Prioritized</div>
    <div class="value">{prio_count}</div>
  </div>
  <div class="metric-card">
    <div class="label">Fan-in modules</div>
    <div class="value">{fanin_count}</div>
  </div>
  <div class="metric-card">
    <div class="label">Git-tracked files</div>
    <div class="value">{git_count}</div>
  </div>
</div>

{"<section class='panel' id='prioritization'><h2>Combined Prioritization</h2><div style='overflow:auto'><table><thead><tr><th>Rank</th><th>Target</th><th>Tier</th><th>Priority</th><th>LLM</th><th>CVSS</th><th>Vulns</th><th>Primary Rule</th><th>Why</th></tr></thead><tbody>" + prio_rows + "</tbody></table></div></section>" if prio_rows else ""}

{"<section class='panel' id='vulnerabilities'><h2>Vulnerability Scan <span style='font-weight:400;font-size:0.8em;color:#6b5b4a'>(" + str(vuln_count) + " finding(s), " + esc(vuln_engine) + " engine)</span></h2><div style='overflow:auto'><table><thead><tr><th>File</th><th>Line</th><th>Severity</th><th>CVSS</th><th>Rule</th><th>Description</th></tr></thead><tbody>" + vuln_rows + "</tbody></table></div></section>" if vuln_rows else ""}

{"<section class='panel' id='llm'><h2>LLM Reachability <span style='font-weight:400;font-size:0.8em;color:#6b5b4a'>(" + str(llm_count) + " target(s), " + esc(llm_model) + ")</span></h2><div style='overflow:auto'><table><thead><tr><th>Rank</th><th>Target</th><th>Score</th><th>Confidence</th><th>Exposure</th><th>Criticality</th><th>Git Activity</th><th>Why</th></tr></thead><tbody>" + llm_rows + "</tbody></table></div></section>" if llm_rows else ""}

{"<section class='panel' id='fanin'><h2>Fan-in Ranking <span style='font-weight:400;font-size:0.8em;color:#6b5b4a'>(" + str(fanin_count) + " module(s), " + esc(fanin_engine) + " engine)</span></h2><div style='overflow:auto'><table><thead><tr><th>Rank</th><th>Module</th><th>Fan-in</th><th>Reached by</th></tr></thead><tbody>" + fanin_rows + "</tbody></table></div></section>" if fanin_rows else ""}

{"<section class='panel' id='git'><h2>Git History <span style='font-weight:400;font-size:0.8em;color:#6b5b4a'>(" + str(git_count) + " file(s))</span></h2><div style='overflow:auto'><table><thead><tr><th>Rank</th><th>File</th><th>Commits</th><th>Added</th><th>Deleted</th><th>Churn</th></tr></thead><tbody>" + git_rows + "</tbody></table></div></section>" if git_rows else ""}

<footer style="margin-top:24px;font-size:0.8em;color:#9a8d7f;text-align:center">
  Generated by experiment pipeline &middot; {generated_at}
</footer>

</div>
</body>
</html>"""
    return html


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <run_dir> [output.html]", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"Not a directory: {run_dir}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else run_dir / "report.html"
    html = generate(run_dir)
    out_path.write_text(html, encoding="utf-8")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
