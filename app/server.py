"""
Flask web UI for the Skylar IQ QA tool — Postgres-backed, multi-user.

Run:
    python -m app.server
"""
from __future__ import annotations

import csv
import io
import json
import os
import platform
import queue
import secrets
import sys
import threading
import time
import traceback
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    send_from_directory, Response, stream_with_context, abort, g, session, flash,
)

from app.runner import RunConfig, run as run_qa
from app.runner_sitesearch import run_sitesearch
from app.report import generate as generate_report
from app.excel_reader import read_questions
from app import db, auth


APP_VERSION = "3.0.0"

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
DATA_DIR = ROOT / "data"
TEST_FILES_DIR = DATA_DIR / "test_files"
BUNDLES_DIR = DATA_DIR / "bundles"
RUNS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
TEST_FILES_DIR.mkdir(exist_ok=True)
BUNDLES_DIR.mkdir(exist_ok=True)


app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get(
    "SQA_SECRET_KEY",
    "dev-only-change-me-in-prod-" + secrets.token_hex(8),
)
app.permanent_session_lifetime = timedelta(days=14)


# ---------------------------------------------------------------------------
# Boot — make sure the schema is in place before serving
# ---------------------------------------------------------------------------
_db_ready = False
_db_lock = threading.Lock()


def _ensure_db_ready() -> None:
    global _db_ready
    if _db_ready: return
    with _db_lock:
        if _db_ready: return
        db.init_schema()
        _db_ready = True


@app.before_request
def _boot():
    if not _db_ready:
        try:
            _ensure_db_ready()
        except Exception as e:
            return Response(
                f"Database not ready yet: {e}\nRetry in a moment.\n",
                503, {"Retry-After": "5"},
            )
    auth.load_current_user()


@app.context_processor
def inject_globals():
    return {"app_version": APP_VERSION, "active": "", "g": g}


# ---------------------------------------------------------------------------
# Auth pages
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    error = None
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        user = auth.authenticate(email, password)
        if user:
            auth.login_user(user)
            nxt = session.pop("next", None) or url_for("dashboard")
            return redirect(nxt)
        error = "Email or password is incorrect."
    return render_template("login.html", error=error, email=email,
                           signup_allowed=auth.signup_allowed())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("dashboard"))
    if not auth.signup_allowed():
        return render_template("login.html",
                               error="Public signup is disabled. Ask your admin to create an account for you.",
                               signup_allowed=False)
    error = None
    name = email = ""
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        try:
            user = auth.create_user(email, password, name)
            auth.login_user(user)
            return redirect(url_for("dashboard"))
        except ValueError as e:
            error = str(e)
        except Exception as e:
            error = f"Signup failed: {e}"
    return render_template("signup.html", error=error, name=name, email=email)


@app.route("/logout")
def logout():
    auth.logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _job_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


# Per-job in-memory event queues + stop flags
_event_queues: dict[str, queue.Queue[str]] = {}
_stop_events: dict[str, threading.Event] = {}


# ---------------------------------------------------------------------------
# Hosted bundle helpers — uploaded ssLibrary builds for users without a public
# search page. We unpack the upload into data/bundles/<id>/ and serve it via
# a synthesised wrapper page at /hosted/<id>/index.html.
# ---------------------------------------------------------------------------
def _save_bundle(uploaded, original_name: str, friendly_name: str,
                 user_id: str) -> dict[str, Any]:
    """Persist an uploaded bundle (.js or .zip) and return its metadata row."""
    import zipfile
    bundle_id = uuid.uuid4().hex  # 32 chars — unguessable URL slug
    bundle_dir = BUNDLES_DIR / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=False)

    safe_name = (original_name or "bundle").replace("/", "_").replace("\\", "_")
    lower = safe_name.lower()

    main_js: str | None = None
    main_css: str | None = None
    file_count = 0

    if lower.endswith(".zip"):
        # Save zip then extract to the bundle dir
        zip_path = bundle_dir / "_upload.zip"
        uploaded.save(str(zip_path))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    if member.endswith("/"): continue       # skip dirs
                    if ".." in member: continue             # zip-slip safety
                    # Skip macOS / Windows metadata cruft that gets auto-added
                    # to zips and confuses the main-file picker below.
                    if "__MACOSX" in member.split("/"): continue
                    base = member.rsplit("/", 1)[-1]
                    if base.startswith("._"): continue       # AppleDouble resource forks
                    if base in (".DS_Store", "Thumbs.db"): continue
                    parts = member.split("/")
                    rel = "/".join(parts[1:]) if len(parts) > 1 and parts[0].endswith("dist") else member
                    rel = rel.replace("..", "_")
                    target = bundle_dir / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    file_count += 1
        finally:
            try: zip_path.unlink()
            except Exception: pass

        # Find the main JS + CSS — prefer files with "bundle" in the name,
        # otherwise the first .js / .css. Filter out macOS/Windows metadata
        # paths even if they slipped through.
        def _real_files(suffix: str) -> list:
            return sorted(
                p for p in bundle_dir.rglob(f"*{suffix}")
                if p.is_file()
                and "__MACOSX" not in p.parts
                and not p.name.startswith("._")
                and p.name not in (".DS_Store", "Thumbs.db")
            )
        js_files = _real_files(".js")
        css_files = _real_files(".css")
        if js_files:
            preferred = [p for p in js_files if "bundle" in p.name.lower()]
            chosen = preferred[0] if preferred else js_files[0]
            main_js = str(chosen.relative_to(bundle_dir))
        if css_files:
            preferred = [p for p in css_files if any(t in p.name.lower() for t in ("library", "bundle", "ss-"))]
            chosen = preferred[0] if preferred else css_files[0]
            main_css = str(chosen.relative_to(bundle_dir))
    elif lower.endswith(".js"):
        # Single JS file
        target = bundle_dir / "bundle.js"
        uploaded.save(str(target))
        main_js = "bundle.js"
        file_count = 1
    else:
        # Unknown — clean up + reject
        import shutil
        shutil.rmtree(bundle_dir, ignore_errors=True)
        raise ValueError("Bundle upload must be a .js file or .zip archive.")

    if not main_js:
        import shutil
        shutil.rmtree(bundle_dir, ignore_errors=True)
        raise ValueError("Could not find any .js file in the upload.")

    size = sum(p.stat().st_size for p in bundle_dir.rglob("*") if p.is_file())
    db.execute(
        """INSERT INTO hosted_bundles (id, user_id, name, original_filename,
                                        file_count, size_bytes, main_js, main_css)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (bundle_id, user_id, friendly_name[:80] or safe_name,
         safe_name, file_count, size, main_js, main_css),
    )
    return db.fetch_one("SELECT * FROM hosted_bundles WHERE id = %s", (bundle_id,))


def _user_bundle(bundle_id: str) -> dict[str, Any] | None:
    return db.fetch_one(
        "SELECT * FROM hosted_bundles WHERE id = %s AND user_id = %s",
        (bundle_id, auth.current_user_id()),
    )


def _delete_bundle(bundle_id: str, user_id: str) -> bool:
    row = db.fetch_one(
        "SELECT id FROM hosted_bundles WHERE id = %s AND user_id = %s",
        (bundle_id, user_id),
    )
    if not row: return False
    db.execute("DELETE FROM hosted_bundles WHERE id = %s", (bundle_id,))
    import shutil
    shutil.rmtree(BUNDLES_DIR / bundle_id, ignore_errors=True)
    return True


def _render_hosted_index(bundle: dict[str, Any]) -> str:
    """Synthesise the wrapper HTML that loads the user's bundle and calls
    ssLibrary.init() with placeholder values. The runner's add_init_script
    override substitutes those placeholders with the user's Tenant Override
    config at runtime."""
    main_js = bundle.get("main_js") or "bundle.js"
    main_css = bundle.get("main_css")
    css_link = f'<link rel="stylesheet" href="{main_css}">' if main_css else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Skylar QA — Hosted test page</title>
{css_link}
<style>
  body {{ margin: 24px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
  .qa-banner {{
    position: fixed; top: 0; right: 0; padding: 6px 14px;
    background: rgba(26, 138, 58, 0.9); color: #fff; font-size: 11px;
    z-index: 9999; border-bottom-left-radius: 6px; pointer-events: none;
  }}
  #searchbox.inputWrap, #searchbox {{
    width: 320px; padding: 10px 14px; font-size: 14px;
    border: 2px solid #1a3a6e; border-radius: 4px; outline: none;
  }}
</style>
</head>
<body class="bodyWrap">
  <div class="qa-banner">Skylar QA hosted test page</div>
  <div class="mainwrap">
    <div>
      <input class="inputWrap" type="text" id="searchbox">
    </div>
  </div>
  <script src="{main_js}"></script>
  <script>
    // Placeholder init() call — these args are replaced at runtime by the
    // QA tool's Tenant Override config (org_id, console_url, jwt_user, etc.)
    if (window.ssLibrary && typeof window.ssLibrary.init === 'function') {{
      window.ssLibrary.init('placeholder', '', '', '', '', 'placeholder', 'placeholder');
    }} else {{
      console.error('[skylar-qa] window.ssLibrary not defined — bundle did not register the widget');
      document.body.insertAdjacentHTML('beforeend',
        '<div style="color:#c62828;margin:14px 0">Bundle did not register window.ssLibrary. Check the JS file.</div>');
    }}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Hosted-bundle API + serving routes
# ---------------------------------------------------------------------------
@app.route("/api/hosted-bundles", methods=["GET", "POST"])
@auth.login_required
def api_hosted_bundles():
    if request.method == "GET":
        rows = db.fetch_all(
            "SELECT * FROM hosted_bundles WHERE user_id = %s ORDER BY uploaded_at DESC",
            (auth.current_user_id(),))
        return jsonify({"bundles": [
            {"id": r["id"], "name": r["name"],
             "original_filename": r["original_filename"],
             "file_count": r["file_count"], "size_bytes": r["size_bytes"],
             "main_js": r["main_js"], "main_css": r["main_css"],
             "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
             "test_url": f"/hosted/{r['id']}/index.html"}
            for r in rows]})
    f = request.files.get("file")
    if not f: return jsonify({"error": "no file uploaded (field 'file')"}), 400
    name = (request.form.get("name") or "").strip() or (f.filename or "bundle")
    try:
        meta = _save_bundle(f, f.filename or "bundle", name, auth.current_user_id())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"upload failed: {e}"}), 500
    return jsonify({"bundle": {
        "id": meta["id"], "name": meta["name"],
        "original_filename": meta["original_filename"],
        "file_count": meta["file_count"], "size_bytes": meta["size_bytes"],
        "main_js": meta["main_js"], "main_css": meta["main_css"],
        "uploaded_at": meta["uploaded_at"].isoformat() if meta["uploaded_at"] else None,
        "test_url": f"/hosted/{meta['id']}/index.html",
    }}), 201


@app.route("/api/hosted-bundles/<bundle_id>", methods=["DELETE"])
@auth.login_required
def api_hosted_bundle_delete(bundle_id: str):
    if _delete_bundle(bundle_id, auth.current_user_id()):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


# Hosted serving — these routes are NOT login-protected (the runner's headless
# Chromium has no session cookie). Bundle IDs are 32-char random hex so URLs
# are unguessable; only the owner ever sees the URL via the API list.
@app.route("/hosted/<bundle_id>/")
@app.route("/hosted/<bundle_id>/index.html")
def hosted_index(bundle_id: str):
    row = db.fetch_one("SELECT * FROM hosted_bundles WHERE id = %s", (bundle_id,))
    if not row: abort(404)
    return Response(_render_hosted_index(row), mimetype="text/html; charset=utf-8")


@app.route("/hosted/<bundle_id>/<path:rel>")
def hosted_asset(bundle_id: str, rel: str):
    if not db.fetch_one("SELECT id FROM hosted_bundles WHERE id = %s", (bundle_id,)):
        abort(404)
    bundle_dir = BUNDLES_DIR / bundle_id
    full = (bundle_dir / rel).resolve()
    if not str(full).startswith(str(bundle_dir.resolve())): abort(403)
    if not full.exists(): abort(404)
    return send_from_directory(bundle_dir, rel)


def _emit(run_id: str, line: str) -> None:
    q = _event_queues.get(run_id)
    if q is not None:
        try: q.put_nowait(line)
        except queue.Full: pass
    log = _job_dir(run_id) / "events.log"
    try:
        with log.open("a") as f: f.write(line + "\n")
    except Exception: pass


def _run_owned_by_current_user(run_id: str) -> dict[str, Any] | None:
    """Return the run row only if owned by the current user."""
    return db.fetch_one(
        "SELECT * FROM runs WHERE id = %s AND user_id = %s",
        (run_id, auth.current_user_id()),
    )


def _all_results_for_run(run_id: str) -> list[dict[str, Any]]:
    rows = db.fetch_all(
        "SELECT record FROM query_results WHERE run_id = %s ORDER BY qid", (run_id,))
    return [r["record"] for r in rows]


def _all_results_summary_for_run(run_id: str) -> list[dict[str, Any]]:
    """Slim per-query summary used by the run dashboard tabs.

    The full ``record`` JSONB carries every captured XHR/fetch (headers +
    full response bodies, including multi-MB run-sql payloads). For runs
    with hundreds of queries that adds up to hundreds of MB of JSON shipped
    on every dashboard refresh, which freezes the browser before it can
    even show the list. The dashboard only needs status, timing, validation
    reasons, and a per-call classification/status/duration count for the
    Network tab — so we project out exactly those fields here.
    """
    rows = db.fetch_all(
        "SELECT record FROM query_results WHERE run_id = %s ORDER BY qid", (run_id,))
    out: list[dict[str, Any]] = []
    for row in rows:
        rec = row["record"] or {}
        v = rec.get("validations") or {}
        rs = rec.get("run_sql_call") or {}
        gv = rec.get("generate_viz_call") or {}
        slim_calls = []
        for c in (rec.get("calls") or []):
            slim_calls.append({
                "classification": c.get("classification"),
                "status": c.get("status"),
                "duration_ms": c.get("duration_ms"),
            })
        out.append({
            "id": rec.get("id"),
            "nl_query": rec.get("nl_query"),
            "overall_status": rec.get("overall_status"),
            "total_duration_ms": rec.get("total_duration_ms"),
            "validations": {
                "fail_reasons": v.get("fail_reasons") or [],
                "warn_reasons": v.get("warn_reasons") or [],
                "run_sql_row_count": v.get("run_sql_row_count"),
            },
            "run_sql_call": {"status": rs.get("status")} if rs else None,
            "generate_viz_call": {"status": gv.get("status")} if gv else None,
            "calls": slim_calls,
        })
    return out


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------
def _run_job(run_id: str, cfg: RunConfig) -> None:
    """Run the QA, persist per-query rows + events. Filesystem still holds
    screenshots/REPORT/etc; DB holds run metadata + per-query JSONB."""
    try:
        db.execute(
            "UPDATE runs SET status = 'running', started_at = NOW() WHERE id = %s",
            (run_id,),
        )
        cfg.on_event = lambda line: _emit(run_id, line)
        cfg.should_stop = lambda: _stop_events.get(run_id, threading.Event()).is_set()

        # Wrap the runner's per-query save so we can ALSO write each row into Postgres.
        from app.runner import save_query_result as orig_save
        def db_aware_save(qr, output_dir):
            path = orig_save(qr, output_dir)
            try:
                from dataclasses import asdict
                d = asdict(qr)
                db.execute(
                    """INSERT INTO query_results
                       (run_id, qid, status, duration_ms, nl_query, record)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (run_id, qid) DO UPDATE SET
                         status = EXCLUDED.status,
                         duration_ms = EXCLUDED.duration_ms,
                         nl_query = EXCLUDED.nl_query,
                         record = EXCLUDED.record""",
                    (run_id, qr.id, qr.overall_status, qr.total_duration_ms,
                     qr.nl_query, db.jsonify(d)),
                )
            except Exception as e:
                _emit(run_id, f"[db] failed to persist q{qr.id:02d}: {e}")
            return path
        # Monkey-patch just for this run — both runners use save_query_result
        import app.runner as runner_mod
        import app.runner_sitesearch as sitesearch_mod
        runner_mod.save_query_result = db_aware_save
        sitesearch_mod.save_query_result = db_aware_save
        try:
            if cfg.test_type == "site_search":
                summary = run_sitesearch(cfg)
            else:
                summary = run_qa(cfg)
        finally:
            runner_mod.save_query_result = orig_save
            sitesearch_mod.save_query_result = orig_save

        try:
            outputs = generate_report(cfg.output_dir)
            summary["report_outputs"] = outputs
        except Exception as e:
            _emit(run_id, f"[report] generation failed: {e}")

        db.execute(
            "UPDATE runs SET status = %s, finished_at = NOW(), summary = %s WHERE id = %s",
            ("stopped" if summary.get("stopped_by_user") else "done",
             db.jsonify(summary), run_id),
        )
        _emit(run_id, f"[done] {summary}")
    except Exception as e:
        tb = traceback.format_exc()
        _emit(run_id, f"[fatal] {type(e).__name__}: {e}")
        _emit(run_id, tb)
        db.execute(
            "UPDATE runs SET status = 'failed', finished_at = NOW(), error = %s, traceback = %s WHERE id = %s",
            (str(e), tb, run_id),
        )
    finally:
        _emit(run_id, "[__end__]")


# ---------------------------------------------------------------------------
# Pages (all login-required)
# ---------------------------------------------------------------------------
@app.route("/")
@auth.login_required
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@app.route("/runs")
@auth.login_required
def runs_page():
    return render_template("runs.html", active="runs")


@app.route("/runs/new")
@auth.login_required
def new_run_page():
    return render_template("new_run.html", active="new_run")


@app.route("/test-files")
@auth.login_required
def test_files_page():
    return render_template("test_files.html", active="test_files")


@app.route("/test-pages")
@auth.login_required
def test_pages_page():
    return render_template("test_pages.html", active="test_pages")


@app.route("/settings")
@auth.login_required
def settings_page():
    try:
        from playwright import __version__ as pw_version
    except Exception:
        pw_version = "unknown"
    return render_template(
        "settings.html",
        active="settings",
        python_version=sys.version.split()[0],
        playwright_version=pw_version,
        runs_dir=str(RUNS_DIR),
        presets_file="postgres://(database)",
    )


@app.route("/help")
@auth.login_required
def help_page():
    return render_template("help.html", active="help")


# ---------------------------------------------------------------------------
# Run creation + viewing (all owner-scoped)
# ---------------------------------------------------------------------------
@app.route("/jobs", methods=["POST"])
@auth.login_required
def jobs_create():
    test_type = (request.form.get("test_type") or "sql_agent").strip()
    if test_type not in ("sql_agent", "site_search"):
        return (f"Unknown test_type '{test_type}'", 400)

    login_url = (request.form.get("login_url") or "").strip()
    cred_username = (request.form.get("username") or "").strip()
    cred_password = (request.form.get("password") or "")
    machine_id = (request.form.get("machine_id") or "100").strip()
    sql_agent_path = (request.form.get("sql_agent_path") or
                      "/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent").strip()
    search_input_selector = (request.form.get("search_input_selector") or "#searchbox").strip()
    run_sql_to = int(request.form.get("run_sql_timeout_ms") or 120_000)
    gen_viz_to = int(request.form.get("gen_viz_timeout_ms") or 120_000)
    test_file_id = (request.form.get("test_file_id") or "").strip()
    bundle_id = (request.form.get("bundle_id") or "").strip()
    f = request.files.get("questions")

    # Site Search runtime config — overrides the hardcoded ssLibrary.init() args
    # in the user's index.html so the same page can be tested against any tenant.
    site_search_config: dict[str, str] = {}
    if test_type == "site_search":
        for key in ("ss_org_id", "ss_console_url", "ss_server_url",
                    "ss_image_url", "ss_not_found_image_url",
                    "ss_jwt_user", "ss_jwt_pass"):
            v = (request.form.get(key) or "").strip()
            if v:
                site_search_config[key.replace("ss_", "")] = v
        if site_search_config and not site_search_config.get("server_url"):
            site_search_config["server_url"] = site_search_config.get("console_url", "")
        if site_search_config and not site_search_config.get("jwt_user"):
            site_search_config["jwt_user"] = site_search_config.get("org_id", "")

        # If a hosted bundle is picked, override login_url to point at our
        # generated wrapper page. The runner inside the container reaches it
        # via 127.0.0.1:5050 (same container).
        if bundle_id:
            owned = db.fetch_one(
                "SELECT id FROM hosted_bundles WHERE id = %s AND user_id = %s",
                (bundle_id, auth.current_user_id()),
            )
            if not owned:
                return ("Hosted bundle not found, or not yours.", 404)
            login_url = f"http://127.0.0.1:5050/hosted/{bundle_id}/index.html"

    if not login_url:
        return ("Missing login_url / target_url", 400)
    # Catch the file:// trap — Docker can't reach host filesystem paths.
    if login_url.lower().startswith("file:"):
        return (
            "file:// URLs cannot be reached from inside the Docker container.\n\n"
            "Use http:// or https:// instead. To test a local page, serve it over HTTP:\n"
            "    cd /path/to/your/page-folder\n"
            "    python3 -m http.server 8765\n"
            "Then use this URL:  http://host.docker.internal:8765/index.html",
            400,
        )
    if test_type == "sql_agent" and not (cred_username and cred_password):
        return ("SQL Agent runs need username and password", 400)
    if not f and not test_file_id:
        return ("Either upload a questions file or pick a saved test file", 400)

    run_id = uuid.uuid4().hex[:8] + "-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    job = _job_dir(run_id)
    job.mkdir(parents=True, exist_ok=True)
    xlsx_path = job / "questions.xlsx"
    test_file_name = None

    if test_file_id:
        # Owner check: user can only use their own saved files
        tf = db.fetch_one(
            "SELECT * FROM test_files WHERE id = %s AND user_id = %s",
            (test_file_id, auth.current_user_id()),
        )
        if not tf:
            return ("Saved test file not found, or not yours.", 404)
        try:
            xlsx_path.write_bytes((TEST_FILES_DIR / tf["filename"]).read_bytes())
        except Exception as e:
            return (f"Failed to copy saved test file: {e}", 500)
        test_file_name = tf["original_name"]
    else:
        f.save(str(xlsx_path))

    try:
        questions = read_questions(xlsx_path)
    except Exception as e:
        return (f"Failed to read questions file: {e}", 400)

    db.execute(
        """INSERT INTO runs (id, user_id, test_type, login_url, username, machine_id,
                             sql_agent_path, search_input_selector, question_count,
                             test_file_id, test_file_name, site_search_config,
                             bundle_id, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'queued')""",
        (run_id, auth.current_user_id(), test_type, login_url, cred_username, machine_id,
         sql_agent_path, search_input_selector, len(questions),
         test_file_id or None, test_file_name,
         db.jsonify(site_search_config) if site_search_config else None,
         bundle_id or None),
    )

    cfg = RunConfig(
        login_url=login_url, username=cred_username, password=cred_password,
        questions=questions, output_dir=job,
        test_type=test_type,
        machine_id=machine_id, sql_agent_path=sql_agent_path,
        search_input_selector=search_input_selector,
        site_search_config=site_search_config or None,
        run_sql_timeout_ms=run_sql_to, gen_viz_timeout_ms=gen_viz_to,
        headless=True,
    )
    _event_queues[run_id] = queue.Queue(maxsize=10_000)
    _stop_events[run_id] = threading.Event()
    threading.Thread(target=_run_job, args=(run_id, cfg), daemon=True).start()
    return redirect(url_for("job_view", job_id=run_id))


@app.route("/jobs/<job_id>")
@auth.login_required
def job_view(job_id: str):
    run = _run_owned_by_current_user(job_id)
    if not run:
        abort(404)
    meta = {
        "test_type": run.get("test_type", "sql_agent"),
        "login_url": run["login_url"],
        "username": run["username"],
        "machine_id": run["machine_id"],
        "sql_agent_path": run["sql_agent_path"],
        "search_input_selector": run.get("search_input_selector"),
        "question_count": run["question_count"],
        "status": run["status"],
        "created_at": run["created_at"].isoformat() if run.get("created_at") else None,
        "started_at": run["started_at"].isoformat() if run.get("started_at") else None,
        "finished_at": run["finished_at"].isoformat() if run.get("finished_at") else None,
    }
    return render_template("job.html", job_id=job_id, meta=meta, active="runs")


@app.route("/jobs/<job_id>/meta")
@auth.login_required
def job_meta_api(job_id: str):
    """Lightweight JSON endpoint — used by query.html to know the test_type."""
    run = _run_owned_by_current_user(job_id)
    if not run: abort(404)
    return jsonify({"test_type": run.get("test_type", "sql_agent"),
                    "login_url": run["login_url"],
                    "question_count": run["question_count"]})


@app.route("/jobs/<job_id>/queries/<int:qid>")
@auth.login_required
def job_query_view(job_id: str, qid: int):
    if not _run_owned_by_current_user(job_id):
        abort(404)
    return render_template("query.html", job_id=job_id, qid=qid, active="runs")


@app.route("/jobs/<job_id>/status")
@auth.login_required
def job_status(job_id: str):
    run = _run_owned_by_current_user(job_id)
    if not run: abort(404)
    rows = db.fetch_all(
        "SELECT qid, status, duration_ms, nl_query FROM query_results WHERE run_id = %s ORDER BY qid",
        (job_id,))
    counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "TIMEOUT": 0, "PENDING": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    last5 = [{"id": r["qid"], "nl_query": (r["nl_query"] or "")[:80],
              "status": r["status"], "duration_ms": r["duration_ms"]} for r in rows[-5:]]
    stop_requested = bool(_stop_events.get(job_id) and _stop_events[job_id].is_set())
    return jsonify({
        "job_id": job_id, "status": run["status"],
        "stop_requested": stop_requested,
        "completed": sum(counts.values()) - counts["PENDING"],
        "total": run["question_count"],
        "counts": counts, "last5": last5,
    })


@app.route("/jobs/<job_id>/results")
@auth.login_required
def job_results(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    return jsonify({"results": _all_results_for_run(job_id)})


@app.route("/jobs/<job_id>/results-summary")
@auth.login_required
def job_results_summary(job_id: str):
    """Slim version of /results — used by the dashboard tabs (Overview,
    All queries, Network) to keep payload size bounded for large runs.
    Drops headers/bodies/etc; keeps the fields the UI actually renders."""
    if not _run_owned_by_current_user(job_id): abort(404)
    return jsonify({"results": _all_results_summary_for_run(job_id)})


@app.route("/jobs/<job_id>/events")
@auth.login_required
def job_events(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)

    @stream_with_context
    def gen():
        log = _job_dir(job_id) / "events.log"
        if log.exists():
            for line in log.read_text().splitlines():
                yield f"data: {line}\n\n"
        q = _event_queues.get(job_id)
        if q is None: return
        while True:
            try:
                line = q.get(timeout=20)
            except queue.Empty:
                yield ": keepalive\n\n"; continue
            yield f"data: {line}\n\n"
            if line == "[__end__]": return
    return Response(gen(), mimetype="text/event-stream")


@app.route("/jobs/<job_id>/stop", methods=["POST"])
@auth.login_required
def job_stop(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    ev = _stop_events.get(job_id)
    if ev is None:
        ev = threading.Event(); _stop_events[job_id] = ev
    ev.set()
    _emit(job_id, "[stop] user requested stop")
    return jsonify({"ok": True, "stop_requested": True})


@app.route("/jobs/<job_id>/result/<int:qid>")
@auth.login_required
def job_result(job_id: str, qid: int):
    if not _run_owned_by_current_user(job_id): abort(404)
    row = db.fetch_one(
        "SELECT record FROM query_results WHERE run_id = %s AND qid = %s",
        (job_id, qid),
    )
    if not row:
        return jsonify({"pending": True, "id": qid}), 202
    return jsonify(row["record"])


@app.route("/jobs/<job_id>/screenshots/<path:rel>")
@auth.login_required
def job_screenshot(job_id: str, rel: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    job = _job_dir(job_id)
    full = (job / "screenshots" / rel).resolve()
    if not str(full).startswith(str((job / "screenshots").resolve())): abort(403)
    if not full.exists(): abort(404)
    return send_from_directory(job / "screenshots", rel)


@app.route("/jobs/<job_id>/report")
@auth.login_required
def job_report(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    job = _job_dir(job_id)
    if not (job / "REPORT.html").exists():
        try: generate_report(job)
        except SystemExit: return ("No results yet", 404)
    return send_from_directory(job, "REPORT.html")


@app.route("/jobs/<job_id>/file/<path:rel>")
@auth.login_required
def job_file(job_id: str, rel: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    job = _job_dir(job_id)
    full = (job / rel).resolve()
    if not str(full).startswith(str(job.resolve())): abort(403)
    if not full.exists(): abort(404)
    return send_from_directory(job, rel)


@app.route("/jobs/<job_id>/export/csv")
@auth.login_required
def job_export_csv(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    results = _all_results_for_run(job_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id","status","duration_ms","nl_query","run_sql_status","run_sql_rows",
                "run_sql_columns","generate_viz_status","chart_type",
                "fail_reasons","warn_reasons","error"])
    for r in results:
        v = r.get("validations") or {}
        rs = r.get("run_sql_call") or {}; gv = r.get("generate_viz_call") or {}
        w.writerow([
            r.get("id"), r.get("overall_status"), r.get("total_duration_ms"),
            (r.get("nl_query") or "")[:200], rs.get("status"),
            v.get("run_sql_row_count"),
            "|".join(map(str, v.get("run_sql_columns") or [])),
            gv.get("status"), v.get("generate_viz_chart_type"),
            "|".join(v.get("fail_reasons") or []),
            "|".join(v.get("warn_reasons") or []),
            (r.get("error") or "")[:300].replace("\n", " "),
        ])
    return Response(buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{job_id}-results.csv"'})


@app.route("/jobs/<job_id>/export/failures.xlsx")
@auth.login_required
def job_export_failures_xlsx(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    from openpyxl import Workbook
    results = _all_results_for_run(job_id)
    bad = [r for r in results if r.get("overall_status") in ("FAIL","PARTIAL","TIMEOUT")]
    wb = Workbook(); ws = wb.active; ws.title = "Failed queries"
    ws.append(["question","expected_sql","status","duration_ms",
               "fail_reasons","warn_reasons","run_sql_status","generate_viz_status","error_summary"])
    for r in bad:
        v = r.get("validations") or {}; rs = r.get("run_sql_call") or {}; gv = r.get("generate_viz_call") or {}
        err = (r.get("error") or "").splitlines()[0][:200] if r.get("error") else ""
        ws.append([
            r.get("nl_query"), r.get("expected_sql") or "",
            r.get("overall_status"), r.get("total_duration_ms"),
            "; ".join(v.get("fail_reasons") or []),
            "; ".join(v.get("warn_reasons") or []),
            rs.get("status"), gv.get("status"), err,
        ])
    ws.column_dimensions["A"].width = 60; ws.column_dimensions["B"].width = 40
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return Response(buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{job_id}-failures.xlsx"',
                 "X-Failure-Count": str(len(bad)), "X-Total-Count": str(len(results))})


@app.route("/jobs/<job_id>/download")
@auth.login_required
def job_download_zip(job_id: str):
    if not _run_owned_by_current_user(job_id): abort(404)
    job = _job_dir(job_id)
    if not job.exists(): abort(404)
    if not (job / "REPORT.html").exists():
        try: generate_report(job)
        except Exception: return ("Could not generate report yet", 500)
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for include in ("REPORT.html","REPORT.md","SUMMARY.json","all_results.json","job.json","questions.xlsx"):
            p = job / include
            if p.exists(): z.write(p, arcname=p.name)
        for sub in ("screenshots","results","network_logs"):
            d = job / sub
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file(): z.write(f, arcname=f"{sub}/{f.name}")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job_id}-report.zip"'})


# ---------------------------------------------------------------------------
# JSON APIs (all user-scoped)
# ---------------------------------------------------------------------------
def _runs_for_user_query(user_filter_clause: str = "") -> str:
    return f"""
    SELECT r.id, r.user_id, r.login_url, r.username, r.machine_id, r.sql_agent_path,
           r.question_count, r.status, r.summary, r.created_at, r.started_at, r.finished_at,
           r.test_file_name,
           COALESCE((SELECT COUNT(*) FROM query_results q WHERE q.run_id = r.id AND q.status = 'PASS'), 0)    AS pass_n,
           COALESCE((SELECT COUNT(*) FROM query_results q WHERE q.run_id = r.id AND q.status = 'PARTIAL'), 0) AS partial_n,
           COALESCE((SELECT COUNT(*) FROM query_results q WHERE q.run_id = r.id AND q.status = 'FAIL'), 0)    AS fail_n,
           COALESCE((SELECT COUNT(*) FROM query_results q WHERE q.run_id = r.id AND q.status = 'TIMEOUT'), 0) AS timeout_n
      FROM runs r
     {user_filter_clause}
     ORDER BY r.created_at DESC
    """


def _list_user_runs(limit: int | None = None) -> list[dict[str, Any]]:
    sql = _runs_for_user_query("WHERE r.user_id = %s")
    params: tuple = (auth.current_user_id(),)
    if limit: sql += f" LIMIT {int(limit)}"
    rows = db.fetch_all(sql, params)
    out = []
    for r in rows:
        out.append({
            "id": r["id"], "login_url": r["login_url"], "username": r["username"],
            "machine_id": r["machine_id"], "sql_agent_path": r["sql_agent_path"],
            "question_count": r["question_count"], "status": r["status"],
            "summary": {"PASS": r["pass_n"], "PARTIAL": r["partial_n"],
                        "FAIL": r["fail_n"], "TIMEOUT": r["timeout_n"]},
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            "test_file_name": r.get("test_file_name"),
        })
    return out


@app.route("/api/runs")
@auth.login_required
def api_runs():
    runs = _list_user_runs()
    return jsonify({"runs": runs, "count": len(runs)})


@app.route("/api/runs/export.csv")
@auth.login_required
def api_runs_csv():
    runs = _list_user_runs()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id","created_at","started_at","finished_at","status",
                "login_url","username","questions","PASS","PARTIAL","FAIL","TIMEOUT"])
    for r in runs:
        s = r.get("summary") or {}
        w.writerow([r.get("id"), r.get("created_at"), r.get("started_at"), r.get("finished_at"),
                    r.get("status"), r.get("login_url"), r.get("username"),
                    r.get("question_count") or 0,
                    s.get("PASS",0), s.get("PARTIAL",0), s.get("FAIL",0), s.get("TIMEOUT",0)])
    return Response(buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="all-runs.csv"'})


@app.route("/api/stats")
@auth.login_required
def api_stats():
    runs = _list_user_runs()
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    runs_last_7d = queries_last_7d = 0
    total_pass = total_partial = total_fail = total_timeout = 0
    durations: list[int] = []; failure_counter: Counter[str] = Counter()
    daily: dict[str, dict[str, int]] = {}

    for r in runs:
        try:
            created_dt = datetime.fromisoformat(r["created_at"]) if r.get("created_at") else None
        except Exception:
            created_dt = None
        s = r.get("summary") or {}
        run_total = sum(s.get(k, 0) for k in ("PASS","PARTIAL","FAIL","TIMEOUT"))
        if created_dt and created_dt >= cutoff_7d:
            runs_last_7d += 1; queries_last_7d += run_total
        total_pass += s.get("PASS", 0); total_partial += s.get("PARTIAL", 0)
        total_fail += s.get("FAIL", 0); total_timeout += s.get("TIMEOUT", 0)
        if created_dt:
            day = created_dt.strftime("%Y-%m-%d")
            d = daily.setdefault(day, {"queries": 0, "pass": 0, "fail": 0})
            d["queries"] += run_total
            d["pass"] += s.get("PASS", 0)
            d["fail"] += s.get("FAIL", 0) + s.get("TIMEOUT", 0)
        for qr in _all_results_for_run(r["id"]):
            if qr.get("total_duration_ms"): durations.append(qr["total_duration_ms"])
            v = qr.get("validations") or {}
            for fr in v.get("fail_reasons") or []:
                failure_counter[fr] += 1

    total_queries = total_pass + total_partial + total_fail + total_timeout
    avg_ms = int(sum(durations) / len(durations)) if durations else 0
    series = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        d = daily.get(day, {"queries": 0, "pass": 0, "fail": 0})
        series.append({"date": day[5:], **d})
    return jsonify({
        "totals": {"runs": len(runs), "queries": total_queries,
                   "pass": total_pass, "partial": total_partial,
                   "fail": total_fail, "timeout": total_timeout, "avg_ms": avg_ms,
                   "runs_last_7d": runs_last_7d, "queries_last_7d": queries_last_7d},
        "daily": series,
        "top_failures": [{"reason": r, "count": n} for r, n in failure_counter.most_common(10)],
        "recent_runs": [{"id": r["id"], "status": r["status"],
                         "created_at": r["created_at"], "summary": r["summary"]}
                        for r in runs[:10]],
    })


@app.route("/api/preview-questions", methods=["POST"])
@auth.login_required
def api_preview_questions():
    f = request.files.get("questions")
    if not f: return jsonify({"error": "no file uploaded"}), 400
    tmp = DATA_DIR / f"_preview_{uuid.uuid4().hex[:8]}.xlsx"
    try:
        f.save(str(tmp))
        try: qs = read_questions(tmp)
        except Exception as e: return jsonify({"error": str(e)}), 400
        warnings: list[str] = []
        for q in qs[:20]:
            txt = (q.get("natural_language_query") or "").strip()
            if len(txt) < 5:
                warnings.append(f"Row {q['id']}: question is very short — \"{txt}\"")
            elif txt[0].isdigit() and ":" in txt[:8]:
                warnings.append(f"Row {q['id']}: looks like a timestamp — \"{txt[:30]}\". Make sure column A contains the question, not a date.")
        return jsonify({"total": len(qs), "preview": qs[:20], "warnings": list(dict.fromkeys(warnings))[:10]})
    finally:
        try: tmp.unlink()
        except Exception: pass


# Test files (per-user)
@app.route("/api/test-files", methods=["GET", "POST"])
@auth.login_required
def api_test_files():
    if request.method == "GET":
        rows = db.fetch_all(
            "SELECT * FROM test_files WHERE user_id = %s ORDER BY uploaded_at DESC",
            (auth.current_user_id(),),
        )
        return jsonify({"files": [
            {"id": r["id"], "filename": r["filename"], "original_name": r["original_name"],
             "question_count": r["question_count"], "size_bytes": r["size_bytes"],
             "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None}
            for r in rows]})
    f = request.files.get("file")
    if not f: return jsonify({"error": "no file uploaded (field name: 'file')"}), 400
    file_id = uuid.uuid4().hex[:10]
    safe = (f.filename or "upload.xlsx").replace("/", "_").replace("\\", "_")
    if not safe.lower().endswith(".xlsx"): safe += ".xlsx"
    stored_name = f"{file_id}-{safe}"
    stored_path = TEST_FILES_DIR / stored_name
    f.save(str(stored_path))
    try: qs = read_questions(stored_path)
    except Exception as e:
        try: stored_path.unlink()
        except Exception: pass
        return jsonify({"error": f"Could not parse uploaded .xlsx: {e}"}), 400
    db.execute(
        """INSERT INTO test_files (id, user_id, filename, original_name, question_count, size_bytes)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (file_id, auth.current_user_id(), stored_name, safe, len(qs), stored_path.stat().st_size),
    )
    row = db.fetch_one("SELECT * FROM test_files WHERE id = %s", (file_id,))
    return jsonify({"file": {
        "id": row["id"], "filename": row["filename"], "original_name": row["original_name"],
        "question_count": row["question_count"], "size_bytes": row["size_bytes"],
        "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
    }}), 201


def _user_test_file(file_id: str) -> dict[str, Any] | None:
    return db.fetch_one(
        "SELECT * FROM test_files WHERE id = %s AND user_id = %s",
        (file_id, auth.current_user_id()),
    )


@app.route("/api/test-files/<file_id>", methods=["DELETE"])
@auth.login_required
def api_test_file_delete(file_id: str):
    row = _user_test_file(file_id)
    if not row: return jsonify({"error": "not found"}), 404
    try: (TEST_FILES_DIR / row["filename"]).unlink()
    except Exception: pass
    db.execute("DELETE FROM test_files WHERE id = %s", (file_id,))
    return jsonify({"ok": True})


@app.route("/api/test-files/<file_id>/preview")
@auth.login_required
def api_test_file_preview(file_id: str):
    row = _user_test_file(file_id)
    if not row: return jsonify({"error": "not found"}), 404
    try: qs = read_questions(TEST_FILES_DIR / row["filename"])
    except Exception as e: return jsonify({"error": str(e)}), 500
    return jsonify({"total": len(qs), "preview": qs[:20], "meta": {
        "id": row["id"], "original_name": row["original_name"],
        "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
    }})


@app.route("/api/test-files/<file_id>/download")
@auth.login_required
def api_test_file_download(file_id: str):
    row = _user_test_file(file_id)
    if not row: abort(404)
    return send_from_directory(TEST_FILES_DIR, row["filename"],
        as_attachment=True, download_name=row["original_name"])


# Presets (per-user)
@app.route("/api/presets", methods=["GET", "POST"])
@auth.login_required
def api_presets():
    if request.method == "GET":
        rows = db.fetch_all(
            "SELECT * FROM presets WHERE user_id = %s ORDER BY created_at DESC",
            (auth.current_user_id(),))
        return jsonify({"presets": [
            {"id": r["id"], "name": r["name"], "login_url": r["login_url"],
             "username": r["username"], "machine_id": r["machine_id"],
             "sql_agent_path": r["sql_agent_path"],
             "run_sql_timeout_ms": r["run_sql_timeout_ms"],
             "gen_viz_timeout_ms": r["gen_viz_timeout_ms"],
             "created_at": r["created_at"].isoformat() if r["created_at"] else None}
            for r in rows]})
    body = request.get_json(silent=True) or {}
    if not body.get("name") or not body.get("login_url"):
        return jsonify({"error": "name and login_url are required"}), 400
    pid = uuid.uuid4().hex[:10]
    db.execute(
        """INSERT INTO presets (id, user_id, name, login_url, username,
                                 machine_id, sql_agent_path,
                                 run_sql_timeout_ms, gen_viz_timeout_ms)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (pid, auth.current_user_id(),
         str(body["name"]).strip()[:80], str(body["login_url"]).strip(),
         str(body.get("username") or "").strip(),
         str(body.get("machine_id") or "100").strip(),
         str(body.get("sql_agent_path") or "/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent").strip(),
         int(body.get("run_sql_timeout_ms") or 120_000),
         int(body.get("gen_viz_timeout_ms") or 120_000)),
    )
    row = db.fetch_one("SELECT * FROM presets WHERE id = %s", (pid,))
    return jsonify({"preset": {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                               for k, v in row.items()}}), 201


@app.route("/api/presets/<preset_id>", methods=["DELETE"])
@auth.login_required
def api_preset_delete(preset_id: str):
    row = db.fetch_one("SELECT id FROM presets WHERE id = %s AND user_id = %s",
                       (preset_id, auth.current_user_id()))
    if not row: return jsonify({"error": "not found"}), 404
    db.execute("DELETE FROM presets WHERE id = %s", (preset_id,))
    return jsonify({"ok": True})


# Whoami (handy for the UI + debugging)
@app.route("/api/me")
@auth.login_required
def api_me():
    u = g.user.copy()
    if u.get("created_at"): u["created_at"] = u["created_at"].isoformat()
    if u.get("last_login_at"): u["last_login_at"] = u["last_login_at"].isoformat()
    return jsonify({"user": u})


# ---------------------------------------------------------------------------
def main() -> None:
    import argparse, webbrowser
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5050)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    url = f"http://{args.host}:{args.port}/"
    print(f"Skylar IQ QA Tool v{APP_VERSION} — {url}")
    if not args.no_browser:
        try: threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        except Exception: pass
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
