# Skylar IQ QA Tool — Tester Guide

A web-based tool that drives the Celerant **SQL AI Engine** and **Site Search** through real browser automation, captures every API call, and produces detailed reports. You upload a list of test inputs, the tool runs them all, you read the report.

---

## 1 · Get access

### The live URL

> 🌐 **https://ai-platform-auto-tester.thankfulmushroom-67b2c86a.centralus.azurecontainerapps.io/**

(Bookmark this — you'll use it daily.)

### Sign in

You have two paths:

#### Path A — Use the shared QA account

| | |
|---|---|
| **Email** | `qa@aiplatformautotester.com` |
| **Password** | `AiPlatform2026` |

Use this for quick testing. Note that everyone using this account shares the same runs / test files / presets — fine for a small team but won't isolate your work.

#### Path B — Create your own account (recommended for your own data)

1. Open the URL → click **"Create one"** under the sign-in form
2. Enter your name, work email, and a password (≥ 8 characters)
3. Click **Create account** — you're in

Your runs, uploaded test files, and saved login presets are private to you. No other QA can see them.

---

## 2 · The two test types

| Test type | What it tests | Inputs needed |
|---|---|---|
| **🧠 SQL AI Engine** | A Celerant tenant's Skylar IQ chat box: types every NL question, captures the `generate-sql` → `run-sql` → `generate-viz` chain, validates response shape | Login URL of the tenant, username, password, .xlsx of questions |
| **🔎 Site Search** | An ssLibrary search widget: types each keyword, captures `search_keywords` and `search_results`, validates that products come back | Page URL **OR** uploaded ssLibrary bundle, JWT credentials, .xlsx of keywords |

---

## 3 · Excel format

Both test types use the same xlsx shape — column A is the test input.

### For SQL AI Engine
| Column A — natural-language question | Column B — expected SQL *(optional)* |
|---|---|
| What are my top 10 selling brands this year? | *(leave blank)* |
| Show inventory cost by department | *(leave blank)* |

### For Site Search
| Column A — search keyword | Column B |
|---|---|
| shirt | *(ignored)* |
| boots | *(ignored)* |

**Rules:**
- First row may be a header (`question`, `keyword`, `query`, etc.) — auto-skipped
- Empty rows are skipped
- Anything past column B is ignored

A 12-question sample lives at `~/Downloads/que_test-1.xlsx` — ask Farhan for it.

---

## 4 · Running a SQL AI Engine test

1. Click **+ New Run** in the top right
2. **Test type**: ◉ **🧠 SQL AI Engine**
3. Fill in:

   | Field | Value |
   |---|---|
   | **Login URL** | The full Celerant login URL of the tenant — e.g. `https://209.208.39.72:8443/backoffice/?mid=100` |
   | **Username** | The Celerant username for that tenant |
   | **Password** | The Celerant password |
   | **Machine ID** | `100` (default) — change if your tenant uses something else |
   | **SQL Agent path** | `/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent` (default — leave alone unless tenant deploys at a non-standard route) |

4. **Questions**: ◉ **Upload new file** → pick your `.xlsx`
   - **OR** ◉ **Use saved test file** if you've uploaded one before to the **Test Files** page
5. Click **▶ Start QA Run**

You'll be taken to the run page. Watch the live progress:
- **PASS / PARTIAL / FAIL / TIMEOUT** counters update as queries run
- **Last 5 queries** table shows the most recent results — click any row to drill down
- **Event log** tab streams every event line from the runner
- **All queries** tab shows every query in a searchable, filterable table

A typical 12-question run takes 2–5 minutes.

---

## 5 · Running a Site Search test

1. **+ New Run** → ◉ **🔎 Site Search**
2. **Where is your search page?**
   - ◉ **Live URL** — paste the URL of the page hosting the search widget (anyone publicly accessible)
   - ◉ **Use uploaded bundle** — pick from your saved bundles (upload one first on **Test Pages** if you don't have one yet)

3. **Search input selector**: `#searchbox` (default — only change if the page uses a different selector)

4. **Tenant override** *(recommended)* — substitute the tenant config that the page hardcodes:

   | Field | Example for the demo |
   |---|---|
   | **Org ID** | `r222ipid` |
   | **Console URL** | `https://celerantai.com/` |
   | **JWT username** | `r222ipid` *(blank → uses Org ID)* |
   | **JWT password** | `W0rkH0us3!` |

   Leave these blank to use whatever the page itself passes to `ssLibrary.init(...)`. Filling them lets you point the same page at any tenant.

5. **Search keywords**: upload your .xlsx
6. **Start QA Run**

A 20-keyword run typically takes 2–3 minutes.

### When to upload a bundle

Use **Test Pages** → **+ Upload bundle** if:
- You have only the `dist/` folder of an ssLibrary build (`.bundle.js` + `.css`) but **no public URL** to host it
- Zip the folder: `zip -r my-bundle.zip dist/ -x "__MACOSX*" "*.DS_Store" "._*"` (the `-x` flags strip macOS metadata)
- Upload the zip → the tool generates a private hosted page at `/hosted/<id>/index.html` and runs against that

---

## 6 · Reading a run report

When the run finishes, three primary outputs:

### A · The HTML report

Click **Open report ↗** at the top of the run page. You'll see:

- **Executive summary** — total / PASS / PARTIAL / FAIL / TIMEOUT counts, avg + max duration
- **API health** table — captured / HTTP-2xx / usable-payload counts per endpoint
- **Failing queries** + **Partial / warnings** sections with reasons
- **Per-query detail** — collapsible blocks for every query showing:
  - Status, duration, timestamps
  - Captured **request**: method, URL, headers (sanitized), body
  - Captured **response**: status, headers, body
  - Inline screenshots (input state + result state)
  - Runner notes (every selector tried, every fallback)
  - All XHR/fetch calls table

### B · Download the run as a zip

**↓ Download report (zip)** — packages REPORT.html + screenshots + raw per-query JSONs into one file you can email or attach to a JIRA ticket.

### C · Download just the failed queries

**↓ Download failed queries (xlsx)** — a re-runnable Excel of only the FAIL/PARTIAL/TIMEOUT queries, same column shape as the input. Hand it to a dev to fix the underlying bug, then re-run that same xlsx after their patch lands.

### D · CSV export

**Export CSV** — a flat results table for spreadsheet pivots. One row per query.

---

## 7 · Status meanings

| Badge | What it means |
|---|---|
| 🟢 **PASS** | All assertions green — captured both API calls, both 2xx, response payload had usable data |
| 🟡 **PARTIAL** | At least one warning — e.g. zero rows returned, or columns mismatch between run-sql and generate-viz |
| 🔴 **FAIL** | A hard failure — required call missing or HTTP non-2xx |
| 🟣 **TIMEOUT** | A request didn't return within 120 seconds |

---

## 8 · Stopping a run

If you started a run and want to abort:

1. On the run page, click the red **⏹ Stop run** button
2. Confirm — the runner finishes the current query, then stops cleanly
3. The report is still generated for queries that already completed

---

## 9 · Per-user data isolation

| Object | Visibility |
|---|---|
| Runs | Private — only you see your own |
| Test files (saved xlsx) | Private |
| Login presets | Private |
| Hosted bundles | Private |

Bob can't view, list, or even guess the URLs to Alice's runs/files even with the run ID. Each user has a fully separate workspace.

---

## 10 · Common issues / FAQ

### "Login failed at … : Machine ID is empty"
Wrong **Machine ID** for the tenant. Try `100` first, or get the right value from the Celerant admin for that client.

### Lots of TIMEOUTs
The Celerant LLM endpoint (`celerantai.com`) can be slow for some questions. Bump **run-sql timeout** to 300000–600000 (5–10 min) under **Advanced timeouts** on the New Run page.

### Site Search popup not showing in screenshots
The page must be HTTPS or localhost — `crypto.subtle` only works in secure contexts. If you're using a tunnel (cloudflared/ngrok), the auto-issued HTTPS URL works. If pointing at a plain HTTP URL, the tool falls back to a polyfill but some real-world pages need the genuine API.

### "file:// URLs cannot be reached from inside Docker"
You can't point the tool at a `file:///Users/...` path on your laptop — the QA runner runs on Azure, with no access to your local files. Either:
- Deploy the page to a public URL (or a tunnel), then paste that URL
- **OR** upload the `dist/` zip via **Test Pages** so the tool serves it for you

### "Search keywords / search_results call missing"
The bundle's `ssLibrary.init(...)` failed to authenticate. Most often: wrong **JWT credentials** in the Tenant Override section. Try the demo's `r222ipid` / `W0rkH0us3!` first to verify the flow works, then plug in your tenant's real creds.

### My run is stuck "running" but nothing is happening
If you redeployed the tool while a run was in progress, the runner thread can die. Click **⏹ Stop run** on that run to mark it failed. Start a new one.

---

## 11 · Sharing results

Three good patterns:

1. **Just the URL** — `https://ai-platform-auto-tester.thankfulmushroom-67b2c86a.centralus.azurecontainerapps.io/jobs/<run-id>` — anyone signed in can view
2. **Download the zip** + email — recipient extracts and opens REPORT.html offline
3. **Download failed queries** xlsx + tag the dev → they fix the bug → re-run the same xlsx

---

## 12 · Quick reference card

```
URL              https://ai-platform-auto-tester.thankfulmushroom-67b2c86a.centralus.azurecontainerapps.io/
Shared QA login  qa@aiplatformautotester.com / AiPlatform2026
Sign up          /signup    (private workspace)
New run          + New Run    (top right)
Test types       🧠 SQL AI Engine    🔎 Site Search
Excel column A   the test input (question or keyword)
Stop a run       red ⏹ Stop run button on the run page
Open report      blue Open report ↗ button on the run page
Download zip     ↓ Download report (zip)
Just failures    ↓ Download failed queries (xlsx)
```

---

## 13 · Need help?

Contact Farhan or post in the QA channel. Common questions are answered above; if your issue isn't, paste:

1. The run ID (top of the run page)
2. A screenshot of the failing query's detail page
3. What you expected vs. what happened

— and we'll diagnose it.
