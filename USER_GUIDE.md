# Skylar IQ QA Tool — User Documentation

> **A self-service automation suite for QA-testing the Celerant Back Office Skylar IQ
> SQL Agent on any tenant.** Provide a login URL, credentials, and an Excel file of
> natural-language questions; the tool drives the real Skylar IQ UI through a headless
> browser, captures every API call, and produces a polished QA report.

---

## Table of contents

1. [What this tool does](#1-what-this-tool-does)
2. [Before you start — prerequisites](#2-before-you-start--prerequisites)
3. [Installation (one-time, ~5 minutes)](#3-installation-one-time-5-minutes)
4. [Your first run (using the sample file)](#4-your-first-run-using-the-sample-file)
5. [Running with your own questions](#5-running-with-your-own-questions)
6. [Excel file format](#6-excel-file-format)
7. [Understanding the live progress page](#7-understanding-the-live-progress-page)
8. [Understanding the final report](#8-understanding-the-final-report)
9. [Result statuses explained](#9-result-statuses-explained)
10. [Configuration options](#10-configuration-options)
11. [Command-line mode (advanced)](#11-command-line-mode-advanced)
12. [Sharing reports with stakeholders](#12-sharing-reports-with-stakeholders)
13. [Troubleshooting](#13-troubleshooting)
14. [FAQ](#14-faq)
15. [How the tool works (architecture)](#15-how-the-tool-works-architecture)

---

## 1. What this tool does

When testing the Skylar IQ SQL Agent manually, a QA engineer would have to:

1. Open the client's Celerant Back Office login page
2. Enter username + password + handle the Machine ID quirk
3. Click **Setup → SQL Agent**
4. Type a natural-language question into the chat box
5. Wait for the result table to appear
6. Click **Generate Visualization** if available
7. Open browser DevTools to inspect the API calls
8. Repeat for every question
9. Manually compile a report

This tool **automates that entire workflow** for any number of questions, against
**any client tenant**, and produces a structured QA report with screenshots and
raw API data — so you can run regression tests for multiple clients in parallel
or as part of a scheduled job.

### What it captures per query

| Captured | Detail |
|---|---|
| **`generate_sql` API call** | The LLM call that converts the natural-language question into SQL — request body, response status, response payload, timing |
| **`run-sql` API call** | The actual SQL execution against the client's database — full request and response |
| **`generate-viz` API call** | The chart-generation LLM call — chart type, axes, columns, data points |
| **Screenshots** | Input box (before submit), result table (after run-sql), chart (after generate-viz) |
| **Validations** | HTTP status, row counts, column-name sync, chart payload integrity |

---

## 2. Before you start — prerequisites

You need:

| Requirement | How to check | If missing |
|---|---|---|
| **Python 3.10 or newer** | `python3 --version` in a terminal | Install from [python.org](https://www.python.org/downloads/) (Mac/Win) or `apt install python3` (Linux) |
| **`pip` (Python package manager)** | `python3 -m pip --version` | Comes with Python 3.4+; otherwise `python3 -m ensurepip` |
| **`git` command** | `git --version` | Install from [git-scm.com](https://git-scm.com/downloads) |
| **A modern browser** (Chrome, Firefox, Edge, Safari) | for opening the local web UI | already on your machine |
| **~200 MB free disk space** | for the Playwright browser binary | `df -h` |
| **Internet access** | to download dependencies (one-time) and to reach the client's Skylar IQ instance | |

> 💡 **Note:** You do NOT need to install Chrome separately for the tool —
> Playwright downloads its own headless Chromium during install.

---

## 3. Installation (one-time, ~5 minutes)

### Step 3.1 — Clone the repository

In your terminal, run:

```bash
git clone https://github.com/farhan713/skylar-qa-tool.git
cd skylar-qa-tool
```

(Replace the URL with whatever your repo URL is.)

> **What this does:** Downloads the latest version of the tool's source code into
> a folder called `skylar-qa-tool` and changes your working directory into it.

---

### Step 3.2 — Install Python dependencies

```bash
python3 -m pip install -r requirements.txt
```

> **What this does:** Reads the `requirements.txt` file and installs everything
> the tool depends on — Playwright (browser automation), Flask (web UI), openpyxl
> (Excel reading), Jinja2 (HTML templating).
>
> **Expected duration:** ~30 seconds. You'll see lines like
> `Successfully installed playwright-1.49.0 flask-3.1.0 ...`

If you see permission errors on Mac/Linux, prefix with `sudo`:
```bash
sudo python3 -m pip install -r requirements.txt
```
On Windows, run the terminal as Administrator.

---

### Step 3.3 — Install the headless browser (one-time)

```bash
python3 -m playwright install chromium
```

> **What this does:** Downloads the headless Chromium browser that the tool will
> use to drive the Skylar IQ UI. It's stored in your user's cache folder, not the
> repo, so it only needs to be done once per machine — not per-clone.
>
> **Expected duration:** ~30 seconds. You'll see a download progress bar reaching
> 100% of ~150 MB.

---

### Step 3.4 — Verify the install

```bash
python3 -c "from app.runner import run; print('OK')"
```

If you see `OK`, the install succeeded. If you see `ModuleNotFoundError: No module named 'playwright'`, go back to **Step 3.2**.

---

## 4. Your first run (using the sample file)

A 5-question sample (`data/sample_questions.xlsx`) ships with the tool so you
can verify everything works before importing your own questions.

### Step 4.1 — Launch the web UI

```bash
./run-server.sh
```

(On Windows: `python -m app.server`)

> **What you'll see in the terminal:**
> ```
> Skylar IQ QA Tool — http://127.0.0.1:5050/
>  * Running on http://127.0.0.1:5050
> ```
>
> **What happens next:** Your default browser opens automatically to that URL.
> If it doesn't, copy/paste the URL into your browser manually.

---

### Step 4.2 — Fill in the form

The landing page shows a **Start a new run** form. Fill in:

| Field | What to enter for the test run |
|---|---|
| **Login URL** | The full Skylar IQ login URL of the client you want to test, e.g. `https://acme-store.com:8443/backoffice/?mid=100` |
| **Username** | The Skylar IQ username for that client |
| **Password** | The matching password |
| **Machine ID** | Leave at `100` unless your client uses a different value |
| **SQL Agent path** | Leave at the default unless told otherwise |
| **run-sql timeout (ms)** | `120000` (2 minutes) is fine for most cases |
| **generate-viz timeout (ms)** | `120000` (2 minutes) |
| **Questions Excel** | Click **Choose File** and pick `data/sample_questions.xlsx` from the cloned repo |

Click **Start QA Run**.

---

### Step 4.3 — Watch it run

You're redirected to the live progress page. You'll see:

- **Configuration table** at the top showing exactly what was submitted
- **Status badge**: `queued` → `running` → `done` (or `failed`)
- **Counters** for PASS / PARTIAL / FAIL / TIMEOUT updating in real time
- **Progress bar** filling up as queries complete
- **Last 5 queries** table showing per-query status and duration
- **Event log** (a black panel) streaming every action:
  ```
  [login] navigating https://...
  [login] success — at https://.../wrmsscreen
  [nav] SQL Agent ready
  [q01] Show me a list of all my calibers
  [q01] PASS (5764 ms)
  [q02] ...
  ```

> **Expected duration for the 5-question sample:** 1–10 minutes depending on
> client LLM speed. Some queries finish in 6 seconds; others (especially aggregate
> queries with joins) can take 60+ seconds.

When the run finishes:
- Status badge turns green: **`done`**
- An **Open final report ↗** button appears
- The final HTML report opens in a new tab

---

## 5. Running with your own questions

Once you've confirmed the sample works, replace it with your own Excel file:

1. Prepare your `.xlsx` (see [Section 6](#6-excel-file-format))
2. Refresh the web UI at `http://127.0.0.1:5050/`
3. Fill the form again, but this time upload your own `.xlsx`
4. Click **Start QA Run**

There's no limit on the number of questions — runs of 50, 100, or 500+ are fine.
Per-query budget defaults to 2 minutes, so you can size-estimate by:

> Total runtime ≈ (fast queries × 10 sec) + (slow queries × ~120 sec)

---

## 6. Excel file format

Your `.xlsx` must look like this (only the **first sheet** is read):

| natural_language_query | expected_sql *(optional)* |
|---|---|
| Show me a list of all my calibers | `SELECT DISTINCT caliber FROM ...` |
| Top 10 brands by sales this year | `SELECT TOP 10 brand, SUM(extended) ...` |
| Which items have the highest return rate? | |

### Rules

- **Column A** must contain the natural-language question (required, must be non-empty)
- **Column B** is the expected SQL (optional — used as a reference, not enforced or compared)
- **Header row** is auto-detected: if the first cell of row 1 is `natural_language_query`, `question`, `query`, or `nl_query`, that row is treated as headers and skipped
- **Empty rows** are silently skipped
- Any **additional columns** (C, D, …) are ignored

### Tips

- Use clear, business-friendly English (the LLM is trained on natural questions)
- Avoid SQL jargon in column A — that's not what the agent expects
- Start each run with a small file (5–10 questions) to verify the client's instance is healthy before unleashing 100+

---

## 7. Understanding the live progress page

| Element | Meaning |
|---|---|
| **Configuration table** | Snapshot of exactly what you submitted — useful for re-creating the run later |
| **Status badge** (top-right) | `queued` (waiting for browser to start) → `running` → `done` / `failed` |
| **Counters row** | PASS / PARTIAL / FAIL / TIMEOUT counts; "Done X / Y" totals completed |
| **Progress bar** | Visual completion |
| **Last 5 queries** table | Most recent results — refreshes every 3 seconds |
| **Event log** | Live tail of every action the runner takes; useful for debugging stuck runs |
| **Open final report ↗** | Appears only after the run completes; opens the full HTML deliverable |

The page **persists** even if you close the browser — the runner keeps going in
the background and you can return to the URL (e.g. from the Past runs list on
the home page) at any time to check progress.

---

## 8. Understanding the final report

After clicking **Open final report ↗** (or navigating to `runs/<job-id>/REPORT.html`),
you'll see a structured report with these sections:

### 8.1 — Executive summary

A grid of headline numbers:

- Total queries
- PASS / PARTIAL / FAIL / TIMEOUT counts
- Average per-query duration
- Maximum duration

### 8.2 — API health table

| Endpoint | Captured | HTTP 2xx | Usable payload |
|---|---|---|---|
| `run-sql` | 45 / 55 | 39 / 55 | 38 / 55 (rows>0) |
| `generate-viz` | 33 / 55 | 33 / 55 | 33 / 55 (chart) |

This tells you at a glance:
- How many queries even reached the SQL execution step
- How many returned successful HTTP responses
- How many returned actual data (not empty result sets)

### 8.3 — Failing queries / Partial / Timed-out queries

Three lists, with the failing reason next to each query. For example:

> **q03** — What firearm brands are my top selling brands for this year?
> ⚠ columns differ between run-sql and generate-viz
> ⚠ run-sql returned 1 column(s) with empty/missing name (SQL aliasing bug)

### 8.4 — Per-query detail

For each of the queries, an expandable section containing:

- **run-sql row**: HTTP method, full URL, status, duration, returned columns, row count
- **generate-viz row**: HTTP method, full URL, status, duration, chart type, x/y axes
- **Columns synced** indicator (true/false/null)
- **Fail / warn reasons**
- **run-sql request body** (collapsed) — what was sent
- **run-sql response body** (collapsed) — what came back
- **generate-viz request body** (collapsed)
- **generate-viz response body** (collapsed)
- **Screenshots** (collapsed) — input, results table, chart

You can search the report (Cmd+F / Ctrl+F) to find specific queries.

---

## 9. Result statuses explained

| Badge | Color | Meaning |
|---|---|---|
| 🟢 **PASS** | Green | Everything green: `run-sql` returned 2xx with rows; if a chart was expected, `generate-viz` returned a valid payload; columns synced |
| 🟡 **PARTIAL** | Yellow | Data was captured but with at least one warning. Common causes: `run-sql` returned no rows; column names differ between `run-sql` output and `generate-viz` axes; SQL had unaliased columns producing empty-string column names |
| 🔴 **FAIL** | Red | Hard failure. `run-sql` was missing entirely OR returned an HTTP error (4xx/5xx); or `generate-viz` was expected but returned an HTTP error |
| 🟣 **TIMEOUT** | Purple | The configured per-query budget was exceeded. The runner reloads the SQL Agent page automatically and proceeds to the next question. The `generate-sql` LLM service likely returned `HTTP 500` or hung. |

> **Note on PARTIAL:** A PARTIAL is *not* a tool failure — it means the
> Skylar IQ SQL Agent returned data, but with a quality issue worth investigating.
> The "columns differ" warning, in particular, is usually a real bug in the
> agent's SQL generation.

---

## 10. Configuration options

| Option | Default | When to change |
|---|---|---|
| **Login URL** | (you supply) | Always — different for each client |
| **Username / Password** | (you supply) | Always |
| **Machine ID** | `100` | If your client's Celerant install uses a different MID. Leave blank to skip the localStorage step entirely. |
| **SQL Agent path** | `/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent` | Rarely. Only if a tenant has a customised SPA route. |
| **run-sql timeout (ms)** | `120000` (2 min) | Increase to `300000` (5 min) or `600000` (10 min) if your client's LLM is slow |
| **generate-viz timeout (ms)** | `120000` (2 min) | Same — slow chart generation = bump this |

---

## 11. Command-line mode (advanced)

If you'd rather skip the web UI (e.g. for CI/CD or scripted batch runs):

```bash
python3 -m app.runner \
  --login-url 'https://client-host:8443/backoffice/?mid=100' \
  --username myuser \
  --password 'mypass' \
  --questions /absolute/path/to/questions.xlsx \
  --output-dir runs/my-run-2026-04-29 \
  --machine-id 100 \
  --run-sql-timeout 120000 \
  --gen-viz-timeout 120000
```

After the run completes, generate the report:

```bash
python3 -m app.report --job-dir runs/my-run-2026-04-29
```

This writes `REPORT.html`, `REPORT.md`, `SUMMARY.json` into that folder.

> **Tip for CI:** Pass `--no-headless` if you want to watch the browser; omit
> for fully headless (default).

---

## 12. Sharing reports with stakeholders

Every run creates a folder `runs/<job-id>/` that is **fully self-contained**:

```
runs/<job-id>/
├── REPORT.html         ← THE deliverable — open in any browser
├── REPORT.md           ← Markdown copy
├── SUMMARY.json        ← Top-level stats only
├── job.json            ← Original config (so the run is reproducible)
├── questions.xlsx      ← The input file
├── events.log          ← Every action the runner took
├── all_results.json    ← Aggregate of every per-query record
├── results/            ← One JSON per query
├── network_logs/       ← Raw API call dumps
└── screenshots/        ← All captured screenshots
```

To share:

- **Just the report** → email `REPORT.html`. It works offline.
- **Report + screenshots** → zip the whole `runs/<job-id>/` folder
- **Just summary stats** → send `SUMMARY.json`

---

## 13. Troubleshooting

### "Login failed: Machine ID is empty"

The Celerant server requires the `machineid` parameter. Two fixes:

1. Make sure your **Login URL includes `?mid=100`** (or whatever value the client uses)
2. Or fill in the **Machine ID** field on the form

If both are set correctly and you still see this, the client may have a custom Machine ID — check with the Celerant admin.

### Lots of TIMEOUTs (everything times out at exactly 2 minutes)

Two possibilities:

1. **The client's LLM service is slow.** Bump both timeouts to `600000` (10 minutes) and re-run.
2. **The LLM service is broken / returning 500.** Check the run's event log for `generate-sql HTTP 500` — if you see this, the service-side LLM is errored. Wait an hour, retry. This is a service-side issue, not a tool issue.

### "jQuery submit handler not bound" (login times out)

The Celerant login page failed to load its JavaScript. Open the login URL manually in a browser to verify connectivity. If it loads in a browser but not the tool, check:

- Are you behind a corporate proxy? Set `HTTPS_PROXY` env var before launching
- Is the SSL certificate self-signed? The tool ignores cert errors by default; if that's not working, file a bug

### Web UI says "Address already in use" on launch

Another process has port 5050 occupied. Either:

- Stop the other process: `lsof -i :5050` to see what's using it, then kill it
- Use a different port: `python3 -m app.server --port 5051`

### Port 5050 not opening in browser

Manually navigate to `http://127.0.0.1:5050/` (sometimes auto-open is blocked).

### Excel file rejected: "no usable rows found"

- Make sure column **A** has the questions (not column B or C)
- Make sure rows aren't all in column B
- Check the file isn't password-protected
- Try saving as a fresh `.xlsx` (not `.xls` or `.csv`)

### Report shows `with_chart=0` for all queries

The chart-payload heuristic doesn't recognise the response format. Inspect a single query:

```bash
cat runs/<job-id>/results/q01.json | python3 -m json.tool | less
```

If the response shape is different from `responseBody.data.visualizations[0]`, file a bug or update `inspect_chart_payload()` in `app/runner.py`.

---

## 14. FAQ

### How long does a typical run take?

For 50 questions with a healthy LLM service:
- Best case (all fast queries): **10 minutes**
- Average mix: **30–60 minutes**
- Worst case (every query hits the 2-min timeout): **~110 minutes** (because timeouts skip)

### Can I run multiple jobs in parallel?

Yes — the web UI supports it. Each job runs in its own thread with its own browser context. However, hitting the same Skylar IQ instance with multiple parallel sessions may cause the LLM to rate-limit you. Recommend max 2–3 parallel.

### Can I stop a run mid-flight?

The web UI doesn't have a stop button yet. To stop:

```bash
# Find the runner process
ps -ef | grep "app.runner\|app.server"
# Kill it
kill <pid>
```

The per-query JSONs already written to `runs/<job-id>/results/` will be preserved.

### Where are the credentials stored?

Credentials are submitted via the form, stored only in:
- The current run's `job.json` file (containing username only — passwords are NOT persisted)
- Memory while the runner is active

They are not logged. If you want extra safety, run on an isolated machine and `rm -rf runs/` after testing.

### Does it support headed mode (visible browser)?

CLI yes — pass `--no-headless`. Web UI currently always runs headless to keep the server portable.

### Can I retry just the failed queries?

Not yet. You'd have to:
1. Open the original `runs/<job-id>/questions.xlsx` and the `SUMMARY.json`
2. Build a new `.xlsx` with only the failed/timed-out queries
3. Submit a new run

---

## 15. How the tool works (architecture)

```
┌─────────────────────┐    POST /jobs      ┌──────────────────────────┐
│ Web UI              │──────────────────▶ │ Flask backend (server.py)│
│ (browser form)      │                    │  - parses .xlsx          │
│                     │◀── SSE events ────│  - spawns runner thread  │
└─────────────────────┘                    │  - serves report        │
                                           └──────────┬───────────────┘
                                                      │ run(cfg)
                                                      ▼
                              ┌────────────────────────────────────────┐
                              │ app/runner.py                          │
                              │  - launches headless Chromium          │
                              │  - performs login + nav                │
                              │  - for each question:                  │
                              │      type, click send, expect_response │
                              │      capture run-sql, click viz,        │
                              │      expect_response capture viz       │
                              │      take screenshots                  │
                              │      validate + save qNN.json           │
                              └────────────────┬───────────────────────┘
                                               │ writes
                                               ▼
                              ┌────────────────────────────────────────┐
                              │ runs/<job-id>/                         │
                              │   results/qNN.json                     │
                              │   screenshots/                         │
                              │   network_logs/                        │
                              │   events.log                           │
                              │   all_results.json                     │
                              └────────────────┬───────────────────────┘
                                               │ feeds
                                               ▼
                              ┌────────────────────────────────────────┐
                              │ app/report.py                          │
                              │   REPORT.html / REPORT.md /            │
                              │   SUMMARY.json                          │
                              └────────────────────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **Playwright over Selenium** | Faster, more reliable, has built-in `expect_response` for waiting on specific API calls (which Selenium doesn't) |
| **Event-driven `expect_response` (not polling)** | Earlier polling-based wait missed responses by milliseconds, leading to false TIMEOUT classifications. Event-driven approach catches every response immediately. |
| **2-minute per-query budget with auto-recovery** | The Skylar IQ LLM has high variance (5s-300s+). A bounded budget keeps total runtime predictable while still capturing slow-but-completing queries. After a timeout, the SQL Agent page is reloaded so the next query has a clean slate. |
| **Per-job folder layout** | Each run is fully self-contained — easy to zip/share/archive. |
| **Flask + SSE for live progress** | Lightweight, no WebSocket complexity, works with curl/browser equally. |
| **Excel via openpyxl** | Most QA teams maintain test cases in Excel. Native `.xlsx` support avoids a CSV-conversion step. |

### Project layout

```
.
├── app/                     ← the tool (importable Python package)
│   ├── runner.py            Playwright-driven QA runner
│   ├── report.py            HTML / MD / JSON report generator
│   ├── excel_reader.py      .xlsx → list of questions
│   ├── server.py            Flask web UI
│   ├── templates/index.html Landing form
│   ├── templates/job.html   Live progress page
│   └── static/style.css
├── runs/                    ← per-job output folders (created at runtime, gitignored)
├── data/sample_questions.xlsx  ← ships with the repo, 5 questions for first-run test
├── tests/legacy/            ← reference scripts from the original 55-question Skylar IQ run
├── requirements.txt
├── run-server.sh            ← one-command launcher
├── README.md                ← short developer docs
├── USER_GUIDE.md            ← this file
└── .gitignore
```

---

## Need help?

For bugs, feature requests, or questions: contact the repo owner.
