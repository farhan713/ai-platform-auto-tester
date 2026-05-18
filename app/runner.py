"""
Generic Skylar IQ SQL Agent QA runner.

Drives the Celerant Back Office "Skylar IQ" SQL Agent for any tenant:
  1. Login at <login_url> with <username>/<password>, injecting <machine_id>
     into localStorage so the server-side "Machine ID" check passes.
  2. Navigate to the SQL Agent SPA route.
  3. For every natural-language question in the supplied list:
        a) Type the question
        b) Click the send button
        c) Wait (event-driven) for the run-sql response
        d) If the UI shows a "Generate Visualization" button, click it
        e) Wait for the generate-viz response
        f) Validate everything and persist a per-query JSON
  4. Aggregate results to <output_dir>/all_results.json.

Config is a dict (or argparse Namespace). See `RunConfig` for the schema.
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
from typing import Any, Callable
from urllib.parse import urljoin, urlparse, urlunparse

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
@dataclass
class RunConfig:
    """Per-run configuration. Build one of these and pass to run() or run_sitesearch()."""
    login_url: str                 # SQL Agent: login page URL.  Site Search: target page URL with #searchbox
    username: str                  # SQL Agent only — leave "" for site search
    password: str                  # SQL Agent only — leave "" for site search
    questions: list[dict[str, Any]]  # [{id, natural_language_query, expected_sql?}]
    output_dir: Path
    test_type: str = "sql_agent"   # 'sql_agent' or 'site_search'
    machine_id: str = "100"
    sql_agent_path: str = "/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent"
    search_input_selector: str = "#searchbox"   # site_search only
    # Optional site-search runtime override. When set, the runner injects an
    # init-script that intercepts the page's ssLibrary.init(...) call and
    # substitutes these values — letting QA test any tenant without editing
    # the hosted index.html. Keys: org_id, console_url, server_url, image_url,
    # not_found_image_url, jwt_user, jwt_pass.
    site_search_config: dict[str, str] | None = None
    run_sql_timeout_ms: int = 120_000
    gen_viz_timeout_ms: int = 120_000
    page_load_timeout_ms: int = 60_000
    headless: bool = True
    on_event: Callable[[str], None] | None = None
    should_stop: Callable[[], bool] | None = None


# Endpoint URL substring hints (used to classify each XHR/fetch we observe)
RUN_SQL_HINTS = ("run-sql", "runsql", "execute-sql", "executesql")
GEN_VIZ_HINTS = ("generate-viz", "generateviz", "generate_viz", "/viz", "visualization", "chart-data")
GEN_SQL_HINTS = ("generate_sql", "generate-sql")
# Site Search classifications
SS_KEYWORDS_HINTS = ("/search_keywords/",)
SS_RESULTS_HINTS  = ("/search_results/", "/search_multi_keyword_and_results/", "/user_search_result")
SS_AUTH_HINTS     = ("/organization_validation/", "/search_ui_styling_info")
SQL_AGENT_INPUT_SELECTOR = (
    'input.greeting-input, input.chat-input, '
    'input[placeholder*="sales question" i], textarea[placeholder*="sales question" i]'
)


# ---------------------------------------------------------------------------
# Captured network call + per-query result
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
    classification: str = "other"


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
    generate_sql_call: CapturedCall | None = None
    generate_viz_call: CapturedCall | None = None
    # Site Search runner populates these instead of run_sql_call / generate_viz_call:
    search_keywords_call: CapturedCall | None = None
    search_results_call: CapturedCall | None = None
    validations: dict[str, Any] = field(default_factory=dict)
    overall_status: str = "PENDING"  # PASS | PARTIAL | FAIL | TIMEOUT
    notes: list[str] = field(default_factory=list)
    error: str | None = None
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _classify(url: str) -> str:
    low = url.lower()
    # Site search classifications first — more specific URL substrings.
    if any(h in low for h in SS_KEYWORDS_HINTS):
        return "search-keywords"
    if any(h in low for h in SS_RESULTS_HINTS):
        return "search-results"
    if any(h in low for h in SS_AUTH_HINTS):
        return "search-auth"
    if any(h in low for h in GEN_VIZ_HINTS):
        return "generate-viz"
    if any(h in low for h in RUN_SQL_HINTS):
        return "run-sql"
    if any(h in low for h in GEN_SQL_HINTS):
        return "generate-sql"
    return "other"


def _is_run_sql_url(url: str) -> bool:
    return any(h in url.lower() for h in RUN_SQL_HINTS)


def _is_gen_viz_url(url: str) -> bool:
    return any(h in url.lower() for h in GEN_VIZ_HINTS)


def _is_search_keywords_url(url: str) -> bool:
    return any(h in url.lower() for h in SS_KEYWORDS_HINTS)


def _is_search_results_url(url: str) -> bool:
    return any(h in url.lower() for h in SS_RESULTS_HINTS)


def derive_sql_agent_url(login_url: str, sql_agent_path: str) -> str:
    """Build the SQL Agent SPA URL from the login URL's origin + the configured path."""
    parsed = urlparse(login_url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    if sql_agent_path.startswith("http"):
        return sql_agent_path
    if not sql_agent_path.startswith("/"):
        sql_agent_path = "/" + sql_agent_path
    return origin + sql_agent_path


class StopRequested(Exception):
    """Raised when a user clicks Stop while a long-running wait is in flight.

    The original blocking calls (page.expect_response with 600s timeout)
    could not be cancelled from another thread, so the Stop button only
    fired *between* queries. That meant "Stopping…" sat for up to 10
    minutes if Stop was clicked while waiting on run-sql for a slow tenant.
    """


def _wait_for_response_interruptible(
    page: "Page",
    predicate,
    timeout_ms: int,
    *,
    should_stop,
    click_fn=None,
    poll_interval_ms: int = 1000,
):
    """Wait for the first response matching ``predicate``, but check
    ``should_stop()`` every ``poll_interval_ms`` so the run can be aborted
    promptly. Returns the captured Response, or raises StopRequested /
    PWTimeoutError.

    Why we don't use page.expect_response: that context manager blocks for
    the full timeout in one go. We need to interleave stop-flag checks. We
    register a page.on("response") listener BEFORE firing ``click_fn`` (so
    we don't race the response), then poll in short ticks.
    """
    captured: dict[str, Any] = {"resp": None}

    def _on_response(resp):
        if captured["resp"] is None:
            try:
                if predicate(resp):
                    captured["resp"] = resp
            except Exception:
                pass

    page.on("response", _on_response)
    try:
        if click_fn is not None:
            click_fn()
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            if should_stop and should_stop():
                raise StopRequested("user requested stop while waiting for response")
            if captured["resp"] is not None:
                return captured["resp"]
            # page.wait_for_timeout uses Playwright's event loop, which lets
            # the response handler fire while we're sleeping. Don't replace
            # this with time.sleep — that blocks Chromium's event delivery
            # to our process.
            remaining_ms = max(50, min(poll_interval_ms,
                                       int((deadline - time.monotonic()) * 1000)))
            try:
                page.wait_for_timeout(remaining_ms)
            except Exception:
                # If the page died mid-wait (TargetClosedError), let the
                # caller's existing handlers see it.
                if captured["resp"] is not None:
                    return captured["resp"]
                raise
        # Timed out without a response.
        raise PWTimeoutError(
            f"interruptible wait: no matching response within {timeout_ms}ms"
        )
    finally:
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# NetworkRecorder
# ---------------------------------------------------------------------------
class NetworkRecorder:
    """Subscribes to page.on('request' / 'response' / 'requestfailed') and records every XHR/fetch."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self._calls: dict[str, CapturedCall] = {}
        self._order: list[str] = []
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_failed)

    def _on_request(self, req: Request) -> None:
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
            classification=_classify(req.url),
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
        out: list[CapturedCall] = []
        for rid in self._order:
            c = self._calls.get(rid)
            if not c:
                continue
            if c.started_at >= started_iso:
                if c.started_at and c.finished_at:
                    try:
                        s = datetime.fromisoformat(c.started_at)
                        e = datetime.fromisoformat(c.finished_at)
                        c.duration_ms = int((e - s).total_seconds() * 1000)
                    except Exception:
                        pass
                out.append(c)
        return out

    def prune_before(self, cutoff_iso: str) -> int:
        """Drop calls that started before ``cutoff_iso``.

        Without this, ``self._calls`` accumulates every XHR/fetch (with full
        parsed JSON bodies) for the entire run. After 5-6 SQL Agent queries a
        single ``run-sql`` response can be megabytes, and the heap pressure
        crashes the Chromium tab — which then makes every subsequent question
        fail with ``TargetClosedError`` because the page is dead. Calling
        this at the start of each iteration keeps memory bounded.
        """
        keep_calls: dict[str, CapturedCall] = {}
        keep_order: list[str] = []
        dropped = 0
        for rid in self._order:
            c = self._calls.get(rid)
            if not c:
                continue
            if c.started_at >= cutoff_iso:
                keep_calls[rid] = c
                keep_order.append(rid)
            else:
                dropped += 1
        self._calls = keep_calls
        self._order = keep_order
        return dropped

    def detach(self) -> None:
        """Detach event listeners — call before discarding a dead page so
        Playwright can release the underlying CDP session."""
        try:
            self.page.remove_listener("request", self._on_request)
            self.page.remove_listener("response", self._on_response)
            self.page.remove_listener("requestfailed", self._on_failed)
        except Exception:
            pass


# Celerant URL fixer — same mechanism as in runner_sitesearch.py. The Celerant
# back-office SPA also calls /sql_agent/generate_sql/<id>/-1/<token> which now
# requires a trailing slash. Without this fix, the call gets 307'd and the
# response never lands in the form the SPA expects, so the run-sql call
# never fires and our runner times out.
_CELERANT_URL_FIXER = r"""
(() => {
  // VERIFIED endpoints that need trailing slash. Adding it elsewhere causes
  // 404s (run-sql is the canonical example: /backoffice/report/run-sql works,
  // /backoffice/report/run-sql/ returns 404). Be conservative.
  const NEEDS_SLASH = [
    /\/console\/organization_validation\/[^\/?#]+$/,   // JWT exchange
    /\/sql_agent\/generate_sql\/[^?#]*[^\/]$/,          // NL → SQL LLM call
  ];
  function fixURL(url) {
    if (typeof url !== 'string') return url;
    if (/[?#]/.test(url)) return url;
    for (const re of NEEDS_SLASH) if (re.test(url)) return url + '/';
    return url;
  }
  const _origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    if (typeof input === 'string') input = fixURL(input);
    else if (input && typeof input === 'object' && 'url' in input) {
      const fixed = fixURL(input.url);
      if (fixed !== input.url) input = new Request(fixed, input);
    }
    return _origFetch(input, init);
  };
  const _origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    return _origOpen.call(this, method, fixURL(url), ...rest);
  };
  console.log('[skylar-qa] Celerant URL fixer: trailing slash for /console/organization_validation/ + /sql_agent/generate_sql/ only');
})();
"""


# ---------------------------------------------------------------------------
# Login + navigation
# ---------------------------------------------------------------------------
def do_login(page: Page, cfg: RunConfig, log: Callable[[str], None]) -> None:
    # Install the fetch/XHR URL fixer BEFORE navigating so it's in place when
    # the back-office SPA's bundles register their first auth fetches.
    page.add_init_script(_CELERANT_URL_FIXER)
    log("[init] Celerant URL fixer installed")

    log(f"[login] navigating {cfg.login_url}")
    # 'domcontentloaded' returns once HTML is parsed; we don't need every
    # image/font to load before interacting. The previous 'load' event added
    # ~30-60s on the Celerant login page (lots of static assets).
    try:
        page.goto(cfg.login_url, wait_until="domcontentloaded", timeout=cfg.page_load_timeout_ms)
    except Exception as e:
        _save_setup_forensics(page, cfg, "login_goto", log)
        msg = (
            "Login page is not accessible. Check the Login URL, VPN/network access, "
            f"and whether the tenant is reachable from this server. URL: {cfg.login_url}"
        )
        log(f"[page-error] {msg}")
        raise RuntimeError(msg) from e
    try:
        page.wait_for_selector("#userid", timeout=20_000)
    except PWTimeoutError as e:
        _save_setup_forensics(page, cfg, "login_userid", log)
        msg = (
            "Login page opened, but the expected username field (#userid) was not found. "
            "This usually means the URL is not the Celerant Back Office login page, "
            "the page is blocked, or the login screen changed."
        )
        log(f"[login-error] {msg}")
        raise RuntimeError(msg) from e

    # Wait for jQuery's submit handler to be wired by RequireJS — without it the form does a
    # native POST that omits machineid and the server returns "Machine ID is empty".
    log("[login] waiting for jQuery submit handler to bind")
    try:
        page.wait_for_function(
            """
            () => {
                if (!window.jQuery) return false;
                const events = jQuery._data(document.getElementById('loginform'), 'events');
                return !!(events && events.submit && events.submit.length > 0);
            }
            """,
            timeout=cfg.page_load_timeout_ms,
        )
    except PWTimeoutError as e:
        _save_setup_forensics(page, cfg, "login_jquery", log)
        msg = (
            "Login page loaded, but the login form did not finish initializing. "
            "The tenant page may be slow, blocked, or missing required scripts."
        )
        log(f"[login-error] {msg}")
        raise RuntimeError(msg) from e
    if cfg.machine_id:
        page.evaluate(
            "(mid) => window.localStorage.setItem('MACHINE_ID', mid)",
            cfg.machine_id,
        )
    page.wait_for_timeout(300)

    page.locator("#userid").fill(cfg.username)
    page.locator("#passwd").fill(cfg.password)
    try:
        page.locator("#btnLogin").click(timeout=5_000)
    except PWTimeoutError:
        page.locator("#btnLogin").click(force=True)

    # Wait for redirect after login (max 30s — the actual redirect happens
    # within ~5s on a healthy tenant). Don't fall back to networkidle: the
    # Celerant SPA polls heartbeats so the network is never idle, and we
    # were burning the full 60s timeout every run for no benefit.
    try:
        page.wait_for_url(re.compile(r".*wrmsscreen.*"), timeout=30_000)
    except PWTimeoutError:
        # Some tenants land elsewhere — fall through and verify by URL below
        pass

    url = page.url
    if "UserAuthenticationServlet" in url or url == cfg.login_url:
        _save_setup_forensics(page, cfg, "login_failed", log)
        body = page.content()[:300]
        msg = (
            "Login failed. Please verify username, password, Machine ID, and tenant URL. "
            f"The page stayed on the login/authentication screen: {url}"
        )
        log(f"[login-error] {msg}")
        raise RuntimeError(f"{msg}\nPage preview: {body}")
    log(f"[login] success — {url}")


# How long to wait for the SQL Agent chat input to render after navigation.
# Manual browsers benefit from cached JS chunks; the tool's headless Chromium
# does a cold load every run, talks to a tenant with a self-signed cert
# (extra TLS round trips), and waits on RequireJS to assemble dozens of
# modules before the SPA mounts. 180s is enough headroom for slow tenants
# without making genuine failures take forever to surface.
SQL_AGENT_READY_TIMEOUT_MS = 180_000


def _save_setup_forensics(page: Page, cfg: RunConfig, phase: str,
                          log: Callable[[str], None]) -> None:
    """Save screenshot + page HTML + URL/title when a setup-phase wait times out.

    Setup-phase failures (login, SQL Agent navigation) historically saved nothing
    — just a bare Playwright TimeoutError. That left us unable to tell whether
    the page rendered a different view, a modal, an error banner, or just hadn't
    finished loading. This function drops a screenshot AND the page HTML into
    the run's output dir so the next failure tells us exactly what the headless
    Chromium was seeing.
    """
    try:
        out = Path(cfg.output_dir) / "screenshots"
        out.mkdir(parents=True, exist_ok=True)
        shot_path = out / f"setup_{phase}_timeout.png"
        try:
            page.screenshot(path=str(shot_path), full_page=True)
            log(f"[forensics] saved screenshot: {shot_path.name}")
        except Exception as se:
            log(f"[forensics] screenshot failed: {se}")

        html_path = Path(cfg.output_dir) / f"setup_{phase}_page.html"
        try:
            html = page.content()
            html_path.write_text(html[:500_000])  # cap at 500 KB
            log(f"[forensics] saved page HTML ({len(html)} bytes) -> {html_path.name}")
        except Exception as ce:
            log(f"[forensics] page.content() failed: {ce}")

        try:
            log(f"[forensics] url={page.url!r} title={page.title()!r}")
        except Exception:
            pass
    except Exception as e:
        log(f"[forensics] unexpected error: {e}")


def open_sql_agent(page: Page, cfg: RunConfig, log: Callable[[str], None]) -> Page:
    target = derive_sql_agent_url(cfg.login_url, cfg.sql_agent_path)
    log(f"[nav] opening {target}")
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=cfg.page_load_timeout_ms)
    except Exception as e:
        _save_setup_forensics(page, cfg, "sql_agent_goto", log)
        msg = (
            "SQL Agent page is not accessible. Check the SQL Agent path, user permissions, "
            f"and network access. URL: {target}"
        )
        log(f"[page-error] {msg}")
        raise RuntimeError(msg) from e

    # Wait for the SPA's root element to mount before checking for the input.
    # On a cold-load headless Chromium the JS chunks take time to download +
    # parse + run; without this we sometimes hit the input selector wait
    # before any React component has rendered, then 60s wasn't enough.
    try:
        page.wait_for_function(
            "() => !!document.querySelector('#root, #app, body > div')"
            " && (document.body.innerText || '').length > 0",
            timeout=60_000,
        )
        log("[nav] SPA root mounted")
    except PWTimeoutError:
        # Not fatal — fall through to the input wait, which has its own
        # forensics. The SPA may use a non-standard root we don't recognise.
        log("[nav] SPA root wait timed out — continuing to input check")

    # Skip 'networkidle' here — the SPA polls heartbeats and never goes idle.
    # The wait_for_selector below is a deterministic ready signal.
    try:
        page.wait_for_selector(SQL_AGENT_INPUT_SELECTOR,
                               timeout=SQL_AGENT_READY_TIMEOUT_MS)
    except PWTimeoutError as e:
        _save_setup_forensics(page, cfg, "sql_agent_input", log)
        msg = (
            f"SQL Agent page opened, but the question input did not appear within "
            f"{SQL_AGENT_READY_TIMEOUT_MS // 1000} seconds. "
            "The account may not have SQL Agent access, the path may be wrong, "
            "or the page is stuck loading. A screenshot of what the tool saw "
            "has been saved alongside the run for diagnosis."
        )
        log(f"[page-error] {msg}")
        raise RuntimeError(msg) from e
    log("[nav] SQL Agent ready")
    return page


# ---------------------------------------------------------------------------
# Per-query
# ---------------------------------------------------------------------------
def submit_query(
    page: Page,
    recorder: NetworkRecorder,
    cfg: RunConfig,
    qresult: QueryResult,
    screenshot_dir: Path,
) -> None:
    def emit_activity(phase: str, message: str) -> None:
        if cfg.on_event:
            cfg.on_event(f"[activity] q{qresult.id:02d} {phase}: {message}")

    def wait_for_chat_input():
        box = page.locator(SQL_AGENT_INPUT_SELECTOR).first
        try:
            box.wait_for(state="visible", timeout=30_000)
            return box
        except PWTimeoutError as first_error:
            try:
                qresult.notes.append(f"chat input missing before submit; url={page.url!r}; title={page.title()!r}")
            except Exception:
                qresult.notes.append("chat input missing before submit; unable to read page url/title")
            missing_shot = _screenshot(
                page,
                screenshot_dir / f"q{qresult.id:02d}_00_missing_input.png",
            )
            if missing_shot:
                qresult.screenshots.append(missing_shot)

            target = derive_sql_agent_url(cfg.login_url, cfg.sql_agent_path)
            qresult.notes.append("chat input missing — reloading SQL Agent and retrying this question once")
            if cfg.on_event:
                cfg.on_event(
                    f"[recover-input-start] q{qresult.id:02d}: SQL Agent input disappeared. "
                    "Reloading page and retrying this question; timeout 60s. "
                    "Reason: the chat input was not visible before typing the question."
                )
            try:
                page.goto(target, wait_until="domcontentloaded", timeout=cfg.page_load_timeout_ms)
                page.wait_for_selector(SQL_AGENT_INPUT_SELECTOR, timeout=60_000)
                recovered_shot = _screenshot(
                    page,
                    screenshot_dir / f"q{qresult.id:02d}_00_recovered_input.png",
                )
                if recovered_shot:
                    qresult.screenshots.append(recovered_shot)
                qresult.notes.append("chat input recovered after SQL Agent reload")
                if cfg.on_event:
                    cfg.on_event(f"[recover-input-ok] q{qresult.id:02d}: SQL Agent input recovered; continuing run.")
                box = page.locator(SQL_AGENT_INPUT_SELECTOR).first
                box.wait_for(state="visible", timeout=15_000)
                return box
            except Exception as reload_error:
                if cfg.on_event:
                    cfg.on_event(
                        f"[recover-input-failed] q{qresult.id:02d}: SQL Agent input did not recover after reload."
                    )
                raise RuntimeError(
                    "SQL Agent chat input was missing, and reload did not recover it. "
                    f"Last URL: {getattr(page, 'url', '')}. "
                    f"Original wait error: {first_error}. Reload error: {reload_error}"
                ) from reload_error

    box = wait_for_chat_input()
    emit_activity("input", "SQL Agent input is visible; preparing question")
    # The chat input is disabled while the previous query is still being
    # processed by the SQL Agent. Without this wait, q02 onward fail with
    # "element is not enabled" because we click before the agent finishes.
    # Tolerate up to 90s — slow tenants can take that long between turns.
    try:
        page.wait_for_function(
            """
            () => {
                const el = document.querySelector(
                    'input.chat-input, input.greeting-input, '
                    + 'input[placeholder*="sales question" i], '
                    + 'textarea[placeholder*="sales question" i]'
                );
                return el && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
            }
            """,
            timeout=90_000,
        )
    except PWTimeoutError:
        qresult.notes.append("chat input still disabled after 90s — proceeding with force-click")
    try:
        box.click(timeout=5_000)
    except PWTimeoutError:
        # Last-ditch: force-click even if Playwright thinks it's disabled
        box.click(force=True)
        qresult.notes.append("clicked input with force=True")
    box.fill("")
    box.type(qresult.nl_query, delay=6)
    emit_activity("submit", "Question typed; sending to SQL Agent")

    qresult.screenshots.append(_screenshot(page, screenshot_dir / f"q{qresult.id:02d}_01_input.png"))
    started_iso = now_iso()
    qresult.notes.append(f"submit_started={started_iso}")

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
            qresult.notes.append("send via Enter (fallback)")
        except Exception as e:
            qresult.notes.append(f"send Enter failed: {e}")

    # run-sql wait — interruptible. The previous page.expect_response(...)
    # blocked for the FULL run_sql_timeout_ms (up to 10 minutes on slow
    # tenants), which meant a user clicking Stop sat with "Stopping…" for
    # that long because should_stop() was only checked between queries.
    # The helper polls should_stop() every 1s while waiting.
    run_sql_resp = None
    try:
        emit_activity(
            "api",
            f"Waiting for run-sql response (timeout {cfg.run_sql_timeout_ms // 1000}s). "
            "If this times out, no run-sql API response was received before the limit.",
        )
        run_sql_resp = _wait_for_response_interruptible(
            page,
            lambda r: _is_run_sql_url(r.url),
            timeout_ms=cfg.run_sql_timeout_ms,
            should_stop=cfg.should_stop,
            click_fn=click_send,
        )
        qresult.notes.append(f"run-sql HTTP {run_sql_resp.status} {run_sql_resp.url}")
        emit_activity("api", f"run-sql responded HTTP {run_sql_resp.status}")
    except StopRequested:
        qresult.notes.append("run-sql wait aborted by Stop request")
        emit_activity("stop", "Stop requested — aborting run-sql wait")
        raise
    except PWTimeoutError:
        qresult.notes.append(f"run-sql TIMEOUT after {cfg.run_sql_timeout_ms}ms")
        emit_activity(
            "api-timeout",
            f"run-sql timed out after {cfg.run_sql_timeout_ms // 1000}s. "
            "Reason: the SQL execution API did not return before the configured timeout. "
            "Possible causes: broad/heavy question, slow tenant database, API/server issue, or network delay.",
        )
        qresult.timed_out = True
        qresult.validations["timed_out_on"] = "run-sql"
        return
    except Exception as e:
        qresult.notes.append(f"run-sql interruptible wait error: {type(e).__name__}: {e}")
        emit_activity("api-error", f"run-sql wait error: {type(e).__name__}: {e}")

    page.wait_for_timeout(500)
    # Capture both run-sql and generate-sql from the recorder. We accept calls
    # WITHOUT a finished response too — for TIMEOUT cases the request side has
    # been captured (URL, method, headers, body) and the user still needs to
    # see what we sent, even if no response came back.
    snapshot = recorder.snapshot_after(started_iso)
    if run_sql_resp is not None:
        for c in snapshot:
            if c.classification == "run-sql" and c.url == run_sql_resp.url and c.finished_at:
                qresult.run_sql_call = c
                break
    if qresult.run_sql_call is None:
        # Prefer a finished call; fall back to a request-only one (timeout case).
        for c in snapshot:
            if c.classification == "run-sql" and c.finished_at:
                qresult.run_sql_call = c
                break
        if qresult.run_sql_call is None:
            for c in snapshot:
                if c.classification == "run-sql":
                    qresult.run_sql_call = c
                    qresult.notes.append("run-sql captured request-only (no response received)")
                    break
    # Same logic for generate-sql (the NL → SQL LLM call to celerantai.com).
    for c in snapshot:
        if c.classification == "generate-sql":
            qresult.generate_sql_call = c
            break

    page.wait_for_timeout(500)
    qresult.screenshots.append(_screenshot(page, screenshot_dir / f"q{qresult.id:02d}_02_runsql.png"))

    # Generate Visualization is conditional — UI omits it for non-chartable (single-column) results.
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
        qresult.notes.append("Generate Visualization button not present (UI hides for non-chartable result)")
        emit_activity("viz", "Generate Visualization button not shown; skipping chart step")
        qresult.validations["viz_button_present"] = False
        return
    qresult.validations["viz_button_present"] = True

    viz_started_iso = now_iso()
    gen_viz_resp = None

    def _click_viz_btn():
        try:
            target = gv_btn.last
            target.scroll_into_view_if_needed(timeout=3000)
            target.click(timeout=5000)
            qresult.notes.append("clicked Generate Visualization")
        except Exception as e:
            qresult.notes.append(f"Generate Visualization click failed: {e}")
            raise

    try:
        emit_activity(
            "api",
            f"Waiting for generate-viz response (timeout {cfg.gen_viz_timeout_ms // 1000}s). "
            "If this times out, no visualization API response was received before the limit.",
        )
        gen_viz_resp = _wait_for_response_interruptible(
            page,
            lambda r: _is_gen_viz_url(r.url),
            timeout_ms=cfg.gen_viz_timeout_ms,
            should_stop=cfg.should_stop,
            click_fn=_click_viz_btn,
        )
        qresult.notes.append(f"generate-viz HTTP {gen_viz_resp.status} {gen_viz_resp.url}")
        emit_activity("api", f"generate-viz responded HTTP {gen_viz_resp.status}")
    except StopRequested:
        qresult.notes.append("generate-viz wait aborted by Stop request")
        emit_activity("stop", "Stop requested — aborting generate-viz wait")
        raise
    except PWTimeoutError:
        qresult.notes.append(f"generate-viz TIMEOUT after {cfg.gen_viz_timeout_ms}ms")
        emit_activity(
            "api-timeout",
            f"generate-viz timed out after {cfg.gen_viz_timeout_ms // 1000}s. "
            "Reason: the chart/visualization API did not return before the configured timeout. "
            "Possible causes: large result set, non-chartable data, API/server issue, or network delay.",
        )
        qresult.timed_out = True
        qresult.validations["timed_out_on"] = "generate-viz"
    except Exception as e:
        qresult.notes.append(f"generate-viz interruptible wait error: {type(e).__name__}: {e}")
        emit_activity("api-error", f"generate-viz wait error: {type(e).__name__}: {e}")

    page.wait_for_timeout(700)
    viz_snapshot = recorder.snapshot_after(viz_started_iso)
    if gen_viz_resp is not None:
        for c in viz_snapshot:
            if c.classification == "generate-viz" and c.url == gen_viz_resp.url and c.finished_at:
                qresult.generate_viz_call = c
                break
    if qresult.generate_viz_call is None:
        for c in viz_snapshot:
            if c.classification == "generate-viz" and c.finished_at:
                qresult.generate_viz_call = c
                break
        # Fall back to request-only (timeout case)
        if qresult.generate_viz_call is None:
            for c in viz_snapshot:
                if c.classification == "generate-viz":
                    qresult.generate_viz_call = c
                    qresult.notes.append("generate-viz captured request-only (no response received)")
                    break

    qresult.screenshots.append(_screenshot(page, screenshot_dir / f"q{qresult.id:02d}_03_viz.png"))


def _screenshot(page: Page, path: Path) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_query(qr: QueryResult) -> None:
    v: dict[str, Any] = dict(qr.validations or {})

    # Back-fill from qr.calls when expect_response missed by a few ms.
    # First try finished calls, then fall back to request-only (timeout case).
    if qr.run_sql_call is None:
        for c in qr.calls:
            if c.classification == "run-sql" and c.finished_at:
                qr.run_sql_call = c
                qr.notes.append("run-sql back-filled from calls list")
                break
        if qr.run_sql_call is None:
            for c in qr.calls:
                if c.classification == "run-sql":
                    qr.run_sql_call = c
                    qr.notes.append("run-sql back-filled (request-only, no response)")
                    break
    if qr.generate_viz_call is None and v.get("viz_button_present"):
        for c in qr.calls:
            if c.classification == "generate-viz" and c.finished_at:
                qr.generate_viz_call = c
                qr.notes.append("generate-viz back-filled from calls list")
                break
    if qr.generate_sql_call is None:
        for c in qr.calls:
            if c.classification == "generate-sql":
                qr.generate_sql_call = c
                break

    rs = qr.run_sql_call
    if not rs:
        v.update({
            "run_sql_present": False,
            "run_sql_status_ok": False,
            "run_sql_has_rows": False,
            "run_sql_columns": [],
        })
    else:
        v["run_sql_present"] = True
        v["run_sql_status_ok"] = bool(rs.status and 200 <= rs.status < 300)
        cols, rc, hr = extract_table_shape(rs.response_body)
        v["run_sql_columns"] = cols
        v["run_sql_empty_named_columns"] = sum(1 for c in cols if not str(c).strip())
        v["run_sql_row_count"] = rc
        v["run_sql_has_rows"] = hr
        v["run_sql_returned_sql"] = extract_returned_sql(rs.response_body)
        v["run_sql_response_keys"] = list(rs.response_body.keys()) if isinstance(rs.response_body, dict) else None

    gv = qr.generate_viz_call
    if not gv:
        v.update({
            "generate_viz_present": False,
            "generate_viz_status_ok": False,
            "generate_viz_has_chart": False,
        })
    else:
        v["generate_viz_present"] = True
        v["generate_viz_status_ok"] = bool(gv.status and 200 <= gv.status < 300)
        v["generate_viz_response_keys"] = list(gv.response_body.keys()) if isinstance(gv.response_body, dict) else None
        chart = inspect_chart_payload(gv.response_body)
        v.update({
            "generate_viz_has_chart": chart["has_chart"],
            "generate_viz_chart_type": chart["chart_type"],
            "generate_viz_chart_title": chart["chart_title"],
            "generate_viz_x_axis": chart["x_axis"],
            "generate_viz_y_axis": chart["y_axis"],
            "generate_viz_x_axis_label": chart["x_axis_label"],
            "generate_viz_y_axis_label": chart["y_axis_label"],
            "generate_viz_columns": chart["columns"],
            "generate_viz_data_points": chart["data_points"],
            "generate_viz_visualizations_count": chart["visualizations_count"],
        })

    rs_norm = [c.lower() for c in (v.get("run_sql_columns") or [])]
    gv_norm = [c.lower() for c in (v.get("generate_viz_columns") or [])]
    if rs_norm and gv_norm:
        synced = set(rs_norm).issubset(set(gv_norm)) or set(gv_norm).issubset(set(rs_norm))
        v["columns_synced_run_sql_vs_generate_viz"] = synced
        v["column_intersection"] = sorted(set(rs_norm) & set(gv_norm))
        v["column_only_in_run_sql"] = sorted(set(rs_norm) - set(gv_norm))
        v["column_only_in_generate_viz"] = sorted(set(gv_norm) - set(rs_norm))
    else:
        v["columns_synced_run_sql_vs_generate_viz"] = None

    qr.validations = v

    fails: list[str] = []
    warns: list[str] = []
    if not v.get("run_sql_present"):
        fails.append("run-sql call missing")
    elif not v.get("run_sql_status_ok"):
        fails.append(f"run-sql HTTP {qr.run_sql_call.status if qr.run_sql_call else 'n/a'}")
    elif not v.get("run_sql_has_rows"):
        warns.append("run-sql returned no rows")

    viz_button_present = v.get("viz_button_present")
    if viz_button_present is False:
        v["viz_skipped_reason"] = "Generate Visualization button not rendered (single-column / non-chartable result)"
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
    v["fail_reasons"] = fails
    v["warn_reasons"] = warns


def extract_table_shape(body: Any) -> tuple[list[str], int, bool]:
    cols: list[str] = []
    row_count = 0
    if isinstance(body, dict):
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

    visualizations = None
    rb = body.get("responseBody")
    if isinstance(rb, dict):
        d = rb.get("data")
        if isinstance(d, dict):
            v = d.get("visualizations")
            if isinstance(v, list):
                visualizations = v
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


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------
def save_query_result(qr: QueryResult, output_dir: Path) -> Path:
    results_dir = output_dir / "results"
    network_dir = output_dir / "network_logs"
    results_dir.mkdir(parents=True, exist_ok=True)
    network_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(qr)
    out = results_dir / f"q{qr.id:02d}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    (network_dir / f"q{qr.id:02d}_calls.json").write_text(
        json.dumps([asdict(c) for c in qr.calls], indent=2, default=str)
    )
    return out


def run(cfg: RunConfig) -> dict[str, Any]:
    """Execute every question in cfg.questions sequentially. Returns a summary dict."""
    cfg.output_dir = Path(cfg.output_dir)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = cfg.output_dir / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)

    def log(line: str) -> None:
        print(line, flush=True)
        if cfg.on_event:
            try:
                cfg.on_event(line)
            except Exception:
                pass

    log(f"[run] {len(cfg.questions)} questions")
    log(f"[run] login_url={cfg.login_url}")
    log(f"[run] output_dir={cfg.output_dir}")

    # How often to reload the SQL Agent page to flush the chat-history DOM
    # (the SPA keeps every previous turn, including big tables and charts, in
    # the page — that grows memory linearly per question). 3 is aggressive
    # enough that we never let the chat get fat enough to crash on tenants
    # with large run-sql results.
    RELOAD_EVERY = 3
    # When the page or browser dies (Chromium tab crash from memory pressure,
    # network blip, etc.) we re-launch from scratch instead of letting every
    # remaining question fail with TargetClosedError. Budget scales with the
    # run size so a 1500-question run isn't capped at a handful of recoveries
    # the way a flat constant would be.
    MAX_RECOVERIES = max(20, len(cfg.questions) // 20)

    def _is_page_alive(pg: Page) -> bool:
        try:
            return not pg.is_closed()
        except Exception:
            return False

    def _looks_like_target_closed(exc: BaseException) -> bool:
        name = type(exc).__name__
        msg = str(exc)
        return (
            "TargetClosedError" in name
            or "Target page, context or browser has been closed" in msg
            or "Browser has been closed" in msg
            or "Page crashed" in msg
            or "page crashed" in msg.lower()
            or "SQL Agent chat input was missing" in msg
        )

    with sync_playwright() as p:
        def _launch():
            br = p.chromium.launch(headless=cfg.headless)
            ctx = br.new_context(
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 900},
            )
            pg = ctx.new_page()
            rec = NetworkRecorder(pg)
            return br, ctx, pg, rec

        browser, context, page, recorder = _launch()

        try:
            do_login(page, cfg, log)
            page = open_sql_agent(page, cfg, log)
        except Exception as e:
            log(f"[run] FATAL during setup: {e}")
            (cfg.output_dir / "fatal_error.txt").write_text(traceback.format_exc())
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            raise

        def _recover() -> tuple[Any, Any, Page, NetworkRecorder]:
            """Tear down the dead browser and bring up a fresh one re-logged-in
            on the SQL Agent page. Raises on failure."""
            log("[recover] tearing down dead browser/context")
            if cfg.on_event:
                cfg.on_event("[recover-browser-step] Closing crashed browser/context")
            try:
                recorder.detach()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            log("[recover] launching fresh browser + re-login")
            if cfg.on_event:
                cfg.on_event("[recover-browser-step] Launching fresh Chromium browser")
            br, ctx, pg, rec = _launch()
            if cfg.on_event:
                cfg.on_event("[recover-browser-step] Re-login started")
            do_login(pg, cfg, log)
            if cfg.on_event:
                cfg.on_event("[recover-browser-step] Login recovered; opening SQL Agent page")
            pg = open_sql_agent(pg, cfg, log)
            log("[recover] ready")
            if cfg.on_event:
                cfg.on_event("[recover-browser-step] SQL Agent ready after recovery")
            return br, ctx, pg, rec

        def _recover_now(reason: str) -> bool:
            """Immediately rebuild the browser so one crashed page does not
            poison every remaining query."""
            nonlocal browser, context, page, recorder, recoveries_used, successful_since_reload
            if recoveries_used >= MAX_RECOVERIES:
                log(f"[recover] skipped — recovery budget exhausted ({recoveries_used}/{MAX_RECOVERIES})")
                return False
            try:
                log(f"[recover] {reason} — launching fresh browser "
                    f"(recovery {recoveries_used + 1}/{MAX_RECOVERIES})")
                if cfg.on_event:
                    cfg.on_event(f"[recover-browser-start] {reason}. Reopening browser and logging in again.")
                browser, context, page, recorder = _recover()
                recoveries_used += 1
                successful_since_reload = 0
                if cfg.on_event:
                    cfg.on_event("[recover-browser-ok] Fresh browser is ready; continuing with next question.")
                return True
            except Exception as recover_error:
                log(f"[recover] fresh browser recovery failed: {recover_error}")
                if cfg.on_event:
                    cfg.on_event(f"[recover-browser-failed] Fresh browser recovery failed: {recover_error}")
                return False

        all_results: list[QueryResult] = []
        stopped = False
        recoveries_used = 0
        successful_since_reload = 0
        for row in cfg.questions:
            # User-initiated abort — bail out before starting the next query.
            if cfg.should_stop and cfg.should_stop():
                log("[run] STOP requested — aborting before next query")
                stopped = True
                break
            qr = QueryResult(
                id=row["id"],
                nl_query=row["natural_language_query"],
                expected_sql=row.get("expected_sql", ""),
                started_at=now_iso(),
            )
            log(f"\n[q{qr.id:02d}] {qr.nl_query[:80]}")

            # Liveness check — if the previous iteration killed the page,
            # rebuild the browser before trying this question. Without this,
            # every remaining question fails with TargetClosedError on the
            # very first locator call.
            if not _is_page_alive(page):
                if recoveries_used >= MAX_RECOVERIES:
                    qr.error = "page died and recovery budget exhausted"
                    qr.overall_status = "FAIL"
                    qr.notes.append(f"recoveries used: {recoveries_used}/{MAX_RECOVERIES}")
                    qr.finished_at = now_iso()
                    save_query_result(qr, cfg.output_dir)
                    all_results.append(qr)
                    continue
                try:
                    log(f"[q{qr.id:02d}] page is closed — recovering "
                        f"(recovery {recoveries_used + 1}/{MAX_RECOVERIES})")
                    browser, context, page, recorder = _recover()
                    recoveries_used += 1
                    successful_since_reload = 0
                except Exception as e:
                    log(f"[q{qr.id:02d}] recovery failed: {e}")
                    qr.error = f"recovery failed: {type(e).__name__}: {e}"
                    qr.overall_status = "FAIL"
                    qr.notes.append("page died and recovery failed")
                    qr.finished_at = now_iso()
                    save_query_result(qr, cfg.output_dir)
                    all_results.append(qr)
                    continue

            try:
                start = now_iso()
                # Bound recorder memory: drop everything captured before this
                # query started. The previous query's calls were already saved
                # into qr.calls + serialized to disk, so we don't need them
                # in the live buffer anymore.
                dropped = recorder.prune_before(start)
                if dropped:
                    qr.notes.append(f"recorder pruned {dropped} stale calls")
                submit_query(page, recorder, cfg, qr, screenshot_dir)
                qr.calls = recorder.snapshot_after(start)
                validate_query(qr)
            except StopRequested:
                # User clicked Stop while this query was mid-flight. Mark the
                # query as STOPPED (not FAIL) and exit the outer loop after
                # the bookkeeping below — don't let the generic except below
                # turn this into a confusing "FAIL: StopRequested" row.
                qr.overall_status = "STOPPED"
                qr.notes.append("aborted by user Stop request mid-query")
                stopped = True
            except Exception as e:
                qr.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                qr.overall_status = "FAIL"
                qr.notes.append(f"unhandled: {e}")
                # Page died during this query — recover immediately so a
                # crashed/poisoned tab does not make every remaining query fail.
                if _looks_like_target_closed(e) or not _is_page_alive(page):
                    qr.notes.append("page closed/crashed mid-query — recovering browser before next question")
                    _recover_now(f"q{qr.id:02d} crashed or lost SQL Agent input")
                else:
                    try:
                        qr.screenshots.append(
                            _screenshot(page, screenshot_dir / f"q{qr.id:02d}_99_error.png")
                        )
                    except Exception:
                        pass

            qr.finished_at = now_iso()
            try:
                qr.total_duration_ms = int(
                    (datetime.fromisoformat(qr.finished_at) - datetime.fromisoformat(qr.started_at))
                    .total_seconds() * 1000
                )
            except Exception:
                pass
            log(f"[q{qr.id:02d}] {qr.overall_status} ({qr.total_duration_ms} ms)")
            save_query_result(qr, cfg.output_dir)
            all_results.append(qr)

            # If StopRequested fired mid-query, bail out NOW — don't bother
            # with the post-query reload/recovery logic below, and don't
            # iterate to the next question. The user wants out, immediately.
            if stopped:
                log("[run] stopping run after current query was aborted by user")
                break

            if qr.timed_out and _is_page_alive(page):
                try:
                    log(f"[q{qr.id:02d}] timed out — reloading SQL Agent")
                    target = derive_sql_agent_url(cfg.login_url, cfg.sql_agent_path)
                    page.goto(target, wait_until="domcontentloaded", timeout=cfg.page_load_timeout_ms)
                    # No networkidle here either — SPA never idles
                    page.wait_for_selector(SQL_AGENT_INPUT_SELECTOR, timeout=30_000)
                    successful_since_reload = 0
                except Exception as e:
                    log(f"[q{qr.id:02d}] reload failed: {e}")
                    qr.notes.append(f"post-timeout SQL Agent reload failed: {e}")
                    _recover_now(f"q{qr.id:02d} timeout reload failed")
            elif qr.overall_status == "PASS" and _is_page_alive(page):
                successful_since_reload += 1
                # Periodic reload to flush the chat-history DOM. Without this,
                # the SPA's accumulated turns (each with table + chart) keep
                # eating memory until the tab crashes — typically around the
                # 6th-7th question on tenants with large result sets.
                if successful_since_reload >= RELOAD_EVERY:
                    try:
                        log(f"[mem] reloading SQL Agent after {successful_since_reload} "
                            f"successful queries (flushing chat DOM)")
                        target = derive_sql_agent_url(cfg.login_url, cfg.sql_agent_path)
                        page.goto(target, wait_until="domcontentloaded",
                                  timeout=cfg.page_load_timeout_ms)
                        page.wait_for_selector(SQL_AGENT_INPUT_SELECTOR, timeout=30_000)
                        successful_since_reload = 0
                    except Exception as e:
                        log(f"[mem] periodic reload failed: {e}")
                        _recover_now("periodic SQL Agent reload failed")

        agg = cfg.output_dir / "all_results.json"
        agg.write_text(json.dumps([asdict(r) for r in all_results], indent=2, default=str))
        log(f"\n[done] aggregate: {agg}")

        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

    # Summary
    counts: dict[str, int] = {}
    for r in all_results:
        counts[r.overall_status] = counts.get(r.overall_status, 0) + 1
    return {
        "total": len(all_results),
        "status_counts": counts,
        "output_dir": str(cfg.output_dir),
        "stopped_by_user": stopped,
    }


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------
def cli() -> None:
    ap = argparse.ArgumentParser(prog="skylar-qa-runner")
    ap.add_argument("--login-url", required=True, help="Full login URL e.g. https://host:8443/backoffice/?mid=100")
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--questions", required=True, help="Path to .xlsx of questions (column A = NL question)")
    ap.add_argument("--output-dir", required=True, help="Directory to write artefacts into")
    ap.add_argument("--machine-id", default="100")
    ap.add_argument("--sql-agent-path", default="/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent")
    ap.add_argument("--run-sql-timeout", type=int, default=120_000)
    ap.add_argument("--gen-viz-timeout", type=int, default=120_000)
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--no-headless", dest="headless", action="store_false")
    args = ap.parse_args()

    from app.excel_reader import read_questions
    questions = read_questions(args.questions)

    cfg = RunConfig(
        login_url=args.login_url,
        username=args.username,
        password=args.password,
        questions=questions,
        output_dir=Path(args.output_dir),
        machine_id=args.machine_id,
        sql_agent_path=args.sql_agent_path,
        run_sql_timeout_ms=args.run_sql_timeout,
        gen_viz_timeout_ms=args.gen_viz_timeout,
        headless=args.headless,
    )
    try:
        summary = run(cfg)
        print("\n=== SUMMARY ===")
        print(json.dumps(summary, indent=2))
    except KeyboardInterrupt:
        print("\n[abort] interrupted")
        sys.exit(130)


if __name__ == "__main__":
    cli()
