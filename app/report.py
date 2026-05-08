"""
Generate REPORT.html / REPORT.md / SUMMARY.json for a single job folder.

A "job folder" is whatever was passed as RunConfig.output_dir to runner.run().
Layout produced by the runner:
    <job_dir>/
        results/qNN.json        ← per-query records
        network_logs/qNN_calls.json
        screenshots/qNN_*.png
        all_results.json        ← aggregate (written when run completes)

This module reads either the aggregate or the per-query JSONs (whichever exists)
and writes:
    <job_dir>/REPORT.html
    <job_dir>/REPORT.md
    <job_dir>/SUMMARY.json
"""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_results(job_dir: Path) -> list[dict[str, Any]]:
    agg = job_dir / "all_results.json"
    if agg.exists():
        return json.loads(agg.read_text())
    res = job_dir / "results"
    if res.exists():
        files = sorted(res.glob("q*.json"))
        if files:
            out = []
            for f in files:
                try:
                    out.append(json.loads(f.read_text()))
                except Exception as e:
                    print(f"warn: skipping {f}: {e}")
            return out
    raise SystemExit(f"No results in {job_dir}")


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    status_counts = Counter(r.get("overall_status", "UNKNOWN") for r in results)

    # Detect test type so the summary uses the right per-endpoint counts
    is_site_search = any(
        r.get("search_keywords_call") or r.get("search_results_call")
        or any(c.get("classification") in ("search-keywords", "search-results")
               for c in (r.get("calls") or []))
        for r in results
    )

    rs_present = sum(1 for r in results if r.get("run_sql_call"))
    rs_ok = sum(1 for r in results if r.get("validations", {}).get("run_sql_status_ok"))
    rs_rows = sum(1 for r in results if r.get("validations", {}).get("run_sql_has_rows"))

    gv_present = sum(1 for r in results if r.get("generate_viz_call"))
    gv_ok = sum(1 for r in results if r.get("validations", {}).get("generate_viz_status_ok"))
    gv_chart = sum(1 for r in results if r.get("validations", {}).get("generate_viz_has_chart"))

    sk_present = sum(1 for r in results if r.get("search_keywords_call"))
    sk_ok = sum(1 for r in results if r.get("validations", {}).get("search_keywords_status_ok"))
    sr_present = sum(1 for r in results if r.get("search_results_call"))
    sr_ok = sum(1 for r in results if r.get("validations", {}).get("search_results_status_ok"))
    sr_with_products = sum(1 for r in results if (r.get("validations", {}).get("search_results_count") or 0) > 0)

    cs = sum(1 for r in results if r.get("validations", {}).get("columns_synced_run_sql_vs_generate_viz") is True)
    cu = sum(1 for r in results if r.get("validations", {}).get("columns_synced_run_sql_vs_generate_viz") is False)

    durations = [r["total_duration_ms"] for r in results if r.get("total_duration_ms")]
    avg = int(sum(durations) / len(durations)) if durations else 0
    mx = max(durations) if durations else 0

    failing = [
        {"id": r["id"], "nl_query": r["nl_query"], "fail_reasons": r.get("validations", {}).get("fail_reasons", [])}
        for r in results if r.get("overall_status") == "FAIL"
    ]
    partial = [
        {"id": r["id"], "nl_query": r["nl_query"], "warn_reasons": r.get("validations", {}).get("warn_reasons", [])}
        for r in results if r.get("overall_status") == "PARTIAL"
    ]
    timeouts = [
        {
            "id": r["id"],
            "nl_query": r["nl_query"],
            "timed_out_on": r.get("validations", {}).get("timed_out_on"),
            "duration_ms": r.get("total_duration_ms"),
        }
        for r in results if r.get("overall_status") == "TIMEOUT"
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_queries": total,
        "status_breakdown": dict(status_counts),
        "test_type": "site_search" if is_site_search else "sql_agent",
        "run_sql": {"present": rs_present, "http_ok": rs_ok, "with_rows": rs_rows},
        "generate_viz": {"present": gv_present, "http_ok": gv_ok, "with_chart": gv_chart},
        "search_keywords": {"present": sk_present, "http_ok": sk_ok},
        "search_results": {"present": sr_present, "http_ok": sr_ok, "with_products": sr_with_products},
        "column_sync": {"synced": cs, "unsynced": cu},
        "performance_ms": {"avg": avg, "max": mx},
        "failing_queries": failing,
        "partial_queries": partial,
        "timeout_queries": timeouts,
    }


# ---------------------------------------------------------------------------
def render_md(results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    sb = summary["status_breakdown"]
    is_site_search = summary.get("test_type") == "site_search"
    title_suffix = "Site Search" if is_site_search else "SQL AI Engine"
    lines: list[str] = []
    lines.append(f"# Skylar IQ {title_suffix} — Automation QA Report")
    lines.append(f"_Generated: {summary['generated_at']}_")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append(f"- **Total:** {summary['total_queries']}")
    lines.append(
        f"- **PASS:** {sb.get('PASS',0)}  |  **PARTIAL:** {sb.get('PARTIAL',0)}  |  "
        f"**FAIL:** {sb.get('FAIL',0)}  |  **TIMEOUT:** {sb.get('TIMEOUT',0)}"
    )
    lines.append(f"- **Avg duration:** {summary['performance_ms']['avg']} ms")
    lines.append(f"- **Max duration:** {summary['performance_ms']['max']} ms")
    lines.append("")
    lines.append("### API health")
    lines.append("| Endpoint | Captured | HTTP 2xx | Usable payload |")
    lines.append("|---|---|---|---|")
    t = summary["total_queries"]
    if is_site_search:
        sk = summary["search_keywords"]; sr = summary["search_results"]
        lines.append(f"| `search-keywords` | {sk['present']}/{t} | {sk['http_ok']}/{t} | — |")
        lines.append(f"| `search-results` | {sr['present']}/{t} | {sr['http_ok']}/{t} | {sr['with_products']}/{t} (products>0) |")
    else:
        rs = summary["run_sql"]; gv = summary["generate_viz"]
        lines.append(f"| `run-sql` | {rs['present']}/{t} | {rs['http_ok']}/{t} | {rs['with_rows']}/{t} (rows>0) |")
        lines.append(f"| `generate-viz` | {gv['present']}/{t} | {gv['http_ok']}/{t} | {gv['with_chart']}/{t} (chart) |")
    lines.append("")
    if not is_site_search:
        cs = summary["column_sync"]
        lines.append(f"### Column-name sync\n- Synced: **{cs['synced']}**, Unsynced: **{cs['unsynced']}**")
        lines.append("")

    if summary["failing_queries"]:
        lines.append("## 2. Failing queries")
        for f in summary["failing_queries"]:
            lines.append(f"- **q{f['id']:02d}** — {f['nl_query']}")
            for r in f["fail_reasons"]:
                lines.append(f"  - {r}")
        lines.append("")
    if summary["partial_queries"]:
        lines.append("## 3. Partial / warnings")
        for w in summary["partial_queries"]:
            lines.append(f"- **q{w['id']:02d}** — {w['nl_query']}")
            for r in w["warn_reasons"]:
                lines.append(f"  - {r}")
        lines.append("")
    if summary["timeout_queries"]:
        lines.append("## 3a. Timed-out queries")
        for t in summary["timeout_queries"]:
            lines.append(f"- **q{t['id']:02d}** — {t['nl_query']}  (on `{t['timed_out_on']}`, {t.get('duration_ms','?')} ms)")
        lines.append("")

    lines.append("## 4. Per-query detail")
    for r in results:
        lines.append(f"### q{r['id']:02d} — {r['nl_query']}")
        lines.append(f"- Status: `{r['overall_status']}` — Duration: {r.get('total_duration_ms')} ms")
        v = r.get("validations", {}) or {}
        if is_site_search:
            sk_call = r.get("search_keywords_call") or {}
            sr_call = r.get("search_results_call") or {}
            lines.append(f"- search-keywords: `{sk_call.get('url','-')}` HTTP {sk_call.get('status','n/a')}, returned {v.get('search_keywords_count','?')} keyword(s)")
            lines.append(f"- search-results: `{sr_call.get('url','-')}` HTTP {sr_call.get('status','n/a')}, returned {v.get('search_results_count','?')} product(s)")
        else:
            rs_call = r.get("run_sql_call") or {}
            gv_call = r.get("generate_viz_call") or {}
            lines.append(f"- run-sql: `{rs_call.get('url','-')}` HTTP {rs_call.get('status','n/a')}, columns={v.get('run_sql_columns')}, rows={v.get('run_sql_row_count')}")
            lines.append(f"- generate-viz: `{gv_call.get('url','-')}` HTTP {gv_call.get('status','n/a')}, chart_type={v.get('generate_viz_chart_type')}, axes=({v.get('generate_viz_x_axis')}, {v.get('generate_viz_y_axis')})")
            lines.append(f"- columns_synced: {v.get('columns_synced_run_sql_vs_generate_viz')}")
        if v.get("fail_reasons"):
            lines.append(f"- fail: {v['fail_reasons']}")
        if v.get("warn_reasons"):
            lines.append(f"- warn: {v['warn_reasons']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
HTML_TMPL = """<!doctype html>
<html><head>
<meta charset="utf-8"><title>Skylar IQ QA Report</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1200px;margin:24px auto;padding:0 20px;color:#222}}
 h1,h2,h3{{color:#1a3a6e}}
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
 .meta{{color:#555;font-size:12px}}
 img.screenshot{{max-width:100%;border:1px solid #ddd;margin:6px 0}}
 h4{{margin:10px 0 4px;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}}
 .card{{background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:10px}}
 .num{{font-size:26px;font-weight:700;color:#1a3a6e}}
</style></head>
<body>
<h1>Skylar IQ {report_title_suffix} — Automation QA Report</h1>
<p class="meta">Generated: {generated_at}</p>

<h2>1. Executive Summary</h2>
<div class="grid">
  <div class="card"><div class="num">{total}</div>Total queries</div>
  <div class="card"><div class="num">{pass_n}</div>PASS</div>
  <div class="card"><div class="num">{partial_n}</div>PARTIAL</div>
  <div class="card"><div class="num">{fail_n}</div>FAIL</div>
  <div class="card"><div class="num">{timeout_n}</div>TIMEOUT</div>
  <div class="card"><div class="num">{avg_ms} ms</div>Avg</div>
  <div class="card"><div class="num">{max_ms} ms</div>Max</div>
</div>

<h3>API health</h3>
{api_health_table}

<h2>2. Failing queries ({fail_n})</h2>{fail_list}
<h2>3. Partial / warnings ({partial_n})</h2>{partial_list}
<h2>3a. Timed-out queries ({timeout_n})</h2>{timeout_list}

<h2>4. Per-query detail</h2>
{per_query}
</body></html>
"""


# Header keys whose values may contain credentials — replaced with ***redacted***
# before rendering. Kept lowercase; matched as substring.
SENSITIVE_HEADER_HINTS = (
    "authorization", "cookie", "set-cookie", "x-csrf-token",
    "x-api-key", "x-auth-token", "jsessionid",
)


def _sanitize_headers(headers: Any) -> dict[str, str]:
    """Return a copy of headers with credential-bearing values redacted."""
    if not isinstance(headers, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        if any(h in str(k).lower() for h in SENSITIVE_HEADER_HINTS):
            out[str(k)] = "***redacted***"
        else:
            out[str(k)] = str(v)
    return out


def _format_body(body: Any, limit: int = 8000) -> str:
    """Pretty-print a request/response body for inclusion in <pre>."""
    if body is None:
        return "(no body)"
    try:
        s = body if isinstance(body, str) else json.dumps(body, indent=2, default=str)
    except Exception:
        s = str(body)
    if len(s) > limit:
        s = s[:limit] + f"\n\n… [truncated, original length {len(s)} chars]"
    return s


def _render_call_block(label: str, call: dict[str, Any] | None,
                       description: str = "") -> str:
    """Render one captured network call. Shows request side always (so timeout
    cases still expose what was sent) and the response side if received."""
    if not call or not call.get("url"):
        return (
            f"<details><summary><b>{html.escape(label)}</b> "
            f"<span class='meta'>not captured</span></summary>"
            f"{('<p class=' + chr(34) + 'meta' + chr(34) + '>' + html.escape(description) + '</p>') if description else ''}"
            f"<p class='meta'>The runner did not see a {html.escape(label)} "
            f"call for this query.</p></details>"
        )
    status = call.get("status")
    has_response = status is not None
    is_ok = bool(status and 200 <= status < 300)
    status_color = "#1a8a3a" if is_ok else "#c62828"
    if has_response:
        status_html = f"HTTP <b style='color:{status_color}'>{status}</b>"
    else:
        status_html = "<span class='badge TIMEOUT'>no response</span>"
    summary_html = (
        f"<b>{html.escape(label)}</b> — "
        f"<code>{html.escape(str(call.get('method','')))} "
        f"{html.escape(str(call.get('url','')))}</code> → "
        f"{status_html} "
        f"({call.get('duration_ms','-')} ms)"
    )
    req_headers = _sanitize_headers(call.get("request_headers") or {})
    req_body = _format_body(call.get("request_post_data"))
    resp_headers = _sanitize_headers(call.get("response_headers") or {})
    resp_body = _format_body(call.get("response_body"), limit=12000)
    open_attr = "" if is_ok else "open"
    no_resp_warning = ""
    if not has_response:
        failure = call.get("failure")
        no_resp_warning = (
            "<p style='background:#fff7e6; border-left:3px solid #d49a00; "
            "padding:8px 12px; margin:8px 0; border-radius:4px'>"
            "<b>Request was sent but no response was received.</b> "
            "Headers and body below are what the tool actually sent."
            + (f" <br><b>Failure:</b> <code>{html.escape(str(failure))}</code>" if failure else "")
            + "</p>"
        )
    return f"""
<details {open_attr}>
<summary>{summary_html}</summary>
{('<p class=' + chr(34) + 'meta' + chr(34) + '>' + html.escape(description) + '</p>') if description else ''}
{no_resp_warning}
<h4>Request headers (sanitized)</h4>
<pre>{html.escape(json.dumps(req_headers, indent=2))}</pre>
<h4>Request body</h4>
<pre>{html.escape(req_body)}</pre>
<h4>Response headers</h4>
<pre>{html.escape(json.dumps(resp_headers, indent=2)) if has_response else '(no response received)'}</pre>
<h4>Response body</h4>
<pre>{html.escape(resp_body) if has_response else '(no response received)'}</pre>
</details>
"""


def render_html(results: list[dict[str, Any]], summary: dict[str, Any], job_dir: Path) -> str:
    sb = summary["status_breakdown"]

    fail_list = "<ul>" + "".join(
        f"<li><b>q{f['id']:02d}</b> — {html.escape(f['nl_query'])}<ul>"
        + "".join(f"<li>{html.escape(r)}</li>" for r in f["fail_reasons"])
        + "</ul></li>"
        for f in summary["failing_queries"]
    ) + "</ul>" if summary["failing_queries"] else "<p><i>None.</i></p>"

    partial_list = "<ul>" + "".join(
        f"<li><b>q{w['id']:02d}</b> — {html.escape(w['nl_query'])}<ul>"
        + "".join(f"<li>{html.escape(r)}</li>" for r in w["warn_reasons"])
        + "</ul></li>"
        for w in summary["partial_queries"]
    ) + "</ul>" if summary["partial_queries"] else "<p><i>None.</i></p>"

    timeout_list = "<ul>" + "".join(
        f"<li><b>q{t['id']:02d}</b> — {html.escape(t['nl_query'])} <span class=\"meta\">(on <code>{html.escape(str(t['timed_out_on']))}</code>, {t.get('duration_ms','?')} ms)</span></li>"
        for t in summary["timeout_queries"]
    ) + "</ul>" if summary["timeout_queries"] else "<p><i>None.</i></p>"

    # Detect the test type from the first record that has any captured calls.
    # Site-search runs populate search_keywords_call / search_results_call;
    # SQL Agent runs populate run_sql_call / generate_viz_call.
    is_site_search = False
    for r in results:
        if r.get("search_keywords_call") or r.get("search_results_call"):
            is_site_search = True; break
        for c in r.get("calls") or []:
            if c.get("classification") in ("search-keywords", "search-results"):
                is_site_search = True; break
        if is_site_search: break

    parts: list[str] = []
    for r in results:
        v = r.get("validations", {}) or {}
        rs_call = r.get("run_sql_call") or {}
        gv_call = r.get("generate_viz_call") or {}
        sk_call = r.get("search_keywords_call") or {}
        sr_call = r.get("search_results_call") or {}
        status = r.get("overall_status", "PENDING")

        # Screenshots — emit as relative URLs ("screenshots/qNN_*.png"). When
        # the report is served at /jobs/<id>/report, the screenshot serving
        # route resolves these. When the report is opened from disk, the
        # files sit next to REPORT.html in the same job folder, so they load
        # with the same path.
        screenshot_imgs = ""
        for sp in (r.get("screenshots") or []):
            if not sp:
                continue
            try:
                rel = Path(sp).resolve().relative_to(job_dir.resolve())
            except Exception:
                rel = Path("screenshots") / Path(sp).name
            url = str(rel).replace("\\", "/")  # windows safety
            screenshot_imgs += (
                f'<div style="margin:8px 0">'
                f'<a href="{html.escape(url)}" target="_blank">{html.escape(Path(sp).name)}</a><br>'
                f'<img class="screenshot" src="{html.escape(url)}" alt="{html.escape(Path(sp).name)}">'
                f'</div>'
            )

        # Error trace (Playwright exception, etc.)
        error_block = ""
        if r.get("error"):
            error_block = (
                "<details open><summary><b style='color:#c62828'>"
                "Unhandled exception</b></summary>"
                f"<pre>{html.escape(str(r['error']))}</pre></details>"
            )

        # Runner notes — every selector tried, every fallback path taken
        notes = r.get("notes") or []
        notes_block = ""
        if notes:
            notes_block = (
                f"<details><summary><b>Runner notes</b> ({len(notes)})</summary>"
                "<ul>" + "".join(f"<li><code>{html.escape(str(n))}</code></li>"
                                 for n in notes) + "</ul></details>"
            )

        # All captured XHR/fetch traffic for this query (not just run-sql / viz)
        all_calls = r.get("calls") or []
        calls_table = ""
        if all_calls:
            rows = "".join(
                f"<tr><td>{i+1}</td>"
                f"<td><code>{html.escape(c.get('classification') or '-')}</code></td>"
                f"<td>{html.escape(c.get('method') or '-')}</td>"
                f"<td><code style='word-break:break-all'>"
                f"{html.escape(c.get('url') or '')}</code></td>"
                f"<td>{c.get('status') if c.get('status') is not None else '-'}</td>"
                f"<td>{c.get('duration_ms') or '-'} ms</td></tr>"
                for i, c in enumerate(all_calls)
            )
            calls_table = (
                f"<details><summary><b>All captured XHR/fetch calls</b> "
                f"({len(all_calls)})</summary>"
                "<table><tr><th>#</th><th>Class</th><th>Method</th><th>URL</th>"
                "<th>HTTP</th><th>Dur</th></tr>"
                f"{rows}</table></details>"
            )

        # Per-query summary rows — different fields for site_search vs sql_agent
        if is_site_search:
            summary_rows = (
                f"<tr><th>Status</th><td><span class='badge {status}'>{status}</span> &nbsp;Duration: {r.get('total_duration_ms','?')} ms &nbsp;Started: <span class='meta'>{html.escape(str(r.get('started_at') or '-'))}</span></td></tr>"
                f"<tr><th>search-keywords summary</th><td>HTTP {sk_call.get('status','-')}, returned {v.get('search_keywords_count','-')} keyword(s)</td></tr>"
                f"<tr><th>search-results summary</th><td>HTTP {sr_call.get('status','-')}, returned {v.get('search_results_count','-')} product(s)</td></tr>"
                f"<tr><th>fail/warn</th><td>{html.escape(json.dumps(v.get('fail_reasons')))} / {html.escape(json.dumps(v.get('warn_reasons')))}</td></tr>"
            )
            call_blocks = (
                f"{_render_call_block('search-keywords', sk_call, 'Autocomplete keywords endpoint — fires on every keystroke')}"
                f"{_render_call_block('search-results', sr_call, 'Product results endpoint — fires after keywords resolve')}"
            )
        else:
            summary_rows = (
                f"<tr><th>Status</th><td><span class='badge {status}'>{status}</span> &nbsp;Duration: {r.get('total_duration_ms','?')} ms &nbsp;Started: <span class='meta'>{html.escape(str(r.get('started_at') or '-'))}</span></td></tr>"
                f"<tr><th>run-sql summary</th><td>columns: <code>{html.escape(json.dumps(v.get('run_sql_columns')))}</code> rows: {v.get('run_sql_row_count','-')}</td></tr>"
                f"<tr><th>generate-viz summary</th><td>chart_type: <code>{html.escape(str(v.get('generate_viz_chart_type')))}</code>, axes (<code>{html.escape(str(v.get('generate_viz_x_axis')))}</code>, <code>{html.escape(str(v.get('generate_viz_y_axis')))}</code>)</td></tr>"
                f"<tr><th>columns synced</th><td><code>{v.get('columns_synced_run_sql_vs_generate_viz')}</code></td></tr>"
                f"<tr><th>fail/warn</th><td>{html.escape(json.dumps(v.get('fail_reasons')))} / {html.escape(json.dumps(v.get('warn_reasons')))}</td></tr>"
            )
            call_blocks = (
                f"{_render_call_block('generate-sql', r.get('generate_sql_call'), 'NL → SQL conversion (LLM call to celerantai.com)')}"
                f"{_render_call_block('run-sql', rs_call, 'SQL execution against the tenant database')}"
                f"{_render_call_block('generate-viz', gv_call, 'Chart generation (LLM call) — fired only when the user clicks Generate Visualization')}"
            )

        parts.append(f"""
<details {'open' if status != 'PASS' else ''}>
<summary><span class="badge {status}">{status}</span> <b>q{r['id']:02d}</b> — {html.escape(r['nl_query'])} <span class="meta">({r.get('total_duration_ms','?')} ms)</span></summary>
<table>{summary_rows}</table>
{error_block}
{call_blocks}
{notes_block}
{calls_table}
{('<details><summary><b>Screenshots</b> ('+str(len(r.get('screenshots') or []))+')</summary>'+screenshot_imgs+'</details>') if screenshot_imgs else ''}
</details>
""")

    # Build the right API-health table for the test type
    t = summary["total_queries"]
    if is_site_search:
        sk = summary["search_keywords"]; sr = summary["search_results"]
        api_health_table = (
            "<table>"
            "<tr><th>Endpoint</th><th>Captured</th><th>HTTP 2xx</th><th>Usable payload</th></tr>"
            f"<tr><td><code>search-keywords</code></td><td>{sk['present']}/{t}</td><td>{sk['http_ok']}/{t}</td><td>—</td></tr>"
            f"<tr><td><code>search-results</code></td><td>{sr['present']}/{t}</td><td>{sr['http_ok']}/{t}</td><td>{sr['with_products']}/{t} (products&gt;0)</td></tr>"
            "</table>"
        )
    else:
        rs = summary["run_sql"]; gv = summary["generate_viz"]; cs2 = summary["column_sync"]
        api_health_table = (
            "<table>"
            "<tr><th>Endpoint</th><th>Captured</th><th>HTTP 2xx</th><th>Usable payload</th></tr>"
            f"<tr><td><code>run-sql</code></td><td>{rs['present']}/{t}</td><td>{rs['http_ok']}/{t}</td><td>{rs['with_rows']}/{t} (rows&gt;0)</td></tr>"
            f"<tr><td><code>generate-viz</code></td><td>{gv['present']}/{t}</td><td>{gv['http_ok']}/{t}</td><td>{gv['with_chart']}/{t} (chart)</td></tr>"
            "</table>"
            f"<h3>Column-name sync</h3><p>Synced: <b>{cs2['synced']}</b> &nbsp;|&nbsp; Unsynced: <b>{cs2['unsynced']}</b></p>"
        )

    return HTML_TMPL.format(
        generated_at=summary["generated_at"],
        report_title_suffix="Site Search" if is_site_search else "SQL AI Engine",
        total=summary["total_queries"],
        pass_n=sb.get("PASS", 0),
        partial_n=sb.get("PARTIAL", 0),
        fail_n=sb.get("FAIL", 0),
        timeout_n=sb.get("TIMEOUT", 0),
        avg_ms=summary["performance_ms"]["avg"],
        max_ms=summary["performance_ms"]["max"],
        api_health_table=api_health_table,
        fail_list=fail_list,
        partial_list=partial_list,
        timeout_list=timeout_list,
        per_query="\n".join(parts),
    )


def generate(job_dir: str | Path) -> dict[str, str]:
    job_dir = Path(job_dir)
    results = load_results(job_dir)
    summary = summarize(results)

    summary_path = job_dir / "SUMMARY.json"
    md_path = job_dir / "REPORT.md"
    html_path = job_dir / "REPORT.html"

    summary_path.write_text(json.dumps(summary, indent=2))
    md_path.write_text(render_md(results, summary))
    html_path.write_text(render_html(results, summary, job_dir))

    return {
        "summary": str(summary_path),
        "markdown": str(md_path),
        "html": str(html_path),
    }


def cli() -> None:
    ap = argparse.ArgumentParser(prog="skylar-qa-report")
    ap.add_argument("--job-dir", required=True, help="Path to job output directory containing results/")
    args = ap.parse_args()
    out = generate(args.job_dir)
    for k, v in out.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    cli()
