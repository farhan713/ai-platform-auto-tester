"""Build a print-ready PDF of the tester guide using headless Chromium."""
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/Users/farhanmemon/Desktop/automationtesting/.claude/worktrees/elegant-lewin-d7fca8/docs/Skylar-IQ-QA-Tool-Tester-Guide.pdf")
OUT_DESKTOP = Path("/Users/farhanmemon/Desktop/Skylar-IQ-QA-Tool-Tester-Guide.pdf")
URL = "https://ai-platform-auto-tester.thankfulmushroom-67b2c86a.centralus.azurecontainerapps.io/"
DATE = date.today().strftime("%B %Y")

CSS = """
:root {
  --brand: #1a3a6e;
  --brand-2: #2e5aa8;
  --accent: #2563eb;
  --pass: #1a8a3a;
  --partial: #d49a00;
  --fail: #c62828;
  --timeout: #6a4ec2;
  --text: #1f2937;
  --muted: #6b7280;
  --soft: #9ca3af;
  --border: #e5e7eb;
  --code-bg: #f3f4f6;
  --surface: #f8fafc;
  --callout: #fff7e6;
  --callout-border: #d49a00;
}
* { box-sizing: border-box; }
@page { size: A4; margin: 18mm 18mm 22mm 18mm; }
@page :first { margin: 0; }
html { font-size: 11pt; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: var(--text); line-height: 1.55; margin: 0;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

/* ===================== Cover Page ===================== */
.cover {
  page-break-after: always;
  width: 210mm; height: 297mm;
  background-color: #1a3a6e;          /* solid fallback */
  background-image:
    radial-gradient(circle at 110% -10%, rgba(255,255,255,0.10) 0, rgba(255,255,255,0) 38%),
    radial-gradient(circle at -20% 110%, rgba(255,255,255,0.08) 0, rgba(255,255,255,0) 36%),
    linear-gradient(135deg, #142d5a 0%, #1a3a6e 50%, #2e5aa8 100%);
  color: #ffffff;
  position: relative;
  display: flex;
  flex-direction: column;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.cover-top {
  padding: 30mm 20mm 0;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
}
.cover-dot {
  width: 16px; height: 16px;
  border-radius: 50%;
  background-color: #22c55e;
  display: inline-block;
}
.cover-brand-name {
  font-size: 14pt;
  font-weight: 600;
  letter-spacing: 1.5px;
  color: #ffffff;
}
.cover-center { flex: 1; padding: 0 20mm; display: flex; flex-direction: column; justify-content: center; }
.cover-eyebrow {
  font-size: 11pt;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.78);
  margin-bottom: 10mm;
  font-weight: 500;
}
.cover-title {
  font-size: 48pt;
  font-weight: 800;
  line-height: 1.05;
  margin: 0;
  letter-spacing: -1px;
  color: #ffffff;
}
.cover-subtitle {
  font-size: 22pt;
  font-weight: 300;
  margin-top: 8mm;
  color: rgba(255, 255, 255, 0.92);
}
.cover-divider {
  width: 60mm;
  height: 4px;
  background-color: rgba(255, 255, 255, 0.45);
  margin: 14mm 0;
  border-radius: 2px;
}
.cover-meta {
  font-size: 11pt;
  color: rgba(255, 255, 255, 0.88);
  line-height: 1.85;
}
.cover-meta b {
  font-weight: 700;
  color: #ffffff;
  display: inline-block;
  width: 22mm;
}
.cover-bottom {
  padding: 0 20mm 22mm;
  font-size: 9pt;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 0.5px;
}

/* ===================== Body content ===================== */
h1 {
  color: var(--brand);
  font-size: 22pt;
  margin: 0 0 4mm;
  font-weight: 700;
  border-bottom: 2px solid var(--brand);
  padding-bottom: 3mm;
  page-break-after: avoid;
}
h2 { color: var(--brand); font-size: 14pt; margin: 8mm 0 3mm; font-weight: 600; page-break-after: avoid; }
h3 { color: var(--brand-2); font-size: 12pt; margin: 6mm 0 2mm; font-weight: 600; page-break-after: avoid; }
p { margin: 0 0 3mm; }
ul, ol { margin: 0 0 4mm; padding-left: 6mm; }
li { margin-bottom: 1.5mm; }
a { color: var(--accent); text-decoration: none; }

code {
  background: var(--code-bg);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.92em;
  color: #b91c1c;
}
pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 4mm;
  border-radius: 4px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 9pt;
  page-break-inside: avoid;
  line-height: 1.4;
  margin: 3mm 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 3mm 0 5mm;
  page-break-inside: avoid;
  font-size: 10pt;
}
th, td { border: 1px solid var(--border); padding: 2.5mm 3.5mm; text-align: left; vertical-align: top; }
th {
  background: var(--surface);
  font-weight: 600;
  color: var(--brand);
  font-size: 9.5pt;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
tr:nth-child(2n) td {
  background: rgba(248, 250, 252, 0.6);
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.callout {
  background: var(--callout);
  border-left: 4px solid var(--callout-border);
  padding: 3mm 4mm;
  border-radius: 3px;
  margin: 4mm 0;
  page-break-inside: avoid;
  font-size: 10.5pt;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.callout.info { background: #eff6ff; border-left-color: var(--accent); }
.callout strong { color: var(--brand); }

.badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 9pt;
  font-weight: 600;
  color: #fff;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.badge.PASS { background-color: #1a8a3a; }
.badge.PARTIAL { background-color: #d49a00; }
.badge.FAIL { background-color: #c62828; }
.badge.TIMEOUT { background-color: #6a4ec2; }

.url-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 3mm 4mm;
  font-family: ui-monospace, monospace;
  font-size: 9.5pt;
  word-break: break-all;
  margin: 3mm 0 4mm;
  color: var(--accent);
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.creds-box {
  border: 1px solid var(--border);
  border-radius: 4px;
  margin: 3mm 0 4mm;
  overflow: hidden;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.creds-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  border-bottom: 1px solid var(--border);
}
.creds-row:last-child { border-bottom: 0; }
.creds-label {
  background: var(--surface);
  padding: 2.5mm 3mm;
  color: var(--muted);
  font-weight: 500;
  font-size: 10pt;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.creds-value {
  padding: 2.5mm 3mm;
  font-family: ui-monospace, monospace;
  font-size: 10pt;
}

.toc { list-style: none; padding: 0; margin: 5mm 0; }
.toc li {
  display: grid;
  grid-template-columns: 12mm 1fr auto;
  align-items: baseline;
  padding: 2mm 0;
  border-bottom: 1px dotted var(--border);
}
.toc li:last-child { border-bottom: 0; }
.toc-num { color: var(--soft); font-weight: 500; }
.toc-title { font-weight: 500; color: var(--text); }
.toc-page-num { color: var(--muted); font-size: 9.5pt; }

.section { page-break-inside: avoid; }
.page-break { page-break-after: always; }

footer.legal {
  margin-top: 12mm;
  padding-top: 4mm;
  border-top: 1px solid var(--border);
  font-size: 9pt;
  color: var(--muted);
  text-align: center;
}
"""

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Skylar IQ QA Tool — Tester Guide</title>
<style>{CSS}</style>
</head>
<body>

<!-- COVER -->
<section class="cover">
  <div class="cover-top">
    <span class="cover-dot"></span>
    <span class="cover-brand-name">SKYLAR&nbsp;IQ&nbsp;QA</span>
  </div>
  <div class="cover-center">
    <div class="cover-eyebrow">QA AUTOMATION · TESTER GUIDE</div>
    <h1 class="cover-title">Skylar IQ<br>QA Tool</h1>
    <div class="cover-subtitle">A practical guide for testers</div>
    <div class="cover-divider"></div>
    <div class="cover-meta">
      <b>Version</b>3.6<br>
      <b>Updated</b>{DATE}<br>
      <b>Audience</b>QA testers running automated tests against<br>
      <span style="display:inline-block; width:22mm">&nbsp;</span>the Celerant SQL AI Engine and Site Search
    </div>
  </div>
  <div class="cover-bottom">INTERNAL QA DOCUMENTATION</div>
</section>

<!-- TOC -->
<section>
  <h1>Contents</h1>
  <ol class="toc">
    <li><span class="toc-num">1.</span><span class="toc-title">Get access</span><span class="toc-page-num">3</span></li>
    <li><span class="toc-num">2.</span><span class="toc-title">The two test types</span><span class="toc-page-num">4</span></li>
    <li><span class="toc-num">3.</span><span class="toc-title">Excel format</span><span class="toc-page-num">5</span></li>
    <li><span class="toc-num">4.</span><span class="toc-title">Running a SQL AI Engine test</span><span class="toc-page-num">6</span></li>
    <li><span class="toc-num">5.</span><span class="toc-title">Running a Site Search test</span><span class="toc-page-num">7</span></li>
    <li><span class="toc-num">6.</span><span class="toc-title">Reading a run report</span><span class="toc-page-num">9</span></li>
    <li><span class="toc-num">7.</span><span class="toc-title">Status meanings</span><span class="toc-page-num">10</span></li>
    <li><span class="toc-num">8.</span><span class="toc-title">Stopping a run</span><span class="toc-page-num">10</span></li>
    <li><span class="toc-num">9.</span><span class="toc-title">Per-user data isolation</span><span class="toc-page-num">11</span></li>
    <li><span class="toc-num">10.</span><span class="toc-title">Common issues / FAQ</span><span class="toc-page-num">11</span></li>
    <li><span class="toc-num">11.</span><span class="toc-title">Sharing results</span><span class="toc-page-num">13</span></li>
    <li><span class="toc-num">12.</span><span class="toc-title">Quick reference card</span><span class="toc-page-num">13</span></li>
    <li><span class="toc-num">13.</span><span class="toc-title">Need help</span><span class="toc-page-num">14</span></li>
  </ol>
  <div class="callout info" style="margin-top: 12mm">
    <strong>What this tool does.</strong> A web app that drives the Celerant <b>SQL AI Engine</b> and <b>Site Search</b> through real browser automation, captures every API call, and produces detailed HTML reports. You upload a list of test inputs; the tool runs them; you read the report.
  </div>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>1 · Get access</h1>
  <h2>The live URL</h2>
  <div class="url-box">{URL}</div>
  <p>Bookmark this — you'll use it daily.</p>
  <h2>Sign in</h2>
  <p>You have two paths.</p>
  <h3>Path A — Use the shared QA account</h3>
  <div class="creds-box">
    <div class="creds-row"><div class="creds-label">Email</div><div class="creds-value">qa@aiplatformautotester.com</div></div>
    <div class="creds-row"><div class="creds-label">Password</div><div class="creds-value">AiPlatform2026</div></div>
  </div>
  <p>Use this for quick testing. Note: everyone using this account shares the same runs, test files, and presets — fine for a small team but won't isolate your work.</p>
  <h3>Path B — Create your own account (recommended)</h3>
  <ol>
    <li>Open the URL → click <b>Create one</b> under the sign-in form.</li>
    <li>Enter your name, work email, and a password (≥ 8 characters).</li>
    <li>Click <b>Create account</b> — you're in.</li>
  </ol>
  <p>Your runs, uploaded test files, and saved login presets are private to you. No other tester can see them.</p>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>2 · The two test types</h1>
  <table>
    <thead><tr><th style="width:30%">Test type</th><th>What it tests</th><th>Inputs needed</th></tr></thead>
    <tbody>
      <tr><td><b>🧠 SQL AI Engine</b></td><td>A Celerant tenant's Skylar IQ chat box: types every NL question, captures the <code>generate-sql</code> → <code>run-sql</code> → <code>generate-viz</code> chain, validates response shape</td><td>Login URL of the tenant, username, password, .xlsx of questions</td></tr>
      <tr><td><b>🔎 Site Search</b></td><td>An ssLibrary search widget: types each keyword, captures <code>search_keywords</code> and <code>search_results</code>, validates that products come back</td><td>Page URL <em>or</em> uploaded ssLibrary bundle, JWT credentials, .xlsx of keywords</td></tr>
    </tbody>
  </table>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>3 · Excel format</h1>
  <p>Both test types use the same xlsx shape — column A is the test input.</p>
  <h3>For SQL AI Engine</h3>
  <table>
    <thead><tr><th>Column A — natural-language question</th><th>Column B — expected SQL <em>(optional)</em></th></tr></thead>
    <tbody>
      <tr><td>What are my top 10 selling brands this year?</td><td><em>(leave blank)</em></td></tr>
      <tr><td>Show inventory cost by department</td><td><em>(leave blank)</em></td></tr>
    </tbody>
  </table>
  <h3>For Site Search</h3>
  <table>
    <thead><tr><th>Column A — search keyword</th><th>Column B</th></tr></thead>
    <tbody>
      <tr><td>shirt</td><td><em>(ignored)</em></td></tr>
      <tr><td>boots</td><td><em>(ignored)</em></td></tr>
      <tr><td>knife</td><td><em>(ignored)</em></td></tr>
    </tbody>
  </table>
  <h3>Rules</h3>
  <ul>
    <li>The first row may be a header (<code>question</code>, <code>keyword</code>, <code>query</code>, etc.) — auto-skipped.</li>
    <li>Empty rows are skipped.</li>
    <li>Anything past column B is ignored.</li>
  </ul>
  <div class="callout"><strong>Tip.</strong> A 12-question sample lives at <code>~/Downloads/que_test-1.xlsx</code> — ask Farhan for it if you don't have it yet.</div>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>4 · Running a SQL AI Engine test</h1>
  <ol>
    <li>Click <b>+ New Run</b> in the top right.</li>
    <li><b>Test type:</b> <b>🧠 SQL AI Engine</b></li>
    <li>Fill in:
      <table style="margin-top:2mm">
        <tbody>
          <tr><th>Login URL</th><td>The full Celerant login URL of the tenant — e.g. <code>https://209.208.39.72:8443/backoffice/?mid=100</code></td></tr>
          <tr><th>Username</th><td>The Celerant username for that tenant</td></tr>
          <tr><th>Password</th><td>The Celerant password</td></tr>
          <tr><th>Machine ID</th><td><code>100</code> by default — change if your tenant uses something else</td></tr>
          <tr><th>SQL Agent path</th><td><code>/backoffice/mv-assets/index-modern.html#/listScreen/sqlagent</code> (default — leave alone unless tenant deploys at a non-standard route)</td></tr>
        </tbody>
      </table>
    </li>
    <li><b>Questions:</b> <b>Upload new file</b> → pick your <code>.xlsx</code> &mdash; <em>or</em> <b>Use saved test file</b> if you've uploaded one before to the <b>Test Files</b> page.</li>
    <li>Click <b>▶ Start QA Run</b>.</li>
  </ol>
  <p>You'll be taken to the run page. Watch the live progress:</p>
  <ul>
    <li><b>PASS / PARTIAL / FAIL / TIMEOUT</b> counters update as queries run.</li>
    <li><b>Last 5 queries</b> table shows the most recent results — click any row to drill down.</li>
    <li><b>Event log</b> tab streams every event line from the runner.</li>
    <li><b>All queries</b> tab shows every query in a searchable, filterable table.</li>
  </ul>
  <p>A typical 12-question run takes 2–5 minutes.</p>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>5 · Running a Site Search test</h1>
  <ol>
    <li><b>+ New Run</b> → <b>🔎 Site Search</b></li>
    <li><b>Where is your search page?</b>
      <ul>
        <li><b>Live URL</b> — paste the URL of the page hosting the search widget (anywhere publicly reachable).</li>
        <li><b>Use uploaded bundle</b> — pick from your saved bundles (upload one first on <b>Test Pages</b> if you don't have one yet).</li>
      </ul>
    </li>
    <li><b>Search input selector:</b> <code>#searchbox</code> by default — only change if the page uses a different selector.</li>
    <li><b>Tenant override</b> <em>(recommended)</em> — substitute the tenant config that the page hardcodes:
      <table style="margin-top:2mm">
        <thead><tr><th>Field</th><th>Example for the demo</th></tr></thead>
        <tbody>
          <tr><td>Org ID</td><td><code>r222ipid</code></td></tr>
          <tr><td>Console URL</td><td><code>https://celerantai.com/</code></td></tr>
          <tr><td>JWT username</td><td><code>r222ipid</code> (blank → uses Org ID)</td></tr>
          <tr><td>JWT password</td><td><code>W0rkH0us3!</code></td></tr>
        </tbody>
      </table>
      <p style="margin-top:2mm">Leave these blank to use whatever the page itself passes to <code>ssLibrary.init(...)</code>. Filling them lets you point the same page at any tenant.</p>
    </li>
    <li><b>Search keywords:</b> upload your .xlsx.</li>
    <li><b>Start QA Run.</b></li>
  </ol>
  <p>A 20-keyword run typically takes 2–3 minutes.</p>
  <h2>When to upload a bundle</h2>
  <p>Use <b>Test Pages</b> → <b>+ Upload bundle</b> if:</p>
  <ul>
    <li>You have only the <code>dist/</code> folder of an ssLibrary build (<code>.bundle.js</code> + <code>.css</code>) but <em>no public URL</em> to host it.</li>
    <li>Zip the folder before uploading: <code>zip -r my-bundle.zip dist/ -x "__MACOSX*" "*.DS_Store" "._*"</code> — the <code>-x</code> flags strip macOS metadata.</li>
    <li>Upload the zip → the tool generates a private hosted page at <code>/hosted/&lt;id&gt;/index.html</code> and runs against that.</li>
  </ul>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>6 · Reading a run report</h1>
  <p>When the run finishes, four primary outputs are available from the run page.</p>
  <h2>A &middot; The HTML report</h2>
  <p>Click <b>Open report ↗</b>. You'll see:</p>
  <ul>
    <li><b>Executive summary</b> — total / PASS / PARTIAL / FAIL / TIMEOUT counts, avg + max duration.</li>
    <li><b>API health</b> table — captured / HTTP-2xx / usable-payload counts per endpoint.</li>
    <li><b>Failing queries</b> + <b>Partial / warnings</b> sections with reasons.</li>
    <li><b>Per-query detail</b> — collapsible blocks for every query showing:
      <ul>
        <li>Status, duration, timestamps</li>
        <li>Captured <b>request</b>: method, URL, headers (sanitized), body</li>
        <li>Captured <b>response</b>: status, headers, body</li>
        <li>Inline screenshots (input state + result state)</li>
        <li>Runner notes — every selector tried, every fallback</li>
        <li>All XHR/fetch calls table</li>
      </ul>
    </li>
  </ul>
  <h2>B &middot; Download the run as a zip</h2>
  <p><b>↓ Download report (zip)</b> — packages REPORT.html + screenshots + raw per-query JSONs into one file you can email or attach to a JIRA ticket.</p>
  <h2>C &middot; Download just the failed queries</h2>
  <p><b>↓ Download failed queries (xlsx)</b> — a re-runnable Excel of only the FAIL/PARTIAL/TIMEOUT queries, same column shape as the input. Hand it to a developer to fix the underlying bug, then re-run that same xlsx after their patch lands.</p>
  <h2>D &middot; CSV export</h2>
  <p><b>Export CSV</b> — a flat results table for spreadsheet pivots. One row per query.</p>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>7 · Status meanings</h1>
  <table>
    <thead><tr><th style="width:20%">Badge</th><th>What it means</th></tr></thead>
    <tbody>
      <tr><td><span class="badge PASS">PASS</span></td><td>All assertions green — captured both API calls, both 2xx, response payload had usable data.</td></tr>
      <tr><td><span class="badge PARTIAL">PARTIAL</span></td><td>At least one warning — e.g. zero rows returned, or columns mismatch between run-sql and generate-viz.</td></tr>
      <tr><td><span class="badge FAIL">FAIL</span></td><td>A hard failure — required call missing or HTTP non-2xx.</td></tr>
      <tr><td><span class="badge TIMEOUT">TIMEOUT</span></td><td>A request didn't return within 120 seconds.</td></tr>
    </tbody>
  </table>
</section>

<section class="section">
  <h1>8 · Stopping a run</h1>
  <p>If you started a run and want to abort:</p>
  <ol>
    <li>On the run page, click the red <b>⏹ Stop run</b> button.</li>
    <li>Confirm — the runner finishes the current query, then stops cleanly.</li>
    <li>The report is still generated for queries that already completed.</li>
  </ol>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>9 · Per-user data isolation</h1>
  <table>
    <thead><tr><th>Object</th><th>Visibility</th></tr></thead>
    <tbody>
      <tr><td>Runs</td><td>Private — only you see your own.</td></tr>
      <tr><td>Test files (saved xlsx)</td><td>Private.</td></tr>
      <tr><td>Login presets</td><td>Private.</td></tr>
      <tr><td>Hosted bundles</td><td>Private.</td></tr>
    </tbody>
  </table>
  <p>Bob can't view, list, or even guess the URLs to Alice's runs/files even with the run ID. Each user has a fully separate workspace.</p>
</section>

<section class="section">
  <h1>10 · Common issues / FAQ</h1>
  <h3>"Login failed at … : Machine ID is empty"</h3>
  <p>Wrong <b>Machine ID</b> for the tenant. Try <code>100</code> first, or get the right value from the Celerant admin for that client.</p>
  <h3>Lots of TIMEOUTs</h3>
  <p>The Celerant LLM endpoint (<code>celerantai.com</code>) can be slow for some questions. Bump <b>run-sql timeout</b> to <code>300000</code>–<code>600000</code> (5–10 min) under <b>Advanced timeouts</b> on the New Run page.</p>
  <h3>Site Search popup not showing in screenshots</h3>
  <p>The page must be HTTPS or localhost — <code>crypto.subtle</code> only works in secure contexts. If you're using a tunnel (cloudflared/ngrok), the auto-issued HTTPS URL works. If pointing at a plain HTTP URL, the tool falls back to a polyfill but some real-world pages need the genuine API.</p>
  <h3>"file:// URLs cannot be reached from inside Docker"</h3>
  <p>You can't point the tool at a <code>file:///Users/...</code> path on your laptop — the QA runner runs on Azure, with no access to your local files. Either:</p>
  <ul>
    <li>Deploy the page to a public URL (or a tunnel), then paste that URL.</li>
    <li><em>Or</em> upload the <code>dist/</code> zip via <b>Test Pages</b> so the tool serves it for you.</li>
  </ul>
  <h3>"Search keywords / search_results call missing"</h3>
  <p>The bundle's <code>ssLibrary.init(...)</code> failed to authenticate. Most often: wrong <b>JWT credentials</b> in the Tenant Override section. Try the demo's <code>r222ipid</code> / <code>W0rkH0us3!</code> first to verify the flow works, then plug in your tenant's real creds.</p>
  <h3>My run is stuck "running" but nothing is happening</h3>
  <p>If the tool was redeployed while a run was in progress, the runner thread can die. Click <b>⏹ Stop run</b> on that run to mark it failed. Start a new one.</p>
</section>

<div class="page-break"></div>

<section class="section">
  <h1>11 · Sharing results</h1>
  <p>Three good patterns:</p>
  <ol>
    <li><b>Just the URL</b> — paste the full <code>/jobs/&lt;run-id&gt;</code> URL. Anyone signed in can view it.</li>
    <li><b>Download the zip</b> + email — recipient extracts and opens REPORT.html offline.</li>
    <li><b>Download failed queries (xlsx)</b> + tag the developer → they fix the bug → re-run the same xlsx after patch lands.</li>
  </ol>
</section>

<section class="section">
  <h1>12 · Quick reference card</h1>
  <table>
    <tbody>
      <tr><th style="width:35%">URL</th><td><code>{URL}</code></td></tr>
      <tr><th>Shared QA login</th><td><code>qa@aiplatformautotester.com</code> / <code>AiPlatform2026</code></td></tr>
      <tr><th>Sign up</th><td><code>/signup</code> &nbsp; (private workspace)</td></tr>
      <tr><th>New run</th><td>+ New Run &nbsp; <em>(top right)</em></td></tr>
      <tr><th>Test types</th><td>🧠 SQL AI Engine &nbsp;&nbsp; 🔎 Site Search</td></tr>
      <tr><th>Excel column A</th><td>The test input (question or keyword)</td></tr>
      <tr><th>Stop a run</th><td>red ⏹ <b>Stop run</b> button on the run page</td></tr>
      <tr><th>Open report</th><td>blue <b>Open report ↗</b> button on the run page</td></tr>
      <tr><th>Download zip</th><td>↓ Download report (zip)</td></tr>
      <tr><th>Just failures</th><td>↓ Download failed queries (xlsx)</td></tr>
    </tbody>
  </table>
</section>

<section class="section">
  <h1>13 · Need help?</h1>
  <p>Contact Farhan or post in the QA channel. Common questions are answered in section 10. If your issue isn't, paste these three things:</p>
  <ol>
    <li>The run ID (top of the run page).</li>
    <li>A screenshot of the failing query's detail page.</li>
    <li>What you expected vs. what happened.</li>
  </ol>
  <p>— and we'll diagnose it.</p>
  <footer class="legal">
    Skylar IQ QA Tool — Internal QA documentation · Version 3.6 · {DATE}<br>
    Not for external distribution without permission.
  </footer>
</section>

</body>
</html>"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content(HTML, wait_until="networkidle")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    page.pdf(
        path=str(OUT),
        format="A4",
        print_background=True,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        display_header_footer=True,
        header_template="<div></div>",
        footer_template="""<div style="font-size:8pt; color:#9ca3af; width:100%;
            font-family: -apple-system, sans-serif;
            padding: 0 18mm; display: flex; justify-content: space-between;
            margin-top: 6mm;">
            <span>Skylar IQ QA Tool — Tester Guide · v3.6</span>
            <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
        </div>""",
    )
    browser.close()

import shutil
shutil.copy(OUT, OUT_DESKTOP)
print(f"  Built: {OUT}")
print(f"  Desktop: {OUT_DESKTOP}")
