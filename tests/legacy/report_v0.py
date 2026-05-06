"""
Generate Markdown + HTML QA reports from reports/all_results.json.

Outputs:
  reports/REPORT.md
  reports/REPORT.html
  reports/SUMMARY.json   (top-level stats only)

The aggregate JSON already has every per-query detail; this script converts it
into reader-friendly artefacts.
"""
from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AGG = ROOT / "reports" / "all_results.json"
RESULTS_DIR = ROOT / "reports" / "results"
MD_OUT = ROOT / "reports" / "REPORT.md"
HTML_OUT = ROOT / "reports" / "REPORT.html"
SUMMARY_OUT = ROOT / "reports" / "SUMMARY.json"


# ---------------------------------------------------------------------------
def load() -> list[dict[str, Any]]:
    """Prefer the final aggregate, but fall back to live per-query JSON files
    so we can render intermediate reports while the run is still in progress."""
    if AGG.exists():
        return json.loads(AGG.read_text())
    if RESULTS_DIR.exists():
        files = sorted(RESULTS_DIR.glob("q*.json"))
        if not files:
            raise SystemExit(f"No per-query results found in {RESULTS_DIR}.")
        out = []
        for f in files:
            try:
                out.append(json.loads(f.read_text()))
            except Exception as e:
                print(f"warn: skipping {f}: {e}")
        return out
    raise SystemExit(f"Missing {AGG} and {RESULTS_DIR}. Run tests/runner.py first.")


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    status_counts = Counter(r.get("overall_status", "UNKNOWN") for r in results)

    run_sql_present = sum(1 for r in results if r.get("run_sql_call"))
    run_sql_ok = sum(1 for r in results if r.get("validations", {}).get("run_sql_status_ok"))
    run_sql_with_rows = sum(1 for r in results if r.get("validations", {}).get("run_sql_has_rows"))

    gv_present = sum(1 for r in results if r.get("generate_viz_call"))
    gv_ok = sum(1 for r in results if r.get("validations", {}).get("generate_viz_status_ok"))
    gv_with_chart = sum(1 for r in results if r.get("validations", {}).get("generate_viz_has_chart"))

    cols_synced = sum(1 for r in results if r.get("validations", {}).get("columns_synced_run_sql_vs_generate_viz") is True)
    cols_unsynced = sum(1 for r in results if r.get("validations", {}).get("columns_synced_run_sql_vs_generate_viz") is False)

    durations = [r.get("total_duration_ms") for r in results if r.get("total_duration_ms")]
    avg_dur = int(sum(durations) / len(durations)) if durations else 0
    max_dur = max(durations) if durations else 0

    failing_queries = [
        {"id": r["id"], "nl_query": r["nl_query"], "fail_reasons": r.get("validations", {}).get("fail_reasons", [])}
        for r in results if r.get("overall_status") == "FAIL"
    ]
    partial_queries = [
        {"id": r["id"], "nl_query": r["nl_query"], "warn_reasons": r.get("validations", {}).get("warn_reasons", [])}
        for r in results if r.get("overall_status") == "PARTIAL"
    ]
    timeout_queries = [
        {
            "id": r["id"],
            "nl_query": r["nl_query"],
            "timed_out_on": r.get("validations", {}).get("timed_out_on"),
            "duration_ms": r.get("total_duration_ms"),
        }
        for r in results if r.get("overall_status") == "TIMEOUT"
    ]

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total_queries": total,
        "status_breakdown": dict(status_counts),
        "run_sql": {
            "present": run_sql_present,
            "http_ok": run_sql_ok,
            "with_rows": run_sql_with_rows,
        },
        "generate_viz": {
            "present": gv_present,
            "http_ok": gv_ok,
            "with_chart": gv_with_chart,
        },
        "column_sync": {
            "synced": cols_synced,
            "unsynced": cols_unsynced,
        },
        "performance_ms": {
            "avg": avg_dur,
            "max": max_dur,
        },
        "failing_queries": failing_queries,
        "partial_queries": partial_queries,
        "timeout_queries": timeout_queries,
    }


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def render_md(results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Skylar IQ SQL Agent — Automation QA Report")
    lines.append("")
    lines.append(f"_Generated: {summary['generated_at']}_")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(f"- **Total queries tested:** {summary['total_queries']}")
    sb = summary["status_breakdown"]
    lines.append(f"- **PASS:** {sb.get('PASS', 0)}  |  **PARTIAL:** {sb.get('PARTIAL', 0)}  |  **FAIL:** {sb.get('FAIL', 0)}  |  **TIMEOUT:** {sb.get('TIMEOUT', 0)}")
    lines.append(f"- **Average per-query duration:** {summary['performance_ms']['avg']} ms")
    lines.append(f"- **Slowest query:** {summary['performance_ms']['max']} ms")
    lines.append("")
    lines.append("### API health")
    lines.append("")
    lines.append("| Endpoint | Captured | HTTP 2xx | With usable payload |")
    lines.append("|---|---|---|---|")
    rs = summary["run_sql"]
    gv = summary["generate_viz"]
    t = summary["total_queries"]
    lines.append(f"| `run-sql` | {rs['present']}/{t} | {rs['http_ok']}/{t} | {rs['with_rows']}/{t} (rows>0) |")
    lines.append(f"| `generate-viz` | {gv['present']}/{t} | {gv['http_ok']}/{t} | {gv['with_chart']}/{t} (chart payload) |")
    lines.append("")
    lines.append("### Column-name sync (run-sql ↔ generate-viz)")
    lines.append("")
    cs = summary["column_sync"]
    lines.append(f"- Synced: **{cs['synced']}**, Unsynced: **{cs['unsynced']}**")
    lines.append("")

    if summary["failing_queries"]:
        lines.append("## 2. Failing queries")
        lines.append("")
        for f in summary["failing_queries"]:
            lines.append(f"- **q{f['id']:02d}** — {f['nl_query']}")
            for r in f["fail_reasons"]:
                lines.append(f"  - ❌ {r}")
        lines.append("")

    if summary["partial_queries"]:
        lines.append("## 3. Partial / warnings")
        lines.append("")
        for w in summary["partial_queries"]:
            lines.append(f"- **q{w['id']:02d}** — {w['nl_query']}")
            for r in w["warn_reasons"]:
                lines.append(f"  - ⚠ {r}")
        lines.append("")

    if summary["timeout_queries"]:
        lines.append("## 3a. Timed-out queries (skipped after 2 min budget)")
        lines.append("")
        for t in summary["timeout_queries"]:
            lines.append(f"- **q{t['id']:02d}** — {t['nl_query']}")
            lines.append(f"  - ⏱ timed out on `{t['timed_out_on']}` after {t.get('duration_ms','?')} ms")
        lines.append("")

    lines.append("## 4. Per-query detail")
    lines.append("")
    for r in results:
        lines.append(f"### q{r['id']:02d} — {r['nl_query']}")
        lines.append("")
        lines.append(f"- **Status:** `{r['overall_status']}`")
        lines.append(f"- **Duration:** {r.get('total_duration_ms')} ms")
        v = r.get("validations", {}) or {}
        rs_call = r.get("run_sql_call") or {}
        gv_call = r.get("generate_viz_call") or {}
        lines.append(f"- **run-sql:** {rs_call.get('method', '-')} `{rs_call.get('url', '-')}` → HTTP {rs_call.get('status', 'n/a')} ({rs_call.get('duration_ms', '-')} ms)")
        lines.append(f"  - rows: {v.get('run_sql_row_count', '-')}, columns: {v.get('run_sql_columns')}")
        lines.append(f"  - response keys: {v.get('run_sql_response_keys')}")
        lines.append(f"- **generate-viz:** {gv_call.get('method', '-')} `{gv_call.get('url', '-')}` → HTTP {gv_call.get('status', 'n/a')} ({gv_call.get('duration_ms', '-')} ms)")
        lines.append(f"  - chart_type: {v.get('generate_viz_chart_type')}, x: {v.get('generate_viz_x_axis')}, y: {v.get('generate_viz_y_axis')}")
        lines.append(f"  - data_points: {v.get('generate_viz_data_points')}, columns: {v.get('generate_viz_columns')}")
        lines.append(f"  - response keys: {v.get('generate_viz_response_keys')}")
        lines.append(f"- **columns synced:** {v.get('columns_synced_run_sql_vs_generate_viz')}")
        if v.get("column_only_in_run_sql"):
            lines.append(f"  - only in run-sql: `{v['column_only_in_run_sql']}`")
        if v.get("column_only_in_generate_viz"):
            lines.append(f"  - only in generate-viz: `{v['column_only_in_generate_viz']}`")
        if v.get("fail_reasons"):
            lines.append(f"- **Failures:** {v['fail_reasons']}")
        if v.get("warn_reasons"):
            lines.append(f"- **Warnings:** {v['warn_reasons']}")
        if r.get("error"):
            lines.append("- **Exception:**")
            lines.append("  ```")
            for ln in (r["error"] or "").splitlines()[:8]:
                lines.append(f"  {ln}")
            lines.append("  ```")
        if r.get("screenshots"):
            for sp in r["screenshots"]:
                if sp:
                    lines.append(f"- ![screenshot]({sp})")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
HTML_TMPL = """<!doctype html>
<html><head>
<meta charset="utf-8"><title>Skylar IQ QA Report</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1200px;margin:24px auto;padding:0 20px;color:#222}}
 h1,h2,h3{{color:#1a3a6e}}
 .pass{{background:#e8f6ee;border-left:4px solid #1a8a3a;padding:8px 12px;margin:8px 0}}
 .partial{{background:#fff8e1;border-left:4px solid #d49a00;padding:8px 12px;margin:8px 0}}
 .fail{{background:#fdecea;border-left:4px solid #c62828;padding:8px 12px;margin:8px 0}}
 table{{border-collapse:collapse;width:100%;margin:12px 0}}
 th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left;font-size:13px}}
 th{{background:#f4f6fa}}
 details{{margin:6px 0}}
 pre{{background:#0f172a;color:#e2e8f0;padding:10px;border-radius:6px;overflow:auto;font-size:11px;max-height:320px}}
 .badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}
 .badge.PASS{{background:#1a8a3a;color:#fff}}
 .badge.PARTIAL{{background:#d49a00;color:#fff}}
 .badge.FAIL{{background:#c62828;color:#fff}}
 .badge.TIMEOUT{{background:#6a4ec2;color:#fff}}
 .badge.PENDING{{background:#888;color:#fff}}
 .meta{{color:#555;font-size:12px}}
 img.screenshot{{max-width:100%;border:1px solid #ddd;margin:6px 0}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:8px}}
 .card{{background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:10px}}
 .num{{font-size:26px;font-weight:700;color:#1a3a6e}}
</style></head>
<body>
<h1>Skylar IQ SQL Agent — Automation QA Report</h1>
<p class="meta">Generated: {generated_at}</p>

<h2>1. Executive Summary</h2>
<div class="grid">
  <div class="card"><div class="num">{total}</div>Total queries</div>
  <div class="card"><div class="num">{pass_n}</div>PASS</div>
  <div class="card"><div class="num">{partial_n}</div>PARTIAL</div>
  <div class="card"><div class="num">{fail_n}</div>FAIL</div>
  <div class="card"><div class="num">{timeout_n}</div>TIMEOUT</div>
  <div class="card"><div class="num">{avg_ms} ms</div>Avg duration</div>
  <div class="card"><div class="num">{max_ms} ms</div>Max duration</div>
</div>

<h3>API health</h3>
<table>
<tr><th>Endpoint</th><th>Captured</th><th>HTTP 2xx</th><th>With usable payload</th></tr>
<tr><td><code>run-sql</code></td><td>{rs_present}/{total}</td><td>{rs_ok}/{total}</td><td>{rs_rows}/{total} (rows&gt;0)</td></tr>
<tr><td><code>generate-viz</code></td><td>{gv_present}/{total}</td><td>{gv_ok}/{total}</td><td>{gv_chart}/{total} (chart payload)</td></tr>
</table>

<h3>Column-name sync</h3>
<p>Synced: <b>{cols_synced}</b> &nbsp;|&nbsp; Unsynced: <b>{cols_unsynced}</b></p>

<h2>2. Failing queries ({fail_n})</h2>
{fail_list}

<h2>3. Partial / warnings ({partial_n})</h2>
{partial_list}

<h2>3a. Timed-out queries ({timeout_n})</h2>
{timeout_list}

<h2>4. Per-query detail</h2>
{per_query}

</body></html>
"""


def render_html(results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    sb = summary["status_breakdown"]
    fail_list_html = "<ul>" + "".join(
        f"<li><b>q{f['id']:02d}</b> — {html.escape(f['nl_query'])}<ul>"
        + "".join(f"<li>❌ {html.escape(r)}</li>" for r in f["fail_reasons"])
        + "</ul></li>"
        for f in summary["failing_queries"]
    ) + "</ul>" if summary["failing_queries"] else "<p><i>No failing queries.</i></p>"

    partial_list_html = "<ul>" + "".join(
        f"<li><b>q{w['id']:02d}</b> — {html.escape(w['nl_query'])}<ul>"
        + "".join(f"<li>⚠ {html.escape(r)}</li>" for r in w["warn_reasons"])
        + "</ul></li>"
        for w in summary["partial_queries"]
    ) + "</ul>" if summary["partial_queries"] else "<p><i>No partial queries.</i></p>"

    timeout_list_html = "<ul>" + "".join(
        f"<li><b>q{t['id']:02d}</b> — {html.escape(t['nl_query'])} "
        f"<span class=\"meta\">(timed out on <code>{html.escape(str(t['timed_out_on']))}</code>, {t.get('duration_ms','?')} ms)</span></li>"
        for t in summary["timeout_queries"]
    ) + "</ul>" if summary["timeout_queries"] else "<p><i>No timeouts.</i></p>"

    parts: list[str] = []
    for r in results:
        v = r.get("validations", {}) or {}
        rs_call = r.get("run_sql_call") or {}
        gv_call = r.get("generate_viz_call") or {}
        status = r.get("overall_status", "PENDING")
        block_class = status.lower()
        screenshots = "".join(
            f'<img class="screenshot" src="../{html.escape(sp)}" alt="screenshot">'
            for sp in (r.get("screenshots") or []) if sp
        )
        rs_body = json.dumps(rs_call.get("response_body"), indent=2, default=str)[:6000] if rs_call else ""
        gv_body = json.dumps(gv_call.get("response_body"), indent=2, default=str)[:6000] if gv_call else ""
        rs_req = json.dumps(rs_call.get("request_post_data"), indent=2, default=str)[:3000] if rs_call else ""
        gv_req = json.dumps(gv_call.get("request_post_data"), indent=2, default=str)[:3000] if gv_call else ""

        parts.append(f"""
<details class="{block_class}" {'open' if status != 'PASS' else ''}>
<summary>
  <span class="badge {status}">{status}</span>
  <b>q{r['id']:02d}</b> — {html.escape(r['nl_query'])}
  <span class="meta">({r.get('total_duration_ms','?')} ms)</span>
</summary>
<table>
 <tr><th>run-sql</th>
   <td>{html.escape(rs_call.get('method','-'))} <code>{html.escape(str(rs_call.get('url','-')))}</code><br>
   HTTP {rs_call.get('status','n/a')} · {rs_call.get('duration_ms','-')} ms<br>
   rows: {v.get('run_sql_row_count','-')}, columns: <code>{html.escape(json.dumps(v.get('run_sql_columns')))}</code><br>
   response keys: <code>{html.escape(json.dumps(v.get('run_sql_response_keys')))}</code>
   </td></tr>
 <tr><th>generate-viz</th>
   <td>{html.escape(gv_call.get('method','-'))} <code>{html.escape(str(gv_call.get('url','-')))}</code><br>
   HTTP {gv_call.get('status','n/a')} · {gv_call.get('duration_ms','-')} ms<br>
   chart_type: <code>{html.escape(str(v.get('generate_viz_chart_type')))}</code>, x: <code>{html.escape(str(v.get('generate_viz_x_axis')))}</code>, y: <code>{html.escape(str(v.get('generate_viz_y_axis')))}</code><br>
   data_points: {v.get('generate_viz_data_points','-')}, columns: <code>{html.escape(json.dumps(v.get('generate_viz_columns')))}</code><br>
   response keys: <code>{html.escape(json.dumps(v.get('generate_viz_response_keys')))}</code>
   </td></tr>
 <tr><th>columns synced</th><td><code>{v.get('columns_synced_run_sql_vs_generate_viz')}</code> — only in run-sql: <code>{html.escape(json.dumps(v.get('column_only_in_run_sql')))}</code>, only in generate-viz: <code>{html.escape(json.dumps(v.get('column_only_in_generate_viz')))}</code></td></tr>
 <tr><th>fail reasons</th><td>{html.escape(json.dumps(v.get('fail_reasons')))}</td></tr>
 <tr><th>warn reasons</th><td>{html.escape(json.dumps(v.get('warn_reasons')))}</td></tr>
</table>
<details><summary>run-sql request body</summary><pre>{html.escape(rs_req or '(none)')}</pre></details>
<details><summary>run-sql response body</summary><pre>{html.escape(rs_body or '(none)')}</pre></details>
<details><summary>generate-viz request body</summary><pre>{html.escape(gv_req or '(none)')}</pre></details>
<details><summary>generate-viz response body</summary><pre>{html.escape(gv_body or '(none)')}</pre></details>
{('<details><summary>screenshots</summary>'+screenshots+'</details>') if screenshots else ''}
{('<details><summary>exception</summary><pre>'+html.escape(r.get('error') or '')+'</pre></details>') if r.get('error') else ''}
</details>
""")

    return HTML_TMPL.format(
        generated_at=summary["generated_at"],
        total=summary["total_queries"],
        pass_n=sb.get("PASS", 0),
        partial_n=sb.get("PARTIAL", 0),
        fail_n=sb.get("FAIL", 0),
        timeout_n=sb.get("TIMEOUT", 0),
        avg_ms=summary["performance_ms"]["avg"],
        max_ms=summary["performance_ms"]["max"],
        rs_present=summary["run_sql"]["present"],
        rs_ok=summary["run_sql"]["http_ok"],
        rs_rows=summary["run_sql"]["with_rows"],
        gv_present=summary["generate_viz"]["present"],
        gv_ok=summary["generate_viz"]["http_ok"],
        gv_chart=summary["generate_viz"]["with_chart"],
        cols_synced=summary["column_sync"]["synced"],
        cols_unsynced=summary["column_sync"]["unsynced"],
        fail_list=fail_list_html,
        partial_list=partial_list_html,
        timeout_list=timeout_list_html,
        per_query="\n".join(parts),
    )


# ---------------------------------------------------------------------------
def main() -> None:
    results = load()
    summary = summarize(results)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2))
    MD_OUT.write_text(render_md(results, summary))
    HTML_OUT.write_text(render_html(results, summary))
    print(f"Wrote {SUMMARY_OUT}")
    print(f"Wrote {MD_OUT}")
    print(f"Wrote {HTML_OUT}")


if __name__ == "__main__":
    main()
