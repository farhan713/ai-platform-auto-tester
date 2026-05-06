"""
Site Search QA runner — parallel to runner.run() for the SQL Agent.

Drives a Site Search page that uses the ssLibrary widget:
  1. Navigate to <login_url>          (the page hosting the ssLibrary widget)
  2. Wait for the search input        (default selector: #searchbox)
  3. For each keyword in the .xlsx:
        a) Type the keyword (one keystroke fires the keyup handler)
        b) Wait for the /search_keywords/ response
        c) Wait for the /search_multi_keyword_and_results/ or /search_results/ response
        d) Capture both, screenshot, validate
  4. Aggregate.

The page itself handles JWT auth in the background (POST to
.../console/organization_validation/<orgId>) — no login form needed.
"""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from playwright.sync_api import (
    sync_playwright, Page, TimeoutError as PWTimeoutError,
)

from app.runner import (
    RunConfig, QueryResult, NetworkRecorder, CapturedCall,
    _is_search_keywords_url, _is_search_results_url,
    now_iso, _screenshot, save_query_result, validate_query,
)


def _validate_sitesearch_query(qr: QueryResult) -> None:
    """Set overall_status + fail/warn reasons for a site-search query result."""
    v: dict[str, Any] = dict(qr.validations or {})

    # Back-fill from calls list if expect_response missed by a few ms
    if qr.search_keywords_call is None:
        for c in qr.calls:
            if c.classification == "search-keywords":
                qr.search_keywords_call = c
                break
    if qr.search_results_call is None:
        for c in qr.calls:
            if c.classification == "search-results":
                qr.search_results_call = c
                break

    sk = qr.search_keywords_call
    sr = qr.search_results_call

    fails: list[str] = []
    warns: list[str] = []

    if not sk:
        v["search_keywords_present"] = False
        fails.append("search_keywords call missing")
    else:
        v["search_keywords_present"] = True
        v["search_keywords_status_ok"] = bool(sk.status and 200 <= sk.status < 300)
        keyword_count = 0
        if isinstance(sk.response_body, dict):
            try:
                kl = sk.response_body.get("responseBody", {}).get("datalist") or []
                keyword_count = len(kl) if isinstance(kl, list) else 0
            except Exception:
                pass
        v["search_keywords_count"] = keyword_count
        if not v.get("search_keywords_status_ok"):
            fails.append(f"search_keywords HTTP {sk.status}")
        elif keyword_count == 0:
            warns.append("search_keywords returned 0 keywords")

    if not sr:
        v["search_results_present"] = False
        fails.append("search_results call missing")
    else:
        v["search_results_present"] = True
        v["search_results_status_ok"] = bool(sr.status and 200 <= sr.status < 300)
        result_count = 0
        if isinstance(sr.response_body, dict):
            try:
                dl = sr.response_body.get("responseBody", {}).get("datalist") or []
                if isinstance(dl, list):
                    # Could be a list of buckets each with their own products
                    if dl and isinstance(dl[0], dict) and "products" in dl[0]:
                        result_count = sum(len(b.get("products") or []) for b in dl)
                    else:
                        result_count = len(dl)
            except Exception:
                pass
        v["search_results_count"] = result_count
        if not v.get("search_results_status_ok"):
            fails.append(f"search_results HTTP {sr.status}")
        elif result_count == 0:
            warns.append("search_results returned 0 products")

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
    qr.validations = v


def _submit_search_query(
    page: Page, recorder: NetworkRecorder, cfg: RunConfig,
    qr: QueryResult, screenshot_dir: Path,
) -> None:
    box = page.locator(cfg.search_input_selector).first
    box.wait_for(state="visible", timeout=15_000)
    try:
        box.scroll_into_view_if_needed(timeout=3_000)
    except Exception:
        pass

    # Clear any prior content + give the page a moment to settle
    box.click()
    box.fill("")
    page.wait_for_timeout(200)

    started_iso = now_iso()
    qr.notes.append(f"submit_started={started_iso}")

    # Type the keyword. The ssLibrary widget binds to keyup, so each char fires.
    # We type, take an "input + keyword" screenshot, then wait for the response.
    sk_resp = sr_resp = None
    try:
        with page.expect_response(
            lambda r: _is_search_keywords_url(r.url),
            timeout=cfg.run_sql_timeout_ms,
        ) as info_kw:
            box.type(qr.nl_query, delay=15)
            # Trigger keyup explicitly in case typing alone doesn't fire it
            page.keyboard.press("End")
            # Snap "input with keyword typed" — captures the user-action state
            # before the popup has a chance to render over it
            page.wait_for_timeout(150)
            qr.screenshots.append(_screenshot(page, screenshot_dir / f"q{qr.id:02d}_01_input.png"))
        sk_resp = info_kw.value
        qr.notes.append(f"search_keywords HTTP {sk_resp.status} {sk_resp.url}")
    except PWTimeoutError:
        qr.notes.append(f"search_keywords TIMEOUT after {cfg.run_sql_timeout_ms}ms")
        qr.timed_out = True
        qr.validations["timed_out_on"] = "search_keywords"
        # Still take the input screenshot if we got that far
        try:
            qr.screenshots.append(_screenshot(page, screenshot_dir / f"q{qr.id:02d}_01_input.png"))
        except Exception: pass
        return
    except Exception as e:
        qr.notes.append(f"search_keywords expect_response error: {type(e).__name__}: {e}")

    # Wait for the results call (search_multi_keyword_and_results OR search_results)
    try:
        with page.expect_response(
            lambda r: _is_search_results_url(r.url),
            timeout=cfg.gen_viz_timeout_ms,
        ) as info_res:
            # The ssLibrary widget chains keywords → results automatically. Just wait.
            pass
        sr_resp = info_res.value
        qr.notes.append(f"search_results HTTP {sr_resp.status} {sr_resp.url}")
    except PWTimeoutError:
        qr.notes.append(f"search_results TIMEOUT after {cfg.gen_viz_timeout_ms}ms")
        qr.timed_out = True
        qr.validations["timed_out_on"] = "search_results"
    except Exception as e:
        qr.notes.append(f"search_results expect_response error: {type(e).__name__}: {e}")

    # CRITICAL: wait for the popup to actually render before screenshotting.
    # ssLibrary's .ss-popup wrapper holds the keyword-list + product results.
    # Without this wait the screenshot would just show the input box.
    popup_rendered = False
    try:
        page.wait_for_function(
            """() => {
                // Real selectors used by ssLibrary (class, not id):
                const candidates = [
                    '.ss-popup', '.ss-data', '.ss-container',
                    '.ss-row.ss-product-row', '.ss-row.ss-header-row',
                    '[class*="ss-popup"]', '[class*="ss-product"]'
                ];
                for (const sel of candidates) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetHeight > 30 &&
                        (el.textContent || '').trim().length > 10) {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=8000,
        )
        popup_rendered = True
        qr.notes.append("results popup rendered")
    except PWTimeoutError:
        qr.notes.append("results popup did not render within 8s — screenshot may show input only")

    # Let any animation finish + scroll the popup into view if needed
    page.wait_for_timeout(700)
    if popup_rendered:
        try:
            page.evaluate(
                """() => {
                    const el = document.querySelector('.ss-popup, .ss-container, .ss-data');
                    if (el && el.scrollIntoView) {
                        el.scrollIntoView({block: 'start', behavior: 'instant'});
                    }
                }"""
            )
            page.wait_for_timeout(200)
        except Exception:
            pass

    # Pull captured records out of the recorder
    snapshot = recorder.snapshot_after(started_iso)
    for c in snapshot:
        if c.classification == "search-keywords" and qr.search_keywords_call is None:
            qr.search_keywords_call = c
        if c.classification == "search-results" and qr.search_results_call is None:
            qr.search_results_call = c

    qr.screenshots.append(_screenshot(page, screenshot_dir / f"q{qr.id:02d}_02_results.png"))


_CRYPTO_POLYFILL = r"""
(() => {
  // ssLibrary calls window.crypto.subtle.generateKey() to encrypt cached
  // search results in localStorage. crypto.subtle is only available in a
  // *secure context* (HTTPS or localhost). When the page is served from
  // host.docker.internal over HTTP (typical dev workflow), subtle is
  // undefined and the lib crashes before rendering the popup. This polyfill
  // is a non-functional pass-through stub — encryption is bypassed but
  // search/render works.
  try {
    if (!window.crypto) window.crypto = {};
    if (!window.crypto.subtle) {
      const stubKey = { type: 'secret', extractable: true, algorithm: { name: 'AES-GCM' }, usages: ['encrypt', 'decrypt'] };
      const passthrough = (a, k, d) => Promise.resolve(d);
      const stub = {
        generateKey: () => Promise.resolve(stubKey),
        importKey:   () => Promise.resolve(stubKey),
        exportKey:   () => Promise.resolve(new ArrayBuffer(32)),
        encrypt:     passthrough,
        decrypt:     passthrough,
        digest:      passthrough,
        sign:        passthrough,
        verify:      () => Promise.resolve(true),
      };
      try { window.crypto.subtle = stub; } catch (_) {
        Object.defineProperty(window.crypto, 'subtle', { value: stub, configurable: true });
      }
      console.log('[skylar-qa] crypto.subtle polyfill installed (insecure context fallback)');
    }
  } catch (e) {
    console.error('[skylar-qa] crypto.subtle polyfill failed:', e);
  }
})();
"""


_INIT_OVERRIDE_TEMPLATE = r"""
(() => {
  // Override config supplied by the QA tool — injected before the page bundle runs.
  const _cfg = __SS_CONFIG__;
  let _ssLib = undefined;
  // Install a property descriptor on window.ssLibrary so when the bundle
  // does `window.ssLibrary = {...}`, our setter wraps init() to use _cfg.
  Object.defineProperty(window, 'ssLibrary', {
    configurable: true,
    set(v) {
      if (v && typeof v.init === 'function') {
        const origInit = v.init.bind(v);
        v.init = function () {
          // Substitute every arg from _cfg, falling back to whatever the
          // page passed for any field the QA tool didn't supply.
          const a = Array.from(arguments);
          return origInit(
            _cfg.org_id              || a[0],
            _cfg.console_url         || a[1],
            _cfg.server_url          || a[2],
            _cfg.image_url           !== undefined ? _cfg.image_url           : a[3],
            _cfg.not_found_image_url !== undefined ? _cfg.not_found_image_url : a[4],
            _cfg.jwt_user            || a[5],
            _cfg.jwt_pass            || a[6]
          );
        };
      }
      _ssLib = v;
    },
    get() { return _ssLib; }
  });
  // Tag the window so the runner can verify the override is in place.
  window.__skylar_qa_override = true;
})();
"""


def _install_ss_override(page: Page, cfg: RunConfig, log: Callable[[str], None]) -> None:
    """If site_search_config is set on the run, install an init-script that
    substitutes the page's hardcoded ssLibrary.init() args with our values."""
    sc = cfg.site_search_config or {}
    sc = {k: v for k, v in sc.items() if v not in (None, "")}
    if not sc:
        return
    safe_keys = ("org_id", "console_url", "server_url", "image_url",
                 "not_found_image_url", "jwt_user", "jwt_pass")
    cfg_dict = {k: sc.get(k, "") for k in safe_keys}
    js = _INIT_OVERRIDE_TEMPLATE.replace("__SS_CONFIG__", json.dumps(cfg_dict))
    page.add_init_script(js)
    log(f"[init] ssLibrary.init override installed: org_id={cfg_dict.get('org_id') or '(page default)'}")
    # Don't log the password — even at debug level
    if cfg_dict.get("jwt_pass"):
        log("[init] custom JWT credentials provided — page's hardcoded ones will be ignored")


def open_search_page(page: Page, cfg: RunConfig, log: Callable[[str], None]) -> None:
    # Always install the crypto polyfill — site_search runs on HTTP fail without it
    page.add_init_script(_CRYPTO_POLYFILL)
    _install_ss_override(page, cfg, log)
    log(f"[nav] opening {cfg.login_url}")
    page.goto(cfg.login_url, wait_until="domcontentloaded", timeout=cfg.page_load_timeout_ms)
    # Wait for the JWT exchange to land before doing anything else — token is
    # set by the .then() of the organization_validation fetch in ssLibrary.init.
    if cfg.site_search_config:
        try:
            page.wait_for_function(
                "() => window.ssLibrary && (window.ssLibrary.token || '').length > 10",
                timeout=30_000,
            )
            log("[init] JWT token obtained")
        except PWTimeoutError:
            log("[init] WARN: JWT token did not arrive within 30s — continuing anyway")
    page.wait_for_load_state("networkidle", timeout=cfg.page_load_timeout_ms)
    page.wait_for_selector(cfg.search_input_selector, timeout=30_000)
    log(f"[nav] search input '{cfg.search_input_selector}' ready")


def run_sitesearch(cfg: RunConfig) -> dict[str, Any]:
    """Execute every keyword/question in cfg.questions against a Site Search page."""
    cfg.output_dir = Path(cfg.output_dir)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = cfg.output_dir / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)

    def log(line: str) -> None:
        print(line, flush=True)
        if cfg.on_event:
            try: cfg.on_event(line)
            except Exception: pass

    log(f"[run] site-search — {len(cfg.questions)} keywords")
    log(f"[run] target_url={cfg.login_url}")
    log(f"[run] output_dir={cfg.output_dir}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        recorder = NetworkRecorder(page)

        try:
            open_search_page(page, cfg, log)
        except Exception as e:
            log(f"[run] FATAL during navigation: {e}")
            (cfg.output_dir / "fatal_error.txt").write_text(traceback.format_exc())
            context.close(); browser.close(); raise

        all_results: list[QueryResult] = []
        stopped = False
        for row in cfg.questions:
            if cfg.should_stop and cfg.should_stop():
                log("[run] STOP requested — aborting"); stopped = True; break
            qr = QueryResult(
                id=row["id"],
                nl_query=row["natural_language_query"],
                expected_sql=row.get("expected_sql", ""),
                started_at=now_iso(),
            )
            log(f"\n[q{qr.id:02d}] keyword: {qr.nl_query[:80]}")
            try:
                start = now_iso()
                _submit_search_query(page, recorder, cfg, qr, screenshot_dir)
                qr.calls = recorder.snapshot_after(start)
                _validate_sitesearch_query(qr)
            except Exception as e:
                qr.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                qr.overall_status = "FAIL"
                qr.notes.append(f"unhandled: {e}")
                qr.screenshots.append(_screenshot(page, screenshot_dir / f"q{qr.id:02d}_99_error.png"))

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

            if qr.timed_out:
                # Reset by reloading the page
                try:
                    log(f"[q{qr.id:02d}] timed out — reloading page")
                    page.goto(cfg.login_url, wait_until="domcontentloaded",
                              timeout=cfg.page_load_timeout_ms)
                    page.wait_for_selector(cfg.search_input_selector, timeout=20_000)
                except Exception as e:
                    log(f"[q{qr.id:02d}] reload failed: {e}")

        agg = cfg.output_dir / "all_results.json"
        agg.write_text(json.dumps([asdict(r) for r in all_results], indent=2, default=str))
        log(f"\n[done] aggregate: {agg}")

        context.close(); browser.close()

    counts: dict[str, int] = {}
    for r in all_results:
        counts[r.overall_status] = counts.get(r.overall_status, 0) + 1
    return {
        "total": len(all_results),
        "status_counts": counts,
        "output_dir": str(cfg.output_dir),
        "stopped_by_user": stopped,
    }
