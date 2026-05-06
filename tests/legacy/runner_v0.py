"""
Skylar IQ SQL Agent - Automated QA Runner
Logs into Celerant Back Office, navigates to SQL Agent, fires every NL query
from data/test_data.json, captures every network call (run-sql + generate-viz),
takes screenshots, and writes per-query result JSON files.

Final report generation is handled separately by tests/report.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    sync_playwright,
    Page,
    Request,
    Response,
    TimeoutError as PWTimeoutError,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "test_data.json"
SCREENSHOT_DIR = ROOT / "screenshots"
NETWORK_DIR = ROOT / "network_logs"
RESULTS_DIR = ROOT / "reports" / "results"

LOGIN_URL = "https://example.celerant.local:8443/backoffice/?mid=100"  # CHANGEME
USERNAME = "CHANGEME"  # NOTE: this v0 script is kept for reference only.
PASSWORD = "CHANGEME"  # NOTE: use the new generic app/runner.py instead — it takes config via CLI/web UI.

# URL fragments that mark calls we care about. Anything else is still captured
# under "other" but only these are considered the key API endpoints.
# Discovered endpoints during smoke testing:
#   POST https://celerantai.com/sql_agent/generate_sql/<tenant>/-1/<query-id>   (LLM->SQL)
#   POST https://example.celerant.local:8443/backoffice/report/run-sql                   (execute SQL)
#   POST https://example.celerant.local:8443/backoffice/report/generate-viz (presumed)   (build chart)
#   POST https://celerantai.com/sql_agent/generate_viz/...        (presumed)
RUN_SQL_HINTS = ("run-sql", "runsql", "execute-sql", "executesql")
GEN_VIZ_HINTS = ("generate-viz", "generateviz", "generate_viz", "/viz", "visualization", "chart-data")
GEN_SQL_HINTS = ("generate_sql", "generate-sql")  # tracked separately for the report

# Generous waits — the celerantai.com generate_sql LLM is slow and highly variable
# (90s-360s+ per query). Run-sql fires ~1ms after generate-sql returns. Generate-viz LLM is similar.
# 600s budget lets us catch even the slowest queries; polling loop returns as soon as call completes.
# Per-query budget — if either run-sql or generate-viz doesn't return within this window,
# the query is marked TIMEOUT and we move on (rather than blocking the suite for hours).
RUN_SQL_TIMEOUT_MS = 120_000  # 2 min
GEN_VIZ_TIMEOUT_MS = 120_000  # 2 min
PAGE_LOAD_TIMEOUT_MS = 60_000


# ---------------------------------------------------------------------------
# Data model for captured network calls
# ---------------------------------------------------------------------------
@dataclass
class CapturedCall:
    request_id: str
    url: str
    method: str
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    status: int | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    request_post_data: Any = None
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: Any = None
    response_body_preview: str | None = None
    failure: str | None = None
    classification: str = "other"  # run-sql | generate-viz | other


@dataclass
class QueryResult:
    id: int
    nl_query: str
    expected_sql: str
    started_at: str
    finished_at: str | None = None
    total_duration_ms: int | None = None
    screenshots: list[str] = field(default_factory=list)
    calls: list[CapturedCall] = field(default_factory=list)
    run_sql_call: CapturedCall | None = None
    generate_viz_call: CapturedCall | None = None
    validations: dict[str, Any] = field(default_factory=dict)
    overall_status: str = "PENDING"  # PASS | PARTIAL | FAIL | TIMEOUT
    notes: list[str] = field(default_factory=list)
    error: str | None = None
    timed_out: bool = False  # set True when run-sql or generate-viz exceeds budget


# ---------------------------------------------------------------------------
# Network capture
# ---------------------------------------------------------------------------
class NetworkRecorder:
    """Subscribes to page.on(...) and stores calls in a flat dict by request id."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self._calls: dict[str, CapturedCall] = {}
        self._order: list[str] = []
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_failed)

    @staticmethod
    def _classify(url: str) -> str:
        low = url.lower()
        if any(h in low for h in GEN_VIZ_HINTS):
            return "generate-viz"
        if any(h in low for h in RUN_SQL_HINTS):
            return "run-sql"
        if any(h in low for h in GEN_SQL_HINTS):
            return "generate-sql"
        return "other"

    def _on_request(self, req: Request) -> None:
        # Ignore static assets — only API/XHR/fetch
        if req.resource_type not in ("xhr", "fetch"):
            return
        rid = self._key(req)
        try:
            post = req.post_data
        except Exception:
            post = None
        try:
            post_json = req.post_data_json
        except Exception:
            post_json = None
        self._calls[rid] = CapturedCall(
            request_id=rid,
            url=req.url,
            method=req.method,
            started_at=now_iso(),
            request_headers=dict(req.headers),
            request_post_data=post_json if post_json is not None else post,
            classification=self._classify(req.url),
        )
        self._order.append(rid)

    def _on_response(self, resp: Response) -> None:
        rid = self._key(resp.request)
        call = self._calls.get(rid)
        if not call:
            return
        call.status = resp.status
        call.response_headers = dict(resp.headers)
        call.finished_at = now_iso()
        try:
            text = resp.text()
            call.response_body_preview = text[:500]
            try:
                call.response_body = json.loads(text)
            except Exception:
                call.response_body = text
        except Exception as e:
            call.response_body = f"<failed to read body: {e}>"

    def _on_failed(self, req: Request) -> None:
        rid = self._key(req)
        call = self._calls.get(rid)
        if not call:
            return
        call.failure = req.failure or "unknown"
        call.finished_at = now_iso()

    @staticmethod
    def _key(req: Request) -> str:
        return f"{id(req):x}-{req.method}-{req.url}"

    def snapshot_after(self, started_iso: str) -> list[CapturedCall]:
        """Return all calls whose started_at >= started_iso, in arrival order."""
        out: list[CapturedCall] = []
        for rid in self._order:
            c = self._calls.get(rid)
            if not c:
                continue
            if c.started_at >= started_iso:
                # Compute duration if possible
                if c.started_at and c.finished_at:
                    try:
                        s = datetime.fromisoformat(c.started_at)
                        e = datetime.fromisoformat(c.finished_at)
                        c.duration_ms = int((e - s).total_seconds() * 1000)
                    except Exception:
                        pass
                out.append(c)
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def slugify(text: str, maxlen: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return s[:maxlen] or "query"


def safe_screenshot(page: Page, path: Path) -> str | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
        return str(path.relative_to(ROOT))
    except Exception as e:
        print(f"  ! screenshot failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Login + navigation
# ---------------------------------------------------------------------------
def do_login(page: Page) -> None:
    print(f"[login] navigating {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="load", timeout=PAGE_LOAD_TIMEOUT_MS)
    page.wait_for_selector('#userid', timeout=20_000)

    # The login bundle uses RequireJS; wait until jQuery has bound the form submit handler
    # (this is when the AJAX-flow is wired up — without it the form does a native POST
    # without the &machineid= suffix and the server responds "Machine ID is empty").
    print("[login] waiting for jQuery submit handler to bind...")
    page.wait_for_function(
        """
        () => {
            if (!window.jQuery) return false;
            const events = jQuery._data(document.getElementById('loginform'), 'events');
            return !!(events && events.submit && events.submit.length > 0);
        }
        """,
        timeout=PAGE_LOAD_TIMEOUT_MS,
    )
    page.evaluate("() => window.localStorage.setItem('MACHINE_ID', '100')")
    page.wait_for_timeout(500)

    page.locator('#userid').fill(USERNAME)
    page.locator('#passwd').fill(PASSWORD)

    # Click the OK button — handler will read MACHINE_ID from localStorage and AJAX-POST
    # Use force=True in case any leftover jQuery-UI overlay still intercepts.
    try:
        page.locator('#btnLogin').click(timeout=5_000)
    except PWTimeoutError:
        page.locator('#btnLogin').click(force=True)

    # The handler does an AJAX POST and on success calls window.location = '/backoffice/wrmsscreen'
    try:
        page.wait_for_url(re.compile(r".*wrmsscreen.*"), timeout=PAGE_LOAD_TIMEOUT_MS)
    except PWTimeoutError:
        pass
    page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)

    url = page.url
    if "UserAuthenticationServlet" in url or url.endswith("?mid=100") or url.endswith("/backoffice/"):
        body = page.content()[:500]
        raise RuntimeError(f"Login failed — at {url}. Body: {body}")
    print(f"[login] success — at {url}")


SQL_AGENT_URL = "https://example.celerant.local:8443/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent"


def open_sql_agent(page: Page) -> Page:
    """Navigate directly to the SQL Agent SPA route (Setup > SQL Agent does the same thing)."""
    print(f"[nav] navigating to SQL Agent: {SQL_AGENT_URL}")
    page.goto(SQL_AGENT_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
    page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)
    page.wait_for_selector(
        'input[placeholder*="sales question" i], textarea[placeholder*="sales question" i]',
        timeout=60_000,
    )
    print(f"[nav] SQL Agent ready at {page.url}")
    return page


# ---------------------------------------------------------------------------
# Per-query execution
# ---------------------------------------------------------------------------
def _is_run_sql_url(url: str) -> bool:
    return any(h in url.lower() for h in RUN_SQL_HINTS)


def _is_gen_viz_url(url: str) -> bool:
    return any(h in url.lower() for h in GEN_VIZ_HINTS)


def submit_query(page: Page, recorder: NetworkRecorder, nl_query: str, qresult: QueryResult) -> None:
    """Type the question, send it, wait for run-sql via Playwright's event API,
    then click Generate Visualization (when the UI shows it) and wait for generate-viz."""
    box = page.locator(
        'input.greeting-input, input.chat-input, '
        'input[placeholder*="sales question" i], textarea[placeholder*="sales question" i]'
    ).first
    box.wait_for(state="visible", timeout=15_000)
    box.click()
    box.fill("")
    box.type(nl_query, delay=6)

    qresult.screenshots.append(
        safe_screenshot(page, SCREENSHOT_DIR / f"q{qresult.id:02d}_01_input.png") or ""
    )

    started_iso = now_iso()
    qresult.notes.append(f"submit_started={started_iso}")

    # Use Playwright's event-driven expect_response so we don't miss the response by polling-window
    # gaps. The send button is an <img class="greeting-send-btn"> in greeting state.
    send_selectors = [
        "img.greeting-send-btn",
        "img.chat-send-btn",
        '[class*="send-btn"]',
        '[class*="send-icon"]',
        ".chat-input-bar img",
        ".chat-input-bar button",
    ]

    def click_send() -> None:
        for sel in send_selectors:
            loc = page.locator(sel)
            try:
                n = loc.count()
            except Exception:
                n = 0
            if n:
                try:
                    loc.last.click(timeout=2500)
                    qresult.notes.append(f"send via {sel!r}")
                    return
                except Exception as e:
                    qresult.notes.append(f"send {sel!r} click failed: {e}")
        try:
            box.press("Enter")
            qresult.notes.append("send via Enter key (fallback)")
        except Exception as e:
            qresult.notes.append(f"send fallback Enter failed: {e}")

    run_sql_resp = None
    try:
        with page.expect_response(
            lambda r: _is_run_sql_url(r.url),
            timeout=RUN_SQL_TIMEOUT_MS,
        ) as info:
            click_send()
        run_sql_resp = info.value
        qresult.notes.append(
            f"run-sql response captured via expect_response: HTTP {run_sql_resp.status} {run_sql_resp.url}"
        )
    except PWTimeoutError:
        qresult.notes.append(f"run-sql TIMEOUT after {RUN_SQL_TIMEOUT_MS}ms — skipping query")
        qresult.timed_out = True
        qresult.validations["timed_out_on"] = "run-sql"
        return  # bail out — main loop will reload the SQL Agent page before next query
    except Exception as e:
        qresult.notes.append(f"run-sql expect_response error: {type(e).__name__}: {e}")

    # Allow recorder a moment to finish stamping finished_at on this response
    page.wait_for_timeout(1500)

    # Pull the recorder's CapturedCall for the run-sql URL we just saw
    if run_sql_resp is not None:
        for c in recorder.snapshot_after(started_iso):
            if c.classification == "run-sql" and c.url == run_sql_resp.url and c.finished_at:
                qresult.run_sql_call = c
                break
    if qresult.run_sql_call is None:
        # Fall back: any run-sql call after we submitted
        for c in recorder.snapshot_after(started_iso):
            if c.classification == "run-sql" and c.finished_at:
                qresult.run_sql_call = c
                break

    # Render-settle wait, then screenshot result state
    page.wait_for_timeout(1500)
    qresult.screenshots.append(
        safe_screenshot(page, SCREENSHOT_DIR / f"q{qresult.id:02d}_02_runsql.png") or ""
    )

    # Generate Visualization button is conditional — single-column results legitimately omit it.
    gv_btn = page.get_by_role("button", name=re.compile("Generate Visualization", re.I))
    try:
        gv_count = gv_btn.count()
    except Exception:
        gv_count = 0
    if gv_count == 0:
        gv_btn = page.locator('button:has-text("Generate Visualization"), :text-is("Generate Visualization")')
        try:
            gv_count = gv_btn.count()
        except Exception:
            gv_count = 0

    qresult.notes.append(f"Generate Visualization button count={gv_count}")
    if gv_count == 0:
        qresult.notes.append("Generate Visualization button not present (UI omits for non-chartable result)")
        qresult.validations["viz_button_present"] = False
        return
    qresult.validations["viz_button_present"] = True

    viz_started_iso = now_iso()
    gen_viz_resp = None
    try:
        with page.expect_response(
            lambda r: _is_gen_viz_url(r.url),
            timeout=GEN_VIZ_TIMEOUT_MS,
        ) as gv_info:
            try:
                target = gv_btn.last
                target.scroll_into_view_if_needed(timeout=3000)
                target.click(timeout=5000)
                qresult.notes.append("clicked Generate Visualization")
            except Exception as e:
                qresult.notes.append(f"Generate Visualization click failed: {e}")
                raise
        gen_viz_resp = gv_info.value
        qresult.notes.append(
            f"generate-viz response captured: HTTP {gen_viz_resp.status} {gen_viz_resp.url}"
        )
    except PWTimeoutError:
        qresult.notes.append(f"generate-viz TIMEOUT after {GEN_VIZ_TIMEOUT_MS}ms — skipping")
        qresult.timed_out = True
        qresult.validations["timed_out_on"] = "generate-viz"
    except Exception as e:
        qresult.notes.append(f"generate-viz expect_response error: {type(e).__name__}: {e}")

    page.wait_for_timeout(2000)

    if gen_viz_resp is not None:
        for c in recorder.snapshot_after(viz_started_iso):
            if c.classification == "generate-viz" and c.url == gen_viz_resp.url and c.finished_at:
                qresult.generate_viz_call = c
                break
    if qresult.generate_viz_call is None:
        for c in recorder.snapshot_after(viz_started_iso):
            if c.classification == "generate-viz" and c.finished_at:
                qresult.generate_viz_call = c
                break

    qresult.screenshots.append(
        safe_screenshot(page, SCREENSHOT_DIR / f"q{qresult.id:02d}_03_viz.png") or ""
    )


def wait_for_call(
    recorder: NetworkRecorder,
    started_iso: str,
    classification: str,
    timeout_ms: int,
) -> CapturedCall | None:
    """Poll the recorder until a finished call of the given classification appears."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for c in recorder.snapshot_after(started_iso):
            if c.classification == classification and c.finished_at:
                return c
        time.sleep(0.25)
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_query(qr: QueryResult) -> None:
    """Inspect captured calls and decide PASS / PARTIAL / FAIL."""
    v: dict[str, Any] = dict(qr.validations or {})  # preserve viz_button_present etc.

    # Fallback: if expect_response missed it, still pull the call from qr.calls
    if qr.run_sql_call is None:
        for c in qr.calls:
            if c.classification == "run-sql" and c.finished_at:
                qr.run_sql_call = c
                qr.notes.append("run-sql back-filled from calls list (post-timeout)")
                break
    if qr.generate_viz_call is None and v.get("viz_button_present"):
        for c in qr.calls:
            if c.classification == "generate-viz" and c.finished_at:
                qr.generate_viz_call = c
                qr.notes.append("generate-viz back-filled from calls list (post-timeout)")
                break

    # --- run-sql ---
    rs = qr.run_sql_call
    if not rs:
        v["run_sql_present"] = False
        v["run_sql_status_ok"] = False
        v["run_sql_has_rows"] = False
        v["run_sql_columns"] = []
    else:
        v["run_sql_present"] = True
        v["run_sql_status_ok"] = bool(rs.status and 200 <= rs.status < 300)
        rs_cols, rs_row_count, rs_has_rows = extract_table_shape(rs.response_body)
        v["run_sql_columns"] = rs_cols
        v["run_sql_empty_named_columns"] = sum(1 for c in rs_cols if not str(c).strip())
        v["run_sql_row_count"] = rs_row_count
        v["run_sql_has_rows"] = rs_has_rows
        v["run_sql_returned_sql"] = extract_returned_sql(rs.response_body)
        v["run_sql_response_keys"] = list(rs.response_body.keys()) if isinstance(rs.response_body, dict) else None

    # --- generate-viz ---
    gv = qr.generate_viz_call
    if not gv:
        v["generate_viz_present"] = False
        v["generate_viz_status_ok"] = False
        v["generate_viz_has_chart"] = False
    else:
        v["generate_viz_present"] = True
        v["generate_viz_status_ok"] = bool(gv.status and 200 <= gv.status < 300)
        v["generate_viz_response_keys"] = list(gv.response_body.keys()) if isinstance(gv.response_body, dict) else None
        chart_meta = inspect_chart_payload(gv.response_body)
        v.update({
            "generate_viz_has_chart": chart_meta["has_chart"],
            "generate_viz_chart_type": chart_meta["chart_type"],
            "generate_viz_chart_title": chart_meta["chart_title"],
            "generate_viz_x_axis": chart_meta["x_axis"],
            "generate_viz_y_axis": chart_meta["y_axis"],
            "generate_viz_x_axis_label": chart_meta["x_axis_label"],
            "generate_viz_y_axis_label": chart_meta["y_axis_label"],
            "generate_viz_columns": chart_meta["columns"],
            "generate_viz_data_points": chart_meta["data_points"],
            "generate_viz_visualizations_count": chart_meta["visualizations_count"],
        })

    # --- column sync ---
    rs_cols_norm = [c.lower() for c in (v.get("run_sql_columns") or [])]
    gv_cols_norm = [c.lower() for c in (v.get("generate_viz_columns") or [])]
    if rs_cols_norm and gv_cols_norm:
        synced = set(rs_cols_norm).issubset(set(gv_cols_norm)) or set(gv_cols_norm).issubset(set(rs_cols_norm))
        v["columns_synced_run_sql_vs_generate_viz"] = synced
        v["column_intersection"] = sorted(set(rs_cols_norm) & set(gv_cols_norm))
        v["column_only_in_run_sql"] = sorted(set(rs_cols_norm) - set(gv_cols_norm))
        v["column_only_in_generate_viz"] = sorted(set(gv_cols_norm) - set(rs_cols_norm))
    else:
        v["columns_synced_run_sql_vs_generate_viz"] = None

    qr.validations = v

    # --- overall status ---
    fails: list[str] = []
    warns: list[str] = []
    if not v.get("run_sql_present"):
        fails.append("run-sql call missing")
    elif not v.get("run_sql_status_ok"):
        fails.append(f"run-sql HTTP {qr.run_sql_call.status if qr.run_sql_call else 'n/a'}")
    elif not v.get("run_sql_has_rows"):
        warns.append("run-sql returned no rows")

    viz_button_present = qr.validations.get("viz_button_present")
    if viz_button_present is False:
        # UI legitimately hides the button for non-chartable results — record as INFO not FAIL
        qr.validations["viz_skipped_reason"] = "Generate Visualization button not rendered (single-column / non-chartable result)"
    elif not v.get("generate_viz_present"):
        fails.append("generate-viz call missing")
    elif not v.get("generate_viz_status_ok"):
        fails.append(f"generate-viz HTTP {qr.generate_viz_call.status if qr.generate_viz_call else 'n/a'}")
    elif not v.get("generate_viz_has_chart"):
        warns.append("generate-viz returned no usable chart payload")

    if v.get("columns_synced_run_sql_vs_generate_viz") is False:
        warns.append("columns differ between run-sql and generate-viz")
    if v.get("run_sql_empty_named_columns"):
        warns.append(f"run-sql returned {v['run_sql_empty_named_columns']} column(s) with empty/missing name (SQL aliasing bug)")

    if qr.timed_out:
        qr.overall_status = "TIMEOUT"
    elif fails:
        qr.overall_status = "FAIL"
    elif warns:
        qr.overall_status = "PARTIAL"
    else:
        qr.overall_status = "PASS"

    qr.validations["fail_reasons"] = fails
    qr.validations["warn_reasons"] = warns


def extract_table_shape(body: Any) -> tuple[list[str], int, bool]:
    """Best-effort extraction of column names + row count from a JSON body."""
    cols: list[str] = []
    row_count = 0
    if isinstance(body, dict):
        # Common shapes: {data: [...]}, {rows: [...]}, {result: [...]}, {columns: [...], rows: [...]}
        if isinstance(body.get("columns"), list) and body["columns"]:
            cols = [str(c) for c in body["columns"]]
        for k in ("data", "rows", "result", "results", "records"):
            v = body.get(k)
            if isinstance(v, list):
                row_count = len(v)
                if v and isinstance(v[0], dict) and not cols:
                    cols = list(v[0].keys())
                break
    elif isinstance(body, list) and body:
        row_count = len(body)
        if isinstance(body[0], dict):
            cols = list(body[0].keys())
    return cols, row_count, row_count > 0


def extract_returned_sql(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for k in ("sql", "query", "sql_query", "executed_sql", "generated_sql"):
        if isinstance(body.get(k), str):
            return body[k]
    return None


def inspect_chart_payload(body: Any) -> dict[str, Any]:
    """Extract chart metadata from the Skylar IQ generate-visualization response.

    Real shape (observed):
      { responseHeader: {...}, responseBody: { data: { visualizations: [
          { chart_type: "bar", chart_title: "...", chart_config: {
                x_axis: { label: "...", columns: ["..."] },
                y_axis: { label: "...", columns: ["..."] },
                ... } } ] } } }
    """
    out: dict[str, Any] = {
        "has_chart": False,
        "chart_type": None,
        "chart_title": None,
        "x_axis_label": None,
        "y_axis_label": None,
        "x_axis_columns": [],
        "y_axis_columns": [],
        "x_axis": None,
        "y_axis": None,
        "columns": [],
        "data_points": 0,
        "visualizations_count": 0,
    }
    if not isinstance(body, dict):
        return out

    # Walk the canonical Skylar IQ shape first
    visualizations = None
    rb = body.get("responseBody")
    if isinstance(rb, dict):
        d = rb.get("data")
        if isinstance(d, dict):
            v = d.get("visualizations")
            if isinstance(v, list):
                visualizations = v

    # Fall back to any top-level visualizations array
    if visualizations is None and isinstance(body.get("visualizations"), list):
        visualizations = body["visualizations"]

    if visualizations:
        out["visualizations_count"] = len(visualizations)
        first = visualizations[0]
        if isinstance(first, dict):
            out["chart_type"] = first.get("chart_type") or first.get("type")
            out["chart_title"] = first.get("chart_title") or first.get("title")
            cfg = first.get("chart_config") or {}
            xa = cfg.get("x_axis") or {}
            ya = cfg.get("y_axis") or {}
            out["x_axis_label"] = xa.get("label")
            out["y_axis_label"] = ya.get("label")
            x_cols = xa.get("columns") or []
            y_cols = ya.get("columns") or []
            out["x_axis_columns"] = list(x_cols) if isinstance(x_cols, list) else []
            out["y_axis_columns"] = list(y_cols) if isinstance(y_cols, list) else []
            out["x_axis"] = out["x_axis_columns"][0] if out["x_axis_columns"] else None
            out["y_axis"] = out["y_axis_columns"][0] if out["y_axis_columns"] else None
            out["columns"] = out["x_axis_columns"] + out["y_axis_columns"]
        out["has_chart"] = bool(out["chart_type"] or out["columns"])
        return out

    # Last-resort generic walk
    chart = body.get("chart") or body.get("visualization") or body.get("viz")
    if isinstance(chart, dict):
        out["chart_type"] = chart.get("type") or chart.get("chartType") or chart.get("chart_type")
        out["x_axis"] = chart.get("x") or chart.get("xAxis") or chart.get("x_axis") or chart.get("xKey")
        out["y_axis"] = chart.get("y") or chart.get("yAxis") or chart.get("y_axis") or chart.get("yKey")
        for k in ("data", "series", "rows", "points"):
            v = chart.get(k)
            if isinstance(v, list) and v:
                out["data_points"] = len(v)
                if isinstance(v[0], dict):
                    out["columns"] = list(v[0].keys())
                break
        out["has_chart"] = bool(out["chart_type"] or out["data_points"] or out["columns"])
    return out


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_query_result(qr: QueryResult) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    # Convert dataclass tree to dict (handle CapturedCall nesting)
    payload = asdict(qr)
    out = RESULTS_DIR / f"q{qr.id:02d}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    # Also write a separate flat network log
    net_out = NETWORK_DIR / f"q{qr.id:02d}_calls.json"
    net_out.write_text(json.dumps([asdict(c) for c in qr.calls], indent=2, default=str))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(limit: int | None = None, headed: bool = True) -> None:
    test_data = json.loads(DATA_FILE.read_text())
    if limit:
        test_data = test_data[:limit]
    print(f"[run] {len(test_data)} queries to execute")

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        recorder = NetworkRecorder(page)

        do_login(page)
        agent_page = open_sql_agent(page)
        if agent_page is not page:
            page = agent_page
            recorder = NetworkRecorder(page)
            print(f"[run] re-bound network recorder to SQL Agent tab")

        all_results: list[QueryResult] = []
        for row in test_data:
            qr = QueryResult(
                id=row["id"],
                nl_query=row["natural_language_query"],
                expected_sql=row.get("expected_sql", ""),
                started_at=now_iso(),
            )
            print(f"\n[q{qr.id:02d}] {qr.nl_query[:80]}")
            try:
                start_iso = now_iso()
                submit_query(page, recorder, qr.nl_query, qr)
                qr.calls = recorder.snapshot_after(start_iso)
                validate_query(qr)
            except Exception as e:
                qr.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                qr.overall_status = "FAIL"
                qr.notes.append(f"unhandled exception: {e}")
                # Try a recovery screenshot
                qr.screenshots.append(
                    safe_screenshot(page, SCREENSHOT_DIR / f"q{qr.id:02d}_99_error.png") or ""
                )
            qr.finished_at = now_iso()
            try:
                qr.total_duration_ms = int(
                    (datetime.fromisoformat(qr.finished_at) - datetime.fromisoformat(qr.started_at))
                    .total_seconds() * 1000
                )
            except Exception:
                pass
            print(f"[q{qr.id:02d}] {qr.overall_status} ({qr.total_duration_ms} ms)")
            save_query_result(qr)
            all_results.append(qr)

            # If the query timed out, the page is in a "submitting" state with the LLM still pending.
            # Reload the SQL Agent route so the next query has a clean input box.
            if qr.timed_out:
                try:
                    print(f"[q{qr.id:02d}] timed out — reloading SQL Agent page to recover")
                    page.goto(SQL_AGENT_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                    page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)
                    page.wait_for_selector(
                        'input[placeholder*="sales question" i], textarea[placeholder*="sales question" i]',
                        timeout=30_000,
                    )
                except Exception as e:
                    print(f"[q{qr.id:02d}] reload failed: {e} — continuing anyway")

        # Aggregate
        agg = ROOT / "reports" / "all_results.json"
        agg.write_text(json.dumps([asdict(r) for r in all_results], indent=2, default=str))
        print(f"\n[done] aggregate: {agg}")

        context.close()
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Run only first N queries")
    ap.add_argument("--headless", action="store_true", help="Run headless (default headed)")
    args = ap.parse_args()
    try:
        run(limit=args.limit, headed=not args.headless)
    except KeyboardInterrupt:
        print("\n[abort] interrupted")
        sys.exit(130)
