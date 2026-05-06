"""
One-time migration: walk runs/ + data/test_files/ + data/presets.json on disk
and import every record into Postgres under a chosen owner.

Usage (inside the running container):
    python -m app.migrate_filesystem --owner-email admin@example.com
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from app import db


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner-email", required=True,
                    help="Email of the user every imported record will belong to")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db.init_schema()
    owner = db.fetch_one("SELECT id, email, role FROM users WHERE email = %s",
                         (args.owner_email.lower(),))
    if not owner:
        print(f"!! No user with email '{args.owner_email}'. Sign that user up first.")
        sys.exit(2)
    user_id = owner["id"]
    print(f"Owner: {owner['email']} ({owner['role']}) — id={user_id}")

    root = Path(__file__).resolve().parent.parent
    runs_dir = root / "runs"
    data_dir = root / "data"
    test_files_dir = data_dir / "test_files"
    presets_file = data_dir / "presets.json"

    runs_imported = qrs_imported = 0
    files_imported = 0
    presets_imported = 0

    # ---- Runs --------------------------------------------------------------
    for d in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        run_id = d.name
        meta_path = d / "job.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except Exception as e:
            print(f"  skip {run_id}: bad job.json ({e})"); continue
        existing = db.fetch_one("SELECT id FROM runs WHERE id = %s", (run_id,))
        if existing:
            continue
        print(f"  import run {run_id}")
        if not args.dry_run:
            db.execute(
                """INSERT INTO runs (id, user_id, login_url, username, machine_id,
                                     sql_agent_path, question_count, status, summary,
                                     created_at, started_at, finished_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
                           COALESCE(%s::timestamptz, NOW()), %s::timestamptz, %s::timestamptz)""",
                (run_id, user_id,
                 meta.get("login_url", ""), meta.get("username"),
                 meta.get("machine_id"), meta.get("sql_agent_path"),
                 meta.get("question_count"), meta.get("status", "done"),
                 db.jsonify(meta.get("summary")),
                 meta.get("created_at"), meta.get("started_at"), meta.get("finished_at")),
            )
        # Per-query rows
        for f in sorted((d / "results").glob("q*.json")):
            try:
                rec = json.loads(f.read_text())
            except Exception:
                continue
            if not args.dry_run:
                db.execute(
                    """INSERT INTO query_results (run_id, qid, status, duration_ms, nl_query, record)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (run_id, qid) DO NOTHING""",
                    (run_id, rec.get("id"), rec.get("overall_status"),
                     rec.get("total_duration_ms"), rec.get("nl_query"),
                     db.jsonify(rec)),
                )
                qrs_imported += 1
        runs_imported += 1

    # ---- Test files --------------------------------------------------------
    if test_files_dir.exists():
        for meta_path in test_files_dir.glob("*.meta.json"):
            try:
                m = json.loads(meta_path.read_text())
            except Exception:
                continue
            fid = m.get("id")
            if not fid: continue
            existing = db.fetch_one("SELECT id FROM test_files WHERE id = %s", (fid,))
            if existing: continue
            print(f"  import test file {fid} ({m.get('original_name')})")
            if not args.dry_run:
                db.execute(
                    """INSERT INTO test_files (id, user_id, filename, original_name,
                                                question_count, size_bytes, uploaded_at)
                       VALUES (%s,%s,%s,%s,%s,%s, COALESCE(%s::timestamptz, NOW()))""",
                    (fid, user_id, m["filename"], m.get("original_name", m["filename"]),
                     m.get("question_count"), m.get("size_bytes"), m.get("uploaded_at")),
                )
            files_imported += 1

    # ---- Presets -----------------------------------------------------------
    if presets_file.exists():
        try:
            items = json.loads(presets_file.read_text())
        except Exception:
            items = []
        for p in items:
            pid = p.get("id") or uuid.uuid4().hex[:10]
            if db.fetch_one("SELECT id FROM presets WHERE id = %s", (pid,)):
                continue
            print(f"  import preset {pid} ({p.get('name')})")
            if not args.dry_run:
                db.execute(
                    """INSERT INTO presets (id, user_id, name, login_url, username,
                                             machine_id, sql_agent_path,
                                             run_sql_timeout_ms, gen_viz_timeout_ms,
                                             created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, COALESCE(%s::timestamptz, NOW()))""",
                    (pid, user_id, p.get("name", "imported"), p.get("login_url"),
                     p.get("username"), p.get("machine_id"), p.get("sql_agent_path"),
                     p.get("run_sql_timeout_ms") or 120_000,
                     p.get("gen_viz_timeout_ms") or 120_000,
                     p.get("created_at")),
                )
            presets_imported += 1

    print()
    print(f"Imported: {runs_imported} runs ({qrs_imported} query results), "
          f"{files_imported} test files, {presets_imported} presets.")
    if args.dry_run:
        print("(dry run — nothing actually written)")


if __name__ == "__main__":
    main()
