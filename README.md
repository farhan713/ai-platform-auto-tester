# Skylar IQ QA Tool

Enterprise QA automation for **Celerant Skylar IQ** — a multi-user web app that drives the **SQL AI Engine** and **Site Search** through Playwright, capturing every request/response and producing rich reports.

Each QA on your team gets their own account. Their runs, uploaded test files, login presets and hosted bundles are private to them. Built on Flask + PostgreSQL + Playwright/Chromium, packaged as a single Docker stack, and ready for Azure (or any container platform).

---

## What it does

Two test types, same workflow shape:

### 🧠 SQL AI Engine
Logs into a Celerant tenant's Skylar IQ chat box, types every natural-language question from your `.xlsx`, captures the `generate-sql` → `run-sql` → `generate-viz` chain, validates response shape and column-name sync, screenshots input + result + chart, and grades each query **PASS / PARTIAL / FAIL / TIMEOUT**.

### 🔎 Site Search
Drives an `ssLibrary` widget — no login form, JWT exchanged in the page's `init()` call. Types each keyword, captures `search_keywords` and `search_results`, asserts non-empty results, screenshots the suggestions popup with categories / brands / products. Tenant config (`org_id`, `console URL`, JWT user/pass) is **runtime-overridable**, so the same page tests any tenant without editing the HTML.

For users with no public URL for their search page (local-only ssLibrary builds), upload the `dist/` zip once → the tool generates a private wrapper page at `/hosted/<id>/index.html` and runs against it.

---

## Highlights

| | |
|---|---|
| 🔐 **Multi-user** | Sign up / sign in. Per-user runs, test files, presets, hosted bundles. Optional `SQA_ALLOW_SIGNUP=false` to lock down public registration. |
| 📊 **Dashboard** | Pass-rate trend (30 days), outcome donut, top failure reasons, recent runs. |
| ▶ **Live progress** | Server-Sent Events stream every event line. Stop button mid-run; the runner aborts cleanly and still generates the report for what's done. |
| 🔬 **Per-query drill-down** | Full request + response (headers, body) for every captured XHR/fetch — `generate-sql`, `run-sql`, `generate-viz`, `search-keywords`, `search-results`. Copy-as-cURL. |
| 📸 **Screenshots** | Input state + results state, full-page, inline in both the live UI and final report. |
| 📥 **Downloads** | HTML report (`Open report ↗`), full report bundle as ZIP, **failed queries as Excel** (re-runnable), CSV export of any run, all-runs CSV. |
| 🌓 **Light + dark mode** | Toggle in the header, persisted per-browser. |
| 📦 **Hosted bundles** | Upload an ssLibrary `.js`/`.zip`, the tool serves it as a private test page so QA can run searches without a deployed URL. |
| ☁ **Cloud-ready** | Tested on **Azure Container Apps + Postgres Flexible Server**. Render.com blueprint included. Ships with `deploy/azure-deploy.sh` (one shell script does it all). |

---

## Quick start (local Docker)

Requires Docker Desktop (Mac/Windows) or Docker Engine (Linux).

```bash
git clone <repo-url> skylar-qa
cd skylar-qa
docker compose up -d
# ↳ first run: pulls Playwright base image (~1 GB) + builds, ~3 min
# ↳ then launches Postgres + the app together
open http://localhost:5050/
```

You'll be redirected to `/signup`. Create the first account — that becomes your QA. Add teammates either by sharing the URL (anyone can sign up) or by setting `SQA_ALLOW_SIGNUP=false` in `docker-compose.yml` and creating accounts manually via Postgres.

To stop:
```bash
docker compose down
```

To completely wipe state (⚠ deletes all runs + accounts):
```bash
docker compose down -v
```

---

## Cloud deploy (Azure)

The repo ships with a one-shot Bash script for Azure that provisions resource group → Postgres Flexible Server → Container Registry → Storage Account + File Share → Container Apps environment → the running app.

```bash
# Pre-reqs: Azure CLI installed, `az login` done
chmod +x deploy/azure-deploy.sh
deploy/azure-deploy.sh
# ↳ asks for resource group, region, Postgres password
# ↳ ~10 minutes later prints your https://*.azurecontainerapps.io URL
```

Approx. cost: **~$50/month** (Container App + Burstable Postgres B1ms + ACR Basic + ~5 GB Storage).

Other supported platforms in [`CLOUD_DEPLOY.md`](CLOUD_DEPLOY.md): **Render.com** (one-click via `render.yaml`), **Fly.io**, **DigitalOcean App Platform**, self-hosted VPS with Caddy.

---

## Architecture

```
┌────────────────┐       ┌────────────────────┐       ┌──────────────────┐
│ Flask app      │──────▶│ Background runner  │──────▶│ Playwright       │
│ (Gunicorn-     │       │ thread per job     │       │ Chromium headless│
│  ready)        │◀──────│ — SSE event stream │◀──────│ inside container │
└────┬───────────┘       └────────┬───────────┘       └──────────────────┘
     │ SQL / writes              │ writes per-query
     ▼                            ▼
┌────────────────┐       ┌────────────────────┐
│ PostgreSQL 16  │       │ Filesystem volume  │
│  users         │       │  /app/runs/<id>/   │
│  runs          │       │   screenshots/     │
│  query_results │       │   REPORT.html      │
│  test_files    │       │   results/qNN.json │
│  presets       │       │  /app/data/        │
│  hosted_bundles│       │   bundles/<id>/    │
└────────────────┘       │   test_files/      │
                         └────────────────────┘
```

- **Postgres** stores everything queryable: users, runs, per-query records (JSONB), test files, presets, hosted bundles.
- **Filesystem** stores everything large or binary: screenshots, generated reports, uploaded `.xlsx`, uploaded JS bundles. Mounted as a volume so it survives container restarts.

---

## Project layout

```
.
├── app/
│   ├── server.py                 # Flask app — routes, dispatching, auth, APIs
│   ├── runner.py                 # SQL Agent runner (Playwright)
│   ├── runner_sitesearch.py      # Site Search runner (Playwright)
│   ├── report.py                 # REPORT.html / .md / SUMMARY.json generator
│   ├── auth.py                   # signup / login / sessions / login_required
│   ├── db.py                     # Postgres connection pool + helpers
│   ├── schema.sql                # idempotent DB schema
│   ├── excel_reader.py           # .xlsx → list[questions/keywords]
│   ├── migrate_filesystem.py     # one-time migrator: filesystem → DB
│   ├── templates/                # Jinja2 — all pages
│   └── static/                   # CSS, JS, vendored Chart.js
├── deploy/
│   └── azure-deploy.sh           # one-shot Azure provisioning
├── data/                         # persisted state (presets, test files, bundles)
├── runs/                         # per-job artefacts (generated)
├── docker-compose.yml            # app + postgres
├── Dockerfile                    # Playwright base + Python deps
├── render.yaml                   # Render.com blueprint
├── requirements.txt
├── CLOUD_DEPLOY.md               # detailed cloud-deploy guide (Render / Fly / DO / Azure / VPS)
├── SETUP.md                      # legacy non-Docker Python setup
└── USER_GUIDE.md                 # end-user reference
```

---

## Tech stack

- **Backend**: Python 3.12, Flask, psycopg 3 (async-ready Postgres driver), Werkzeug auth
- **Browser automation**: Playwright 1.59 + Chromium (headless)
- **Database**: PostgreSQL 16
- **Frontend**: server-rendered Jinja2 templates, vanilla JS, Chart.js (vendored locally so it works air-gapped)
- **Container**: official `mcr.microsoft.com/playwright/python:v1.59.0-noble` base image
- **Auth**: PBKDF2-SHA256 (Werkzeug) password hashing, signed cookie sessions, 14-day lifetime

---

## Configuration

Set via environment variables (works in `docker-compose.yml` or any cloud platform):

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | (required) | `postgresql://user:pass@host:5432/dbname` — everything else (`PGHOST`, `PGUSER`, etc.) is consulted as fallback |
| `SQA_SECRET_KEY` | random per boot | Signs session cookies. **Set this in production**, otherwise sessions are invalidated every restart. |
| `SQA_ALLOW_SIGNUP` | `true` | Set to `false` to disable public signup once your team is in |

---

## Validations

Every query, both test types, gets one of four statuses:

| Status | Meaning |
|---|---|
| **PASS** | All assertions green |
| **PARTIAL** | Warning(s) — e.g. zero rows returned, columns mismatch |
| **FAIL** | A hard failure — call missing, HTTP non-2xx |
| **TIMEOUT** | A request didn't complete within the per-query budget |

For full validation specs, see [USER_GUIDE.md](USER_GUIDE.md).

---

## Development

```bash
# Run the test suite (requires Postgres running)
docker compose up -d db
DATABASE_URL=postgresql://skylar:skylar@localhost:5432/skylar python -m app.server

# Or full stack:
docker compose up -d
docker compose logs -f skylar-qa
```

Hot-reload isn't on by default (Flask dev server is intentionally off in container).

To run a one-off migration of legacy filesystem data into Postgres:

```bash
docker exec skylar-qa python -m app.migrate_filesystem --owner-email you@example.com
```

---

## Security notes

- **Password hashes** stored with PBKDF2-SHA256 (Werkzeug default) — never plaintext.
- **Sensitive HTTP headers** (`Authorization`, `Cookie`, `X-CSRF-Token`, etc.) are **redacted** before being shown in the UI or report.
- **Tenant credentials** (Skylar IQ login passwords, JWT passwords) are passed only at run-creation time; never stored in presets unless you explicitly include them. Login presets only persist the URL/username/machine ID — never passwords.
- **Per-user data isolation**: every read endpoint filters by `user_id`. Bob can't view, list, or guess Alice's runs/files even with the run ID.
- **Hosted bundle URLs** use 32-char random hex slugs. Only the owner ever sees the URL.

---

## License

Internal QA automation. Not for external distribution without permission.
