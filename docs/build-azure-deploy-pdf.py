"""Build the professional Azure Deployment Guide PDF."""
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/Users/farhanmemon/Desktop/automationtesting/.claude/worktrees/elegant-lewin-d7fca8/docs/Skylar-IQ-QA-Tool-Azure-Deployment-Guide.pdf")
OUT_DESKTOP = Path("/Users/farhanmemon/Desktop/Skylar-IQ-QA-Tool-Azure-Deployment-Guide.pdf")
DATE = date.today().strftime("%B %Y")

CSS = r"""
:root{
  --brand:#1a3a6e; --brand-2:#2e5aa8; --accent:#2563eb;
  --pass:#1a8a3a; --partial:#d49a00; --fail:#c62828;
  --text:#1f2937; --muted:#6b7280; --soft:#9ca3af;
  --border:#e5e7eb; --code-bg:#f3f4f6; --surface:#f8fafc;
  --callout:#fff7e6; --callout-border:#d49a00;
  --info-bg:#eff6ff; --info-border:#2563eb;
  --danger-bg:#fef2f2; --danger-border:#c62828;
  --success-bg:#effaf0; --success-border:#1a8a3a;
}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
@page{size:A4; margin:18mm 18mm 22mm 18mm}
@page:first{margin:0}
html{font-size:10.5pt}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
  color:var(--text); line-height:1.55; margin:0;
}

/* ===== Cover ===== */
.cover{
  page-break-after:always;
  width:210mm; height:297mm;
  background-color:#1a3a6e;
  background-image:
    radial-gradient(circle at 110% -10%, rgba(255,255,255,0.10) 0, rgba(255,255,255,0) 38%),
    radial-gradient(circle at -20% 110%, rgba(255,255,255,0.08) 0, rgba(255,255,255,0) 36%),
    linear-gradient(135deg,#142d5a 0%,#1a3a6e 50%,#2e5aa8 100%);
  color:#fff; position:relative; display:flex; flex-direction:column;
}
.cover-top{padding:30mm 20mm 0; display:flex; align-items:center; gap:12px; color:#fff}
.cover-dot{width:16px; height:16px; border-radius:50%; background:#22c55e}
.cover-brand-name{font-size:14pt; font-weight:600; letter-spacing:1.5px; color:#fff}
.cover-center{flex:1; padding:0 20mm; display:flex; flex-direction:column; justify-content:center}
.cover-eyebrow{
  font-size:11pt; text-transform:uppercase; letter-spacing:3px;
  color:rgba(255,255,255,0.8); margin-bottom:10mm; font-weight:500;
}
.cover-title{
  font-size:42pt; font-weight:800; line-height:1.05; margin:0;
  letter-spacing:-0.5px; color:#fff;
}
.cover-subtitle{font-size:18pt; font-weight:300; margin-top:8mm; color:rgba(255,255,255,0.92)}
.cover-divider{width:60mm; height:4px; background:rgba(255,255,255,0.45); margin:14mm 0; border-radius:2px}
.cover-meta{font-size:11pt; color:rgba(255,255,255,0.88); line-height:1.85}
.cover-meta b{font-weight:700; color:#fff; display:inline-block; width:24mm}
.cover-bottom{padding:0 20mm 22mm; font-size:9pt; color:rgba(255,255,255,0.6); letter-spacing:0.5px}

/* ===== Body content ===== */
h1{
  color:var(--brand); font-size:20pt; margin:0 0 4mm;
  font-weight:700; border-bottom:2px solid var(--brand);
  padding-bottom:3mm; page-break-after:avoid;
}
h2{color:var(--brand); font-size:13pt; margin:8mm 0 3mm; font-weight:600; page-break-after:avoid}
h3{color:var(--brand-2); font-size:11.5pt; margin:6mm 0 2mm; font-weight:600; page-break-after:avoid}
h4{color:var(--text); font-size:10.5pt; margin:4mm 0 2mm; font-weight:600; page-break-after:avoid}
p{margin:0 0 3mm}
ul,ol{margin:0 0 4mm; padding-left:5mm}
li{margin-bottom:1.2mm}
a{color:var(--accent); text-decoration:none}

code{
  background:var(--code-bg); padding:1px 5px; border-radius:3px;
  font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  font-size:0.9em; color:#b91c1c; word-break:break-word;
}
pre{
  background:#0f172a; color:#e2e8f0; padding:4mm; border-radius:4px;
  font-family:ui-monospace,"SF Mono",Menlo,monospace;
  font-size:8.5pt; page-break-inside:avoid; line-height:1.45;
  margin:3mm 0; white-space:pre-wrap; word-break:break-word;
}
pre code{background:transparent; color:inherit; padding:0}

table{
  width:100%; border-collapse:collapse; margin:3mm 0 5mm;
  page-break-inside:avoid; font-size:9.5pt;
}
th,td{border:1px solid var(--border); padding:2.5mm 3mm; text-align:left; vertical-align:top}
th{
  background:var(--surface); font-weight:600; color:var(--brand);
  font-size:9pt; text-transform:uppercase; letter-spacing:0.4px;
}
tr:nth-child(2n) td{background:rgba(248,250,252,0.6)}

/* Step boxes */
.step{
  border:1px solid var(--border); border-radius:6px;
  background:#fff; padding:4mm 5mm; margin:3mm 0 5mm;
  page-break-inside:avoid; position:relative;
}
.step-head{
  display:flex; align-items:center; gap:3mm;
  margin:-4mm -5mm 3mm; padding:3mm 5mm;
  background:var(--brand); color:#fff; border-radius:6px 6px 0 0;
  font-weight:600; font-size:11pt;
}
.step-num{
  background:#fff; color:var(--brand); border-radius:50%;
  width:8mm; height:8mm; display:inline-flex; align-items:center; justify-content:center;
  font-weight:700; font-size:10pt; flex-shrink:0;
}
.step h3, .step h4{margin-top:2mm}
.step ol, .step ul{margin-bottom:0}

/* Callouts */
.callout{
  border-left:4px solid var(--callout-border); background:var(--callout);
  padding:3mm 4mm; border-radius:3px; margin:4mm 0; page-break-inside:avoid;
  font-size:10pt;
}
.callout.info{background:var(--info-bg); border-left-color:var(--info-border)}
.callout.success{background:var(--success-bg); border-left-color:var(--success-border)}
.callout.danger{background:var(--danger-bg); border-left-color:var(--danger-border)}
.callout strong{color:var(--brand); display:block; margin-bottom:1mm; font-size:10.5pt}
.callout.danger strong{color:var(--fail)}
.callout.success strong{color:var(--pass)}

/* TOC */
.toc{list-style:none; padding:0; margin:5mm 0}
.toc li{
  display:grid; grid-template-columns:14mm 1fr auto;
  align-items:baseline; padding:1.8mm 0;
  border-bottom:1px dotted var(--border);
}
.toc li:last-child{border-bottom:0}
.toc-num{color:var(--soft); font-weight:500}
.toc-title{font-weight:500; color:var(--text)}
.toc-page{color:var(--muted); font-size:9.5pt}

/* Architecture diagram */
.arch{
  border:1px solid var(--border); background:var(--surface);
  border-radius:6px; padding:6mm; margin:4mm 0 6mm;
  page-break-inside:avoid;
}
.arch-grid{display:grid; gap:3mm}
.arch-row{display:flex; gap:3mm; justify-content:center; flex-wrap:wrap}
.arch-box{
  background:#fff; border:1.5px solid var(--brand); border-radius:6px;
  padding:3mm 4mm; min-width:42mm; text-align:center;
  font-size:9.5pt; line-height:1.35; box-shadow:0 1px 2px rgba(0,0,0,0.04);
}
.arch-box .arch-name{font-weight:600; color:var(--brand); display:block; margin-bottom:1mm}
.arch-box .arch-sub{color:var(--muted); font-size:8.5pt}
.arch-box.user{border-color:var(--soft); background:#fafafa}
.arch-box.azure{background:#eef4fb}
.arch-arrow{
  display:flex; align-items:center; justify-content:center;
  color:var(--soft); font-weight:600; font-size:14pt;
}

/* URL / creds boxes */
.url-box{
  background:var(--surface); border:1px solid var(--border); border-radius:4px;
  padding:3mm 4mm; font-family:ui-monospace,monospace; font-size:9pt;
  word-break:break-all; margin:3mm 0 4mm; color:var(--accent);
}
.kv-box{
  border:1px solid var(--border); border-radius:4px; margin:3mm 0 4mm; overflow:hidden;
}
.kv-row{display:grid; grid-template-columns:34mm 1fr; border-bottom:1px solid var(--border)}
.kv-row:last-child{border-bottom:0}
.kv-label{
  background:var(--surface); padding:2.2mm 3mm; color:var(--muted);
  font-weight:500; font-size:9.5pt;
}
.kv-value{padding:2.2mm 3mm; font-family:ui-monospace,monospace; font-size:9.5pt}

/* Phase header */
.phase-banner{
  background:linear-gradient(90deg, var(--brand) 0%, var(--brand-2) 100%);
  color:#fff; padding:5mm 6mm; border-radius:6px;
  margin:0 0 5mm; page-break-after:avoid;
}
.phase-banner .phase-tag{
  font-size:9pt; text-transform:uppercase; letter-spacing:2px; opacity:0.7;
}
.phase-banner .phase-title{
  font-size:18pt; font-weight:700; margin-top:1mm; line-height:1.2;
}
.phase-banner .phase-meta{
  margin-top:3mm; font-size:9.5pt; opacity:0.85; display:flex; gap:8mm; flex-wrap:wrap;
}
.phase-banner .phase-meta span b{font-weight:600; opacity:0.7; margin-right:1mm}

/* Cost table specific */
.cost-table tr.total{background:var(--surface); font-weight:700}
.cost-table tr.total td{border-top:2px solid var(--brand); color:var(--brand)}

/* Pitfall card */
.pitfall{
  border:1px solid var(--fail); border-left:4px solid var(--fail);
  border-radius:4px; padding:3mm 4mm; margin:3mm 0 4mm;
  background:#fff; page-break-inside:avoid;
}
.pitfall-title{
  color:var(--fail); font-weight:700; font-size:10.5pt;
  margin:0 0 1.5mm; display:flex; align-items:baseline; gap:2mm;
}
.pitfall-title .pitfall-num{
  background:var(--fail); color:#fff; border-radius:50%;
  width:6mm; height:6mm; display:inline-flex; align-items:center; justify-content:center;
  font-size:9pt;
}
.pitfall-fix{margin-top:2mm; padding-top:2mm; border-top:1px dashed var(--border); font-size:9.5pt}
.pitfall-fix b{color:var(--pass)}

.section{page-break-inside:avoid}
.page-break{page-break-after:always}

/* Badges */
.badge{display:inline-block; padding:1px 7px; border-radius:10px; font-size:8.5pt; font-weight:600; color:#fff; vertical-align:1px}
.badge.PASS{background:#1a8a3a}
.badge.PARTIAL{background:#d49a00}
.badge.FAIL{background:#c62828}

footer.legal{
  margin-top:10mm; padding-top:3mm; border-top:1px solid var(--border);
  font-size:8.5pt; color:var(--muted); text-align:center;
}
"""

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Skylar IQ QA Tool — Azure Deployment Guide</title><style>{CSS}</style></head><body>

<!-- COVER -->
<section class="cover">
  <div class="cover-top">
    <span class="cover-dot"></span>
    <span class="cover-brand-name">SKYLAR&nbsp;IQ&nbsp;QA</span>
  </div>
  <div class="cover-center">
    <div class="cover-eyebrow">DEPLOYMENT GUIDE · AZURE</div>
    <h1 class="cover-title">Azure<br>Deployment</h1>
    <div class="cover-subtitle">End-to-end deployment of the Skylar IQ QA Tool to Microsoft Azure</div>
    <div class="cover-divider"></div>
    <div class="cover-meta">
      <b>Version</b>3.6<br>
      <b>Updated</b>{DATE}<br>
      <b>Audience</b>Internal team — anyone (no Azure experience required)<br>
      <b>Length</b>~25 pages, ~2-3 hours end-to-end first time
    </div>
  </div>
  <div class="cover-bottom">INTERNAL DEPLOYMENT DOCUMENTATION</div>
</section>

<!-- TOC -->
<section>
  <h1>Contents</h1>
  <ol class="toc">
    <li><span class="toc-num">1.</span><span class="toc-title">Overview &amp; what you'll build</span><span class="toc-page">3</span></li>
    <li><span class="toc-num">2.</span><span class="toc-title">Architecture at a glance</span><span class="toc-page">4</span></li>
    <li><span class="toc-num">3.</span><span class="toc-title">Pre-requisites</span><span class="toc-page">5</span></li>
    <li><span class="toc-num">4.</span><span class="toc-title">Phase 1 · Sign in to Azure</span><span class="toc-page">6</span></li>
    <li><span class="toc-num">5.</span><span class="toc-title">Phase 2 · Resource Group</span><span class="toc-page">7</span></li>
    <li><span class="toc-num">6.</span><span class="toc-title">Phase 3 · PostgreSQL Flexible Server</span><span class="toc-page">8</span></li>
    <li><span class="toc-num">7.</span><span class="toc-title">Phase 4 · Azure Container Registry</span><span class="toc-page">10</span></li>
    <li><span class="toc-num">8.</span><span class="toc-title">Phase 5 · Build &amp; push the image</span><span class="toc-page">11</span></li>
    <li><span class="toc-num">9.</span><span class="toc-title">Phase 6 · Storage &amp; File Shares</span><span class="toc-page">13</span></li>
    <li><span class="toc-num">10.</span><span class="toc-title">Phase 7 · Container Apps Environment</span><span class="toc-page">15</span></li>
    <li><span class="toc-num">11.</span><span class="toc-title">Phase 8 · Container App</span><span class="toc-page">16</span></li>
    <li><span class="toc-num">12.</span><span class="toc-title">Phase 9 · Mount file-share volumes</span><span class="toc-page">18</span></li>
    <li><span class="toc-num">13.</span><span class="toc-title">Phase 10 · First sign-in &amp; lockdown</span><span class="toc-page">19</span></li>
    <li><span class="toc-num">14.</span><span class="toc-title">Day-to-day operations</span><span class="toc-page">20</span></li>
    <li><span class="toc-num">15.</span><span class="toc-title">Cost breakdown</span><span class="toc-page">21</span></li>
    <li><span class="toc-num">16.</span><span class="toc-title">Common pitfalls (real ones)</span><span class="toc-page">22</span></li>
    <li><span class="toc-num">17.</span><span class="toc-title">Troubleshooting / FAQ</span><span class="toc-page">24</span></li>
    <li><span class="toc-num">18.</span><span class="toc-title">Quick reference card</span><span class="toc-page">25</span></li>
  </ol>
</section>

<div class="page-break"></div>

<!-- 1. OVERVIEW -->
<section class="section">
  <h1>1 · Overview &amp; what you'll build</h1>

  <p>This guide walks you through deploying the <b>Skylar IQ QA Tool</b> to Microsoft Azure. By the end you'll have:</p>

  <ul>
    <li>A live HTTPS URL where your QA team can sign in and run automated tests against the Celerant SQL AI Engine and Site Search</li>
    <li>A managed PostgreSQL database for users, runs, and per-query results</li>
    <li>Persistent file storage for uploaded test files, bundles, and generated reports — survives container restarts</li>
    <li>A private container registry that holds your built application image</li>
    <li>A repeatable, version-controlled deployment you can update with one command</li>
  </ul>

  <h2>What you don't need</h2>
  <ul>
    <li><b>Docker installed locally</b> — Azure builds the container image cloud-side from source</li>
    <li><b>Kubernetes knowledge</b> — Azure Container Apps abstracts that away</li>
    <li><b>Hand-written ARM/Bicep templates</b> — every step in this guide is portal click-through or one CLI command</li>
  </ul>

  <h2>Time &amp; cost</h2>
  <table>
    <thead><tr><th>Aspect</th><th>Estimate</th></tr></thead>
    <tbody>
      <tr><td>Total time, first deployment</td><td>2–3 hours (a lot of waiting on Azure provisioning)</td></tr>
      <tr><td>Total time, subsequent re-deployments</td><td>~5 minutes (just rebuild image + roll new revision)</td></tr>
      <tr><td>Approximate monthly cost (idle, ~50 runs/month)</td><td>~₹3,700 / ~$45 USD</td></tr>
      <tr><td>Free tier coverage (new Azure account)</td><td>$200 credit ≈ 4 months runway</td></tr>
    </tbody>
  </table>

  <div class="callout success">
    <strong>Real-world reference deployment.</strong>
    Production URL today: <code>https://ai-platform-auto-tester.thankfulmushroom-67b2c86a.centralus.azurecontainerapps.io/</code><br>
    Resource group: <code>ai-platform-auto-tester</code> · Region: <b>Central US</b>
  </div>
</section>

<div class="page-break"></div>

<!-- 2. ARCHITECTURE -->
<section class="section">
  <h1>2 · Architecture at a glance</h1>

  <p>Eight Azure resources working together. Read top-to-bottom: a tester's browser hits Azure, which routes to the Container App, which runs Playwright against the test target, and writes results to Postgres + File Shares.</p>

  <div class="arch">
    <div class="arch-grid">
      <div class="arch-row">
        <div class="arch-box user">
          <span class="arch-name">QA Tester</span>
          <span class="arch-sub">Web browser</span>
        </div>
      </div>
      <div class="arch-row"><span class="arch-arrow">↓</span></div>
      <div class="arch-row">
        <div class="arch-box azure">
          <span class="arch-name">Container App</span>
          <span class="arch-sub">Flask + Playwright<br>1 vCPU / 2 GiB</span>
        </div>
      </div>
      <div class="arch-row"><span class="arch-arrow">↓ ↓ ↓</span></div>
      <div class="arch-row">
        <div class="arch-box azure">
          <span class="arch-name">PostgreSQL</span>
          <span class="arch-sub">Flexible Server B1ms<br>users · runs · query_results</span>
        </div>
        <div class="arch-box azure">
          <span class="arch-name">File Shares</span>
          <span class="arch-sub">skylar-runs (reports)<br>skylar-data (bundles, xlsx)</span>
        </div>
        <div class="arch-box azure">
          <span class="arch-name">Container Registry</span>
          <span class="arch-sub">Holds skylar-qa:latest<br>image</span>
        </div>
      </div>
      <div class="arch-row"><span class="arch-arrow">↑ during runs ↑</span></div>
      <div class="arch-row">
        <div class="arch-box user">
          <span class="arch-name">Test target</span>
          <span class="arch-sub">Celerant tenant<br><i>or</i> Site-Search page</span>
        </div>
      </div>
    </div>
  </div>

  <h2>The 8 resources we'll create (in order)</h2>
  <table>
    <thead><tr><th style="width:8%">#</th><th>Resource</th><th>Why it exists</th></tr></thead>
    <tbody>
      <tr><td>1</td><td><b>Resource Group</b></td><td>A folder that holds everything else; deleting it tears down the whole stack</td></tr>
      <tr><td>2</td><td><b>PostgreSQL Flexible Server</b></td><td>Persistent database for users, runs, per-query results</td></tr>
      <tr><td>3</td><td><b>Azure Container Registry (ACR)</b></td><td>Stores the application Docker image</td></tr>
      <tr><td>4</td><td><b>The image itself</b></td><td>Built from source via <code>az acr build</code>; lives inside ACR</td></tr>
      <tr><td>5</td><td><b>Storage Account</b> + <b>two File Shares</b></td><td>Persistent disk for reports (<code>skylar-runs</code>) and uploaded test files / bundles (<code>skylar-data</code>)</td></tr>
      <tr><td>6</td><td><b>Container Apps Environment</b></td><td>The shared platform where one or more container apps run; binds the file shares</td></tr>
      <tr><td>7</td><td><b>Container App</b></td><td>The actual running app — pulls the image, mounts volumes, exposes HTTPS</td></tr>
      <tr><td>8</td><td><b>Volume mounts</b></td><td>The "wires" connecting Container App's <code>/app/runs</code> and <code>/app/data</code> to the file shares</td></tr>
    </tbody>
  </table>

  <p style="margin-top:5mm">All of these go into a single <b>Resource Group</b>. To tear everything down later, delete the resource group — one action, all resources gone.</p>
</section>

<div class="page-break"></div>

<!-- 3. PRE-REQUISITES -->
<section class="section">
  <h1>3 · Pre-requisites</h1>

  <h2>Things you need before starting</h2>
  <table>
    <thead><tr><th>Item</th><th>Why</th><th>How to get it</th></tr></thead>
    <tbody>
      <tr><td>An Azure subscription with credit / payment method</td><td>To pay for resources (or use Free Trial credit)</td><td>Sign up at <a href="https://azure.microsoft.com/free">azure.microsoft.com/free</a> — $200 free credit valid 30 days</td></tr>
      <tr><td>Azure CLI installed on your Mac</td><td>One step (image build) needs it; nice for verification too</td><td><code>brew install azure-cli</code></td></tr>
      <tr><td>The application source code</td><td>To build the image from</td><td><code>git clone https://github.com/farhan713/ai-platform-auto-tester.git</code></td></tr>
      <tr><td>~30 GB free disk space</td><td>Source + Docker daemon + Azure CLI cache</td><td>—</td></tr>
      <tr><td>Internet connection</td><td>You'll be uploading source to Azure</td><td>Wired/strong WiFi recommended (we hit upload timeouts on slow connections)</td></tr>
    </tbody>
  </table>

  <div class="callout danger">
    <strong>⚠ Common false start: account without a subscription.</strong>
    Just creating a Microsoft account does <b>not</b> activate an Azure subscription.
    You must go through the Free Trial sign-up flow which requires phone OTP <b>and a credit card</b>
    (the card is for identity verification only — won't be charged unless you upgrade).
    If you skip this step, every Azure CLI command will fail with
    <code>No subscriptions found for <i>your-email</i></code>.
  </div>
</section>

<div class="page-break"></div>

<!-- 4. PHASE 1: SIGN IN -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 1 OF 10 · ~5 MINUTES</div>
    <div class="phase-title">Sign in to Azure</div>
    <div class="phase-meta"><span><b>creates:</b> nothing</span><span><b>cost:</b> $0</span><span><b>tools:</b> CLI + browser</span></div>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Install Azure CLI (one-time, on your Mac)</div>
    <pre>brew install azure-cli</pre>
    <p>Verify it landed:</p>
    <pre>az --version</pre>
    <p>You should see <code>azure-cli 2.x.x</code>.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Start the device-code login flow</div>
    <pre>az login --use-device-code</pre>
    <p>The command prints something like:</p>
    <pre>To sign in, use a web browser to open the page
https://login.microsoft.com/device and enter the code XXXXXXXXX</pre>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Complete sign-in in your browser</div>
    <ol>
      <li>Open <code>https://login.microsoft.com/device</code></li>
      <li>Enter the 9-character code shown in the terminal</li>
      <li>Sign in with the <b>account that has the active subscription</b></li>
      <li>Click <b>Continue</b> / <b>Allow</b></li>
    </ol>
    <p>Within 1–2 seconds the terminal will show your subscription details.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">4</span> Verify you're on the right subscription</div>
    <pre>az account show --query '{{Name:name, ID:id, State:state, User:user.name}}' -o table</pre>
    <p>Expected output:</p>
    <pre>Name                  ID                                    State    User
--------------------  ------------------------------------  -------  -------------
Azure subscription 1  8fb70e2e-0f55-4708-bd04-7ea4f38f6147  Enabled  you@work.com</pre>
    <p>If <code>State</code> is anything other than <b>Enabled</b>, your subscription isn't active — go back and complete Free Trial activation first.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">5</span> Register the resource providers (one-time per subscription)</div>
    <pre>az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.DBforPostgreSQL
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Storage</pre>
    <p>Wait ~2 minutes, then verify all five show <code>Registered</code>:</p>
    <pre>az provider list \
  --query "[?namespace=='Microsoft.App' || namespace=='Microsoft.OperationalInsights' \
            || namespace=='Microsoft.DBforPostgreSQL' || namespace=='Microsoft.ContainerRegistry' \
            || namespace=='Microsoft.Storage'].{{Provider:namespace, State:registrationState}}" \
  -o table</pre>
  </div>
</section>

<div class="page-break"></div>

<!-- 5. PHASE 2: RG -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 2 OF 10 · &lt; 1 MINUTE</div>
    <div class="phase-title">Resource Group</div>
    <div class="phase-meta"><span><b>creates:</b> 1 RG</span><span><b>cost:</b> $0 (RGs are free)</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>The Resource Group is the container that holds every other resource. We'll name it <code>ai-platform-auto-tester</code> in our reference deployment.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Open the portal</div>
    <p>Go to <a href="https://portal.azure.com">https://portal.azure.com</a> and sign in with the same account you authenticated the CLI with.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Create the resource group</div>
    <ol>
      <li>Top search bar → type <b>"Resource groups"</b> → click the result</li>
      <li>Click <b>+ Create</b> at the top of the page</li>
      <li>Fill in:
        <ul>
          <li><b>Subscription:</b> <code>Azure subscription 1</code> (or whichever)</li>
          <li><b>Resource group:</b> <code>ai-platform-auto-tester</code></li>
          <li><b>Region:</b> <b>Central US</b> <em>(or your team's preferred region — write it down, every other resource must use the same one)</em></li>
        </ul>
      </li>
      <li>Click <b>Review + create</b> → <b>Create</b></li>
    </ol>
    <p>Provisions in ~10 seconds. You can leave the page; we'll come back to this RG over and over.</p>
  </div>

  <div class="callout info">
    <strong>Naming convention.</strong>
    Throughout this guide we use <code>ai-platform-auto-tester</code> as the resource group name. If you choose a different name,
    substitute it in every <code>-g &lt;rg-name&gt;</code> CLI command later. We strongly recommend keeping the name as-is for your first deployment so the reference snippets work verbatim.
  </div>
</section>

<div class="page-break"></div>

<!-- 6. PHASE 3: POSTGRES -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 3 OF 10 · ~5 MINUTES</div>
    <div class="phase-title">PostgreSQL Flexible Server</div>
    <div class="phase-meta"><span><b>creates:</b> Postgres server + database</span><span><b>cost:</b> ~₹1,800/mo (Burstable B1ms)</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>The persistent database. Holds user accounts, run history, per-query results, presets, test-file metadata, hosted-bundle metadata.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Start the create flow</div>
    <ol>
      <li>Top search → <b>"Azure Database for PostgreSQL flexible servers"</b> → click the result</li>
      <li>Click <b>+ Create</b> → choose <b>Flexible server</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Fill the Basics tab</div>
    <table>
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td><b>Subscription</b></td><td>Azure subscription 1</td></tr>
        <tr><td><b>Resource group</b></td><td><code>ai-platform-auto-tester</code></td></tr>
        <tr><td><b>Server name</b></td><td><code>ai-platform-auto-tester-db-XXXX</code> (must be <i>globally</i> unique — append digits if taken)</td></tr>
        <tr><td><b>Region</b></td><td>Central US <em>(same as RG)</em></td></tr>
        <tr><td><b>PostgreSQL version</b></td><td><b>16</b></td></tr>
        <tr><td><b>Workload type</b></td><td><b>Development</b> <em>(picks Burstable B1ms — cheapest tier; production switches you to Memory-Optimized which is ~5× the cost)</em></td></tr>
        <tr><td><b>Authentication method</b></td><td><b>PostgreSQL authentication only</b></td></tr>
        <tr><td><b>Admin username</b></td><td><code>CelerantAITesting</code> <em>(or any name; remember it)</em></td></tr>
        <tr><td><b>Admin password</b></td><td>8+ chars, mix of upper/lower/digit, avoid <code>&lt; &gt; ' " $</code> — <b>save this in a password manager immediately</b></td></tr>
      </tbody>
    </table>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Configure networking</div>
    <ol>
      <li>Click the <b>Networking</b> tab at the top</li>
      <li><b>Connectivity method:</b> select <b>Public access (allowed IP addresses)</b></li>
      <li>Tick: <b>Allow public access from any Azure service within Azure to this server</b></li>
    </ol>
    <p>This lets the Container App (also on Azure) reach the database without VNet plumbing. For a production-hardened setup you'd switch to Private endpoint, but Public + Azure-services-only is plenty secure for QA.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">4</span> Click Review + create → Create</div>
    <p>Provisioning takes <b>3–5 minutes</b>. Don't refresh the page; just wait. Use this time to start Phase 4 (ACR) in another tab.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">5</span> Add the application database</div>
    <p>Once the server is Ready, open it.</p>
    <ol>
      <li>Left sidebar → expand <b>Settings</b> → click <b>Databases</b> <em>(if you don't see it, the Settings group may need to be clicked first to expand)</em></li>
      <li>Click <b>+ Add</b></li>
      <li>Enter database name: <code>auto_tester</code> (or <code>skylar</code>; remember which)</li>
      <li>Click <b>Save</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">6</span> Note these values for Phase 8</div>
    <p>Open the Postgres server's <b>Overview</b> tab. You'll need:</p>
    <div class="kv-box">
      <div class="kv-row"><div class="kv-label">Server name</div><div class="kv-value">ai-platform-auto-tester-db-XXXX.postgres.database.azure.com</div></div>
      <div class="kv-row"><div class="kv-label">Admin username</div><div class="kv-value">CelerantAITesting</div></div>
      <div class="kv-row"><div class="kv-label">Database</div><div class="kv-value">auto_tester</div></div>
      <div class="kv-row"><div class="kv-label">Password</div><div class="kv-value">(the strong password you saved in Step 2)</div></div>
    </div>
  </div>

  <div class="callout">
    <strong>Pitfall: where is "Databases" hidden?</strong>
    Azure recently moved the Databases option inside <b>Settings</b> in the left sidebar.
    If you don't see it as a top-level entry, click <b>Settings</b> first to expand the group — <b>Databases</b> is the 6th item. Alternative: use the portal's Cloud Shell with <code>az postgres flexible-server db create -g ai-platform-auto-tester --server-name &lt;your-server&gt; --database-name auto_tester</code>.
  </div>
</section>

<div class="page-break"></div>

<!-- 7. PHASE 4: ACR -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 4 OF 10 · ~1 MINUTE</div>
    <div class="phase-title">Azure Container Registry (ACR)</div>
    <div class="phase-meta"><span><b>creates:</b> 1 ACR</span><span><b>cost:</b> ~₹400/mo (Basic SKU)</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>ACR is your private Docker image registry. Phase 5 will push the application image into it; Phase 8 will pull from it.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Start the create flow</div>
    <ol>
      <li>Top search → <b>"Container registries"</b> → <b>+ Create</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Fill in Basics</div>
    <table>
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td><b>Resource group</b></td><td><code>ai-platform-auto-tester</code></td></tr>
        <tr><td><b>Registry name</b></td><td><code>aiplatformautotester</code> <em>(lowercase only, globally unique, no hyphens)</em></td></tr>
        <tr><td><b>Location</b></td><td>Central US <em>(same as everything)</em></td></tr>
        <tr><td><b>Pricing plan</b></td><td><b>Basic</b> <em>(Standard/Premium add geo-replication, security scanning — overkill for QA)</em></td></tr>
      </tbody>
    </table>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Review + create → Create</div>
    <p>Provisions in ~1 minute.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">4</span> Enable Admin user</div>
    <p>Once created, open the registry.</p>
    <ol>
      <li>Left sidebar → <b>Settings</b> → <b>Access keys</b></li>
      <li>Toggle <b>Admin user: Enabled</b> → click <b>Save</b></li>
    </ol>
    <p>This lets the Container App authenticate to the registry using a username/password (instead of managed identity, which is more setup).</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">5</span> Note these values for Phase 8</div>
    <div class="kv-box">
      <div class="kv-row"><div class="kv-label">Login server</div><div class="kv-value">aiplatformautotester.azurecr.io</div></div>
      <div class="kv-row"><div class="kv-label">Username</div><div class="kv-value">aiplatformautotester</div></div>
      <div class="kv-row"><div class="kv-label">Password</div><div class="kv-value">password (from Access keys page)</div></div>
    </div>
  </div>
</section>

<div class="page-break"></div>

<!-- 8. PHASE 5: BUILD IMAGE -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 5 OF 10 · ~3 MINUTES (FAST CONNECTION)</div>
    <div class="phase-title">Build &amp; push the application image</div>
    <div class="phase-meta"><span><b>creates:</b> 1 image in ACR</span><span><b>cost:</b> $0 (build minutes free on Basic)</span><span><b>tools:</b> CLI</span></div>
  </div>

  <p>This is the only step that <b>must</b> be done from the command line. The <code>az acr build</code> command uploads your source code, builds the Docker image cloud-side, and stores it in your registry — without needing Docker installed locally.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Open Terminal on your Mac</div>
    <p>Press <b>⌘ + Space</b>, type <b>Terminal</b>, hit Enter.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Clone the source code</div>
    <pre>cd ~
git clone https://github.com/farhan713/ai-platform-auto-tester.git
cd ai-platform-auto-tester</pre>
    <p>Confirm you're in the right place:</p>
    <pre>ls
# Should show: app/  Dockerfile  deploy/  requirements.txt  README.md ...</pre>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Build &amp; push the image (one command)</div>
    <pre>az acr build --registry aiplatformautotester --image skylar-qa:latest .</pre>
    <p>The trailing <code>.</code> tells <code>az</code> to use the current directory as build context.</p>
    <p>You'll see Docker layer output stream by. The whole process takes <b>2–4 minutes</b>. Last lines you want to see:</p>
    <pre>2026/05/07 09:30:36 Successfully pushed image: aiplatformautotester.azurecr.io/skylar-qa:latest
Run ID: cj1 was successful after 2m49s</pre>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">4</span> Verify the image landed</div>
    <pre>az acr repository show-tags --name aiplatformautotester --repository skylar-qa -o table</pre>
    <p>Output:</p>
    <pre>Result
--------
latest</pre>
  </div>

  <div class="callout danger">
    <strong>⚠ Pitfall: upload timeout.</strong>
    On a slow connection, <code>az acr build</code> can hit a write timeout while uploading the source archive. The error looks like:
    <pre style="margin-top:2mm">ERROR: ('Connection aborted.', TimeoutError('The write operation timed out'))</pre>
    Cause: a stale <code>runs/</code> folder (per-job test artefacts from running locally) gets included in the upload — easily 300+ MB. Fix:
    <pre style="margin-top:2mm">mv runs /tmp/runs.bak    # move local test outputs aside
mkdir runs               # keep an empty placeholder so the app still works locally
az acr build --registry aiplatformautotester --image skylar-qa:latest .
mv /tmp/runs.bak runs    # restore after the build succeeds</pre>
    Then re-run the build. With <code>runs/</code> moved aside, the upload is &lt;1 MB and finishes in seconds.
  </div>

  <div class="callout info">
    <strong>Future updates.</strong>
    To redeploy after pulling new code:
    <pre style="margin-top:2mm">git pull
az acr build --registry aiplatformautotester --image skylar-qa:latest .
az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --image aiplatformautotester.azurecr.io/skylar-qa:latest \
  --revision-suffix "v$(date +%s | tail -c 5)"</pre>
    The Container App rolls out the new revision with zero downtime.
  </div>
</section>

<div class="page-break"></div>

<!-- 9. PHASE 6: STORAGE & SHARES -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 6 OF 10 · ~3 MINUTES</div>
    <div class="phase-title">Storage Account &amp; File Shares</div>
    <div class="phase-meta"><span><b>creates:</b> 1 storage acct + 2 file shares</span><span><b>cost:</b> ~₹150/mo</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>The application needs persistent disk for two folders: <code>/app/runs</code> (generated reports + screenshots) and <code>/app/data</code> (uploaded test files + ssLibrary bundles). Without these, every container revision rollout would wipe everything users uploaded. We use Azure File Shares (SMB-mounted into the container).</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Create the storage account</div>
    <ol>
      <li>Top search → <b>"Storage accounts"</b> → <b>+ Create</b></li>
      <li>Fill in <b>Basics</b>:
        <table style="margin-top:2mm">
          <tbody>
            <tr><th>Resource group</th><td><code>ai-platform-auto-tester</code></td></tr>
            <tr><th>Storage account name</th><td><code>aiplatformautotester</code> <em>(lowercase, globally unique — pick something else if taken)</em></td></tr>
            <tr><th>Region</th><td>Central US</td></tr>
            <tr><th>Performance</th><td>Standard</td></tr>
            <tr><th>Redundancy</th><td><b>LRS</b> (Locally-redundant storage — cheapest)</td></tr>
          </tbody>
        </table>
      </li>
      <li>Click <b>Review + create</b> → <b>Create</b> (~30 sec)</li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Create the first file share</div>
    <ol>
      <li>Once created, click <b>Go to resource</b></li>
      <li>Left sidebar → <b>Data storage</b> → <b>File shares</b></li>
      <li>Click <b>+ File share</b></li>
      <li>Fill:
        <ul>
          <li><b>Name:</b> <code>skylar-runs</code></li>
          <li><b>Access tier:</b> Hot</li>
          <li><b>Quota:</b> 5 GiB</li>
        </ul>
      </li>
      <li><b>Create</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Create the second file share</div>
    <p>Repeat Step 2 with a different name:</p>
    <ul>
      <li><b>Name:</b> <code>skylar-data</code></li>
      <li><b>Access tier:</b> Hot</li>
      <li><b>Quota:</b> 5 GiB</li>
    </ul>
    <p>You should now see both shares listed:</p>
    <div class="kv-box">
      <div class="kv-row"><div class="kv-label">skylar-runs</div><div class="kv-value">For /app/runs (reports, screenshots)</div></div>
      <div class="kv-row"><div class="kv-label">skylar-data</div><div class="kv-value">For /app/data (uploaded xlsx + bundles)</div></div>
    </div>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">4</span> Get the storage account access key</div>
    <p>You'll need this to bind the file shares to the Container Apps Environment in Phase 7.</p>
    <ol>
      <li>Same storage account → left sidebar → <b>Security + networking</b> → <b>Access keys</b></li>
      <li>Click <b>Show</b> next to <b>key1</b></li>
      <li>Click the copy icon next to the long base64 <b>Key</b> string</li>
      <li>Paste it into a private notes app — you'll need it once in Phase 7</li>
    </ol>
  </div>

  <div class="callout danger">
    <strong>⚠ Don't paste the access key anywhere public.</strong>
    This key gives full read/write access to your storage account. Treat it like a password.
    Once you've used it in Phase 7, you can stop carrying it around — Azure remembers the binding from there.
  </div>

  <div class="callout">
    <strong>Why two file shares, not one?</strong>
    They have different lifecycle and backup needs. <code>/app/runs</code> grows with every test run (screenshots can be a few MB each); easy to grow or rotate. <code>/app/data</code> is small, important user-uploaded content that you might want to back up before destructive changes. Keeping them separate lets you tune quota and retention per concern.
  </div>
</section>

<div class="page-break"></div>

<!-- 10. PHASE 7: CONTAINER APPS ENV -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 7 OF 10 · ~3 MINUTES</div>
    <div class="phase-title">Container Apps Environment</div>
    <div class="phase-meta"><span><b>creates:</b> 1 env + 2 storage bindings</span><span><b>cost:</b> $0 (env itself is free)</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>The "environment" is the platform layer that hosts one or more Container Apps. It manages networking, log aggregation, and shared storage bindings.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Create the environment</div>
    <p>Two ways to land on the create form:</p>
    <ul>
      <li><b>Direct URL:</b> <code>https://portal.azure.com/#create/Microsoft.ContainerAppEnvironment</code></li>
      <li><b>Or:</b> Home → <b>+ Create a resource</b> → search <b>"Container Apps Environment"</b></li>
    </ul>
    <p>Fill in <b>Basics</b>:</p>
    <table>
      <tbody>
        <tr><th>Resource group</th><td><code>ai-platform-auto-tester</code></td></tr>
        <tr><th>Environment name</th><td><code>skylar-qa-env</code> <em>(or accept the auto-generated name)</em></td></tr>
        <tr><th>Region</th><td>Central US</td></tr>
        <tr><th>Workload Profiles</th><td>Leave default — Consumption only</td></tr>
        <tr><th>Networking</th><td>Leave defaults — auto-create VNet</td></tr>
      </tbody>
    </table>
    <p>Click <b>Review + create</b> → <b>Create</b>. Provisioning takes <b>~2 minutes</b>.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Bind the FIRST file share to the environment</div>
    <ol>
      <li>Once created, click <b>Go to resource</b></li>
      <li>Left sidebar → <b>Settings</b> → <b>Azure Files</b></li>
      <li>Click <b>+ Add</b></li>
      <li>Fill in:
        <ul>
          <li><b>Name:</b> <code>skylar-runs-mount</code></li>
          <li><b>Storage account name:</b> <code>aiplatformautotester</code> (pick from dropdown)</li>
          <li><b>Storage account key:</b> paste the access key from Phase 6 Step 4</li>
          <li><b>File share:</b> <code>skylar-runs</code> (pick from dropdown — it lists shares from the storage account)</li>
          <li><b>Access mode:</b> <b>Read/Write</b></li>
        </ul>
      </li>
      <li>Click <b>Add</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Bind the SECOND file share</div>
    <p>Repeat Step 2 with the second share:</p>
    <ul>
      <li><b>Name:</b> <code>skylar-data-mount</code></li>
      <li><b>File share:</b> <code>skylar-data</code></li>
      <li>Same key, same Read/Write access</li>
    </ul>
    <p>You should now see both bindings listed.</p>
  </div>

  <div class="callout danger">
    <strong>⚠ Pitfall: order matters.</strong>
    The Container App's <b>Volumes</b> dropdown in Phase 9 only shows file shares that are <b>already bound at the env level</b>.
    If you skip Phase 7 Step 2/3 and try to add a volume to the app first, the dropdown will be empty
    with the message <code>No file shares found on this Environment</code>. Bind first, mount second.
  </div>
</section>

<div class="page-break"></div>

<!-- 11. PHASE 8: CONTAINER APP -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 8 OF 10 · ~3 MINUTES</div>
    <div class="phase-title">Container App</div>
    <div class="phase-meta"><span><b>creates:</b> the running app</span><span><b>cost:</b> ~₹2,500/mo (1 vCPU/2 Gi)</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>This is where the app actually starts running. The Container App pulls the image from ACR, sets environment variables (including the database connection string), and exposes an HTTPS URL.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Start the create flow</div>
    <ol>
      <li>Top search → <b>"Container Apps"</b> (no "Environments" suffix)</li>
      <li>Click <b>+ Create</b> → choose <b>Container App</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Basics tab</div>
    <table>
      <tbody>
        <tr><th>Resource group</th><td><code>ai-platform-auto-tester</code></td></tr>
        <tr><th>Container app name</th><td><code>ai-platform-auto-tester</code> <em>(or any name)</em></td></tr>
        <tr><th>Region</th><td>Central US</td></tr>
        <tr><th>Container Apps Environment</th><td>Pick the env you just created (<code>skylar-qa-env</code> or auto-generated name)</td></tr>
      </tbody>
    </table>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Container tab</div>
    <ol>
      <li><b>Use quickstart image:</b> <b>NO</b> (untick)</li>
      <li><b>Image source:</b> <b>Azure Container Registry</b></li>
      <li><b>Registry:</b> <code>aiplatformautotester</code> (pick from dropdown)</li>
      <li><b>Image:</b> <code>skylar-qa</code></li>
      <li><b>Image tag:</b> <code>latest</code></li>
      <li><b>CPU and memory:</b> <b>1.0 CPU cores · 2.0 Gi memory</b> <em>(below 2 GiB, Chromium will OOM)</em></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">4</span> Environment variables</div>
    <p>Click <b>+ Add</b> three times:</p>
    <table>
      <thead><tr><th style="width:30%">Name</th><th>Source</th><th>Value</th></tr></thead>
      <tbody>
        <tr>
          <td><code>DATABASE_URL</code></td><td>Manual</td>
          <td><code>postgresql://CelerantAITesting:&lt;PG-PASSWORD&gt;@ai-platform-auto-tester-db-XXXX.postgres.database.azure.com:5432/auto_tester?sslmode=require</code></td>
        </tr>
        <tr>
          <td><code>SQA_SECRET_KEY</code></td><td>Manual</td>
          <td>A random 64-char hex string. Generate with: <code>openssl rand -hex 32</code></td>
        </tr>
        <tr>
          <td><code>SQA_ALLOW_SIGNUP</code></td><td>Manual</td>
          <td><code>true</code> <em>(set to <code>false</code> later, after your QA team has accounts)</em></td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="callout danger">
    <strong>⚠ URL-encode special characters in the password.</strong>
    If your Postgres password contains <code>@ # % / : ? &amp; +</code> or a space, you must URL-encode them in the <code>DATABASE_URL</code>:
    <table style="margin-top:2mm; font-size:9pt">
      <tbody><tr><td><code>@</code> → <code>%40</code></td><td><code>#</code> → <code>%23</code></td><td><code>%</code> → <code>%25</code></td><td><code>/</code> → <code>%2F</code></td></tr>
      <tr><td><code>:</code> → <code>%3A</code></td><td><code>?</code> → <code>%3F</code></td><td><code>&amp;</code> → <code>%26</code></td><td><code>+</code> → <code>%2B</code></td></tr></tbody>
    </table>
    Plain alphanumerics + <code>! _ - * ( )</code> are safe to use as-is. If you used only those in your password, no encoding needed.
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">5</span> Ingress tab</div>
    <ol>
      <li><b>Ingress:</b> ✅ Enabled</li>
      <li><b>Ingress traffic:</b> <b>Accepting traffic from anywhere</b></li>
      <li><b>Ingress type:</b> HTTP</li>
      <li><b>Target port:</b> <code>5050</code></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">6</span> Review + create → Create</div>
    <p>Provisioning takes <b>~2 minutes</b>. The first revision boots and starts serving traffic.</p>
  </div>
</section>

<div class="page-break"></div>

<!-- 12. PHASE 9: VOLUMES -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 9 OF 10 · ~2 MINUTES</div>
    <div class="phase-title">Mount file-share volumes</div>
    <div class="phase-meta"><span><b>creates:</b> 2 volumes + 2 mounts</span><span><b>cost:</b> $0</span><span><b>tools:</b> portal</span></div>
  </div>

  <p>The Container App is running, but its <code>/app/runs</code> and <code>/app/data</code> are on ephemeral container disk — every revision rollout would wipe them. We now wire those paths to the persistent file shares we bound to the env in Phase 7.</p>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Add the first volume (runs)</div>
    <ol>
      <li>Open the Container App</li>
      <li>Left sidebar → <b>Application</b> → <b>Volumes</b></li>
      <li>Click <b>+ Add</b></li>
      <li>Fill:
        <ul>
          <li><b>Name:</b> <code>runs-vol</code></li>
          <li><b>Volume type:</b> Azure file volume</li>
          <li><b>File share name:</b> <code>skylar-runs-mount</code> <em>(picks from dropdown — populated from Phase 7)</em></li>
          <li><b>Mount options:</b> leave empty</li>
        </ul>
      </li>
      <li>Click <b>Add</b></li>
    </ol>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Add the second volume (data)</div>
    <p>Click <b>+ Add</b> again:</p>
    <ul>
      <li><b>Name:</b> <code>data-vol</code></li>
      <li><b>File share name:</b> <code>skylar-data-mount</code></li>
    </ul>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Mount both volumes into the container</div>
    <ol>
      <li>Same Container App → left sidebar → <b>Application</b> → <b>Containers</b></li>
      <li>Tick the checkbox next to your container row → click <b>Edit and deploy</b> at the top</li>
      <li>In the right pane, scroll to the <b>Volume mounts</b> section → click <b>+ Add new volume mount</b></li>
      <li>First mount:
        <ul>
          <li><b>Volume name:</b> <code>runs-vol</code></li>
          <li><b>Mount path:</b> <code>/app/runs</code></li>
        </ul>
      </li>
      <li>Click <b>+ Add new volume mount</b> again. Second mount:
        <ul>
          <li><b>Volume name:</b> <code>data-vol</code></li>
          <li><b>Mount path:</b> <code>/app/data</code></li>
        </ul>
      </li>
      <li>Click <b>Save</b> in the right pane</li>
      <li>Click <b>Create</b> at the bottom of the page — this creates a new revision with both mounts wired up</li>
    </ol>
    <p>Wait ~1 minute for the new revision to roll out. The page will show the new revision name (e.g. <code>ai-platform-auto-tester--XXXX</code>) and turn <b>Healthy</b>.</p>
  </div>

  <div class="callout success">
    <strong>What you just did.</strong>
    All four artefact stores now persist across revision rollouts and container restarts:
    <table style="margin-top:2mm">
      <tbody>
        <tr><td><b>users / runs / per-query results</b></td><td>→ PostgreSQL</td></tr>
        <tr><td><b>screenshots / REPORT.html / per-query JSONs</b></td><td>→ <code>skylar-runs</code> file share</td></tr>
        <tr><td><b>uploaded test xlsx / hosted bundles</b></td><td>→ <code>skylar-data</code> file share</td></tr>
      </tbody>
    </table>
  </div>
</section>

<div class="page-break"></div>

<!-- 13. PHASE 10: FIRST SIGN-IN -->
<section class="section">
  <div class="phase-banner">
    <div class="phase-tag">PHASE 10 OF 10 · ~1 MINUTE</div>
    <div class="phase-title">First sign-in &amp; lockdown</div>
    <div class="phase-meta"><span><b>creates:</b> first user account</span><span><b>cost:</b> $0</span><span><b>tools:</b> browser</span></div>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">1</span> Get the application URL</div>
    <ol>
      <li>Open the Container App → <b>Overview</b> tab</li>
      <li>Look for <b>Application URL</b> in the top-right</li>
      <li>It looks like: <code>https://ai-platform-auto-tester.&lt;random&gt;.centralus.azurecontainerapps.io</code></li>
    </ol>
    <p>Click it. Your browser opens the live tool.</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">2</span> Create the first account</div>
    <p>You'll be redirected to the <code>/login</code> page.</p>
    <ol>
      <li>Click <b>Create one</b> under the form</li>
      <li>Fill in name, work email, password (≥ 8 characters)</li>
      <li>Click <b>Create account</b></li>
    </ol>
    <p>You're in. Dashboard shows zero runs (correct — fresh tenant).</p>
  </div>

  <div class="step">
    <div class="step-head"><span class="step-num">3</span> Lock down public signup once your team is in</div>
    <p>By default, anyone with the URL can sign up. Once your QA team has all created accounts, disable public signup:</p>
    <pre>az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --set-env-vars SQA_ALLOW_SIGNUP=false</pre>
    <p>The app rolls out a new revision in ~30 seconds with the flag flipped. From this point on, only existing users can sign in; <code>/signup</code> shows a polite "Public signup is disabled" message.</p>
    <p>To re-enable later (e.g. when adding a new tester):</p>
    <pre>az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --set-env-vars SQA_ALLOW_SIGNUP=true</pre>
  </div>

  <div class="callout success">
    <strong>🎉 Deployment complete.</strong>
    You now have a working, multi-user, persistent QA automation tool on Azure with HTTPS. Distribute the URL + the <i>Tester Guide</i> PDF to your team. They sign up, run tests, share results.
  </div>
</section>

<div class="page-break"></div>

<!-- 14. DAY-TO-DAY -->
<section class="section">
  <h1>14 · Day-to-day operations</h1>

  <h2>View live application logs</h2>
  <pre>az containerapp logs show -g ai-platform-auto-tester -n ai-platform-auto-tester --follow</pre>
  <p>Streams every Flask request line + every <code>[run]</code> / <code>[login]</code> / <code>[q01]</code> event from the runner. Press <b>Ctrl+C</b> to stop.</p>

  <h2>Push new code from GitHub → Azure</h2>
  <pre>cd ~/ai-platform-auto-tester
git pull origin main

# Move local runs/ aside if you've been using local Docker (avoids upload timeout)
mv runs /tmp/runs.bak 2>/dev/null; mkdir -p runs

# Build new image
az acr build --registry aiplatformautotester --image skylar-qa:latest .

# Roll new revision (force pull of new image even though :latest tag is unchanged)
az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --image aiplatformautotester.azurecr.io/skylar-qa:latest \
  --revision-suffix "v$(date +%s | tail -c 5)"

# Restore your local runs (Azure doesn't need them)
rm -rf runs && mv /tmp/runs.bak runs 2>/dev/null</pre>
  <p>Total: ~5 minutes. Zero-downtime — Container Apps keeps the old revision serving traffic until the new one is healthy, then switches.</p>

  <h2>Restart the app (no code change)</h2>
  <pre>REV=$(az containerapp show -g ai-platform-auto-tester -n ai-platform-auto-tester \
        --query 'properties.latestRevisionName' -o tsv)
az containerapp revision restart -g ai-platform-auto-tester \
  -n ai-platform-auto-tester --revision "$REV"</pre>

  <h2>Scale up CPU/RAM (if QA team grows)</h2>
  <pre>az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --cpu 2.0 --memory 4.0Gi --max-replicas 3</pre>
  <p>Three replicas means three QA runs can execute in parallel. Each replica costs ~₹2,500/mo, so three replicas ≈ ₹7,500/mo.</p>

  <h2>Connect to Postgres directly</h2>
  <pre>PG=$(az postgres flexible-server list -g ai-platform-auto-tester --query '[0].name' -o tsv)
psql "host=${{PG}}.postgres.database.azure.com port=5432 dbname=auto_tester \
      user=CelerantAITesting sslmode=require"
# (asks for the password you set in Phase 3)</pre>

  <h2>Tear it ALL down</h2>
  <p>One command kills every resource we created:</p>
  <pre>az group delete --name ai-platform-auto-tester --yes --no-wait</pre>
  <div class="callout danger">
    <strong>⚠ Irreversible.</strong>
    Deleting the resource group destroys the Postgres database (with all user data and run history), the file shares (with all reports and uploaded files), the Container App, the registry, the image, and the env binding — everything. Make sure to back up anything you care about first.
  </div>
</section>

<div class="page-break"></div>

<!-- 15. COST -->
<section class="section">
  <h1>15 · Cost breakdown</h1>

  <p>Steady-state monthly cost at QA team usage levels (~50 runs/month, idle most of the day):</p>

  <table class="cost-table">
    <thead><tr><th>Resource</th><th>Configuration</th><th>Approx. ₹/month</th><th>Approx. $/month</th></tr></thead>
    <tbody>
      <tr><td>Container App</td><td>1 vCPU / 2 GiB · 1 replica · always-on</td><td>2,500</td><td>$30</td></tr>
      <tr><td>PostgreSQL Flexible Server</td><td>Burstable B1ms · 32 GB storage</td><td>1,800</td><td>$13</td></tr>
      <tr><td>Azure Container Registry</td><td>Basic SKU</td><td>400</td><td>$5</td></tr>
      <tr><td>Storage Account (File Shares)</td><td>Standard LRS · ~5 GB used</td><td>150</td><td>$1</td></tr>
      <tr><td>Log Analytics Workspace</td><td>Auto-created · ingestion-priced</td><td>~50</td><td>$1</td></tr>
      <tr><td>Bandwidth (egress)</td><td>~5 GB/mo at QA scale</td><td>~50</td><td>$1</td></tr>
      <tr class="total"><td colspan="2">Total</td><td>~₹4,950</td><td>~$51</td></tr>
    </tbody>
  </table>

  <h2>Free Trial coverage</h2>
  <p>New Azure accounts get $200 in credit valid for 30 days — that covers ~4 months of this stack. After the credit runs out, billing kicks in automatically (you can opt out with one click in the portal).</p>

  <h2>Cost-cutting options</h2>
  <table>
    <thead><tr><th>If you want to save money...</th><th>...do this</th><th>Tradeoff</th></tr></thead>
    <tbody>
      <tr><td>Cut Container App cost in half</td><td>Set <b>min-replicas=0</b> to scale to zero when idle</td><td>5–10s cold start on first request after idle period; not ideal for live demos</td></tr>
      <tr><td>Skip Postgres backup retention</td><td>Reduce backup retention to 7 days (default 7 is already minimum on Flexible Server)</td><td>Already minimal — no further savings here</td></tr>
      <tr><td>Avoid bandwidth costs</td><td>Make sure the QA team uses short report-zip downloads, not streaming</td><td>None practical at QA scale; bandwidth is already &lt;$1/mo</td></tr>
      <tr><td>Tear down between sprints</td><td>Delete the RG when not actively testing; redeploy when needed</td><td>30 minutes to redeploy, must re-create user accounts (data is destroyed)</td></tr>
    </tbody>
  </table>

  <h2>Setting a budget alert</h2>
  <p>Catch surprise bills early — set a $100/month cap that emails you if hit:</p>
  <pre>az consumption budget create \
  --budget-name skylar-qa-budget --amount 100 \
  --time-grain Monthly \
  --start-date "$(date +%Y-%m-01)" \
  --end-date "$(date -v+1y +%Y-%m-01)"</pre>
</section>

<div class="page-break"></div>

<!-- 16. PITFALLS -->
<section class="section">
  <h1>16 · Common pitfalls (real ones we hit)</h1>

  <p>Every one of these came up during the reference deployment. The fixes are baked into the latest code; this section warns you so you recognise them if they recur.</p>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">1</span> Microsoft account exists but no subscription</div>
    <p>Symptom: Every <code>az</code> command fails with <code>No subscriptions found for &lt;email&gt;</code>. Browser portal shows blank "Cost analysis" or no resource list.</p>
    <div class="pitfall-fix"><b>Fix:</b> Sign up at <a href="https://azure.microsoft.com/free">azure.microsoft.com/free</a> with a credit card (won't be charged unless trial ends + you upgrade). Subscription activates within 60 seconds. Re-run <code>az login --use-device-code</code>.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">2</span> ACR name not globally unique</div>
    <p>Symptom: Phase 4 create form shows red error "The registry name is already in use".</p>
    <div class="pitfall-fix"><b>Fix:</b> Append digits or your initials to the name — e.g. <code>aiplatformautotester01</code>. ACR names share a global namespace across all of Azure.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">3</span> Postgres password rejected</div>
    <p>Symptom: Phase 3 create form shows "Password does not meet complexity requirements".</p>
    <div class="pitfall-fix"><b>Fix:</b> Azure requires 8–128 chars, with at least 3 of: uppercase, lowercase, digit, symbol. Cannot contain the username (<code>CelerantAITesting</code>). Avoid <code>&lt; &gt; ' " $</code> to keep CLI usage easy. <i>Example that works:</i> <code>AiTesting2026!</code>.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">4</span> "Databases" option missing in Postgres sidebar</div>
    <p>Symptom: After creating the server, you can't find where to add the <code>auto_tester</code> database.</p>
    <div class="pitfall-fix"><b>Fix:</b> The option is hidden inside <b>Settings</b> in the left sidebar — click to expand, then <b>Databases</b> appears. Alternative: use the portal Cloud Shell with <code>az postgres flexible-server db create -g ai-platform-auto-tester --server-name &lt;your-server&gt; --database-name auto_tester</code>.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">5</span> <code>az acr build</code> upload timeout</div>
    <p>Symptom: <code>ERROR: ('Connection aborted.', TimeoutError('The write operation timed out'))</code></p>
    <div class="pitfall-fix"><b>Fix:</b> Move the local <code>runs/</code> folder aside before building (it's often 300+ MB of test artefacts that get uploaded even though they're in <code>.dockerignore</code>):
    <pre style="margin-top:1mm; font-size:8pt">mv runs /tmp/runs.bak; mkdir runs; az acr build ...; rm -rf runs; mv /tmp/runs.bak runs</pre></div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">6</span> Volume dropdown empty in Container App</div>
    <p>Symptom: Phase 9 — clicking <b>+ Add volume</b> shows "No file shares found on this Environment".</p>
    <div class="pitfall-fix"><b>Fix:</b> You skipped Phase 7 Step 2/3. The file share must be bound at the env level <b>before</b> it appears in the app's volume dropdown. Go back to <b>Container Apps Environment → Settings → Azure Files</b> and add the binding.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">7</span> Bundle file vanishes after revision rollout</div>
    <p>Symptom: User uploaded a Site Search bundle, runs work fine. After redeploying, all bundle requests return 404 — the JS file isn't found.</p>
    <div class="pitfall-fix"><b>Fix:</b> You only mounted <code>/app/runs</code> persistently, not <code>/app/data</code> (where bundles live). Phase 9 of this guide mounts both. If your existing app is missing the data mount, follow Phase 9 Steps 2–3 to add it. Old bundles will need to be re-uploaded once.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">8</span> Site Search timeouts despite valid credentials</div>
    <p>Symptom: Every keyword times out with "search_keywords call missing".</p>
    <div class="pitfall-fix"><b>Fix:</b> The page's <code>ssLibrary.init()</code> is failing to authenticate. Most often: wrong JWT credentials in <b>Tenant Override</b>. Test with the demo's <code>r222ipid</code> / <code>W0rkH0us3!</code> first to verify the flow, then swap in your real tenant credentials.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">9</span> SQL Agent run-sql timeout — endpoint reached but no response captured</div>
    <p>Symptom: <code>generate-sql</code> returns HTTP 200, then <code>run-sql</code> hangs for the full 120s timeout, marked TIMEOUT.</p>
    <div class="pitfall-fix"><b>Fix:</b> Often a transient slowdown on the tenant server. If persistent, bump <b>run-sql timeout</b> to <code>300000</code>–<code>600000</code> (5–10 min) under <b>Advanced timeouts</b> on the New Run page.</div>
  </div>

  <div class="pitfall">
    <div class="pitfall-title"><span class="pitfall-num">10</span> Pre-question phase very slow (~3 min before any query runs)</div>
    <p>Symptom: After clicking Start QA Run, you wait minutes before the first <code>[q01]</code> log line appears.</p>
    <div class="pitfall-fix"><b>Fix:</b> The latest code (v3.6+) replaced <code>wait_until="load"</code> with <code>"domcontentloaded"</code> and removed three <code>wait_for_load_state("networkidle")</code> calls (Celerant's SPA polls heartbeats and never goes idle). If on an older version, redeploy with the current image — pre-question time drops from ~227s to ~30-60s.</div>
  </div>
</section>

<div class="page-break"></div>

<!-- 17. FAQ / TROUBLESHOOTING -->
<section class="section">
  <h1>17 · Troubleshooting / FAQ</h1>

  <h3>Container App won't start — stuck in "Activating"</h3>
  <p>Check the logs: <code>az containerapp logs show -g ai-platform-auto-tester -n ai-platform-auto-tester --tail 100</code>. Most common cause: <code>DATABASE_URL</code> typo (especially un-encoded special characters). Re-check Phase 8 Step 4.</p>

  <h3>"Database not ready yet" page on first load</h3>
  <p>The app retries the Postgres connection for ~30s on startup. If it still doesn't recover, the Postgres firewall is likely blocking. Re-verify Phase 3 Step 3 — <b>Allow public access from any Azure service</b> must be ticked.</p>

  <h3>Custom domain instead of <code>*.azurecontainerapps.io</code></h3>
  <p>Add a CNAME in your DNS pointing your domain to the auto-generated FQDN, then:</p>
  <pre>az containerapp hostname add -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --hostname qa.yourcompany.com
az containerapp hostname bind -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --hostname qa.yourcompany.com --environment skylar-qa-env --validation-method CNAME</pre>
  <p>Azure auto-issues a managed certificate (free, auto-renews).</p>

  <h3>Subscription quota exceeded</h3>
  <p>Free Trial subscriptions cap regional vCPUs at 4. If you've created other resources today, you may be at the limit. Either delete unused resources or pick a different region (try <b>westus2</b> or <b>eastus</b>).</p>

  <h3>The QA tool is up but I can't reach the test target (Celerant tenant)</h3>
  <p>Tenants on private VPNs aren't reachable from public Azure. Either:</p>
  <ul>
    <li>Coordinate with the client's IT to whitelist the Container App's outbound IP:
      <pre>az containerapp show -g ai-platform-auto-tester -n ai-platform-auto-tester \
  --query 'properties.outboundIpAddresses' -o tsv</pre>
    </li>
    <li>Or run the tool on a VM inside the client's VNet</li>
  </ul>

  <h3>Run is stuck "running" but nothing is happening</h3>
  <p>If a revision rolled out while a run was in progress, the Playwright thread died but the database row stayed. Have the user click <b>⏹ Stop run</b> to mark it stopped. Future runs work normally.</p>

  <h3>How do I view a run's full report locally?</h3>
  <p>From the run's page, click <b>↓ Download report (zip)</b>. Extract on your laptop, double-click <code>REPORT.html</code> — opens in any browser, all screenshots inline, no internet needed.</p>

  <h3>Reset a user's password</h3>
  <p>Currently no built-in self-service. Connect to Postgres and update directly:</p>
  <pre>UPDATE users SET password_hash = 'pbkdf2:sha256:600000$...$...' WHERE email='user@example.com';</pre>
  <p>Generate the hash with: <code>python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('newpass1234'))"</code></p>
</section>

<div class="page-break"></div>

<!-- 18. QUICK REFERENCE -->
<section class="section">
  <h1>18 · Quick reference card</h1>

  <h2>Resource names (reference deployment)</h2>
  <div class="kv-box">
    <div class="kv-row"><div class="kv-label">Resource group</div><div class="kv-value">ai-platform-auto-tester</div></div>
    <div class="kv-row"><div class="kv-label">Region</div><div class="kv-value">Central US</div></div>
    <div class="kv-row"><div class="kv-label">Postgres server</div><div class="kv-value">ai-platform-auto-tester-db-XXXX</div></div>
    <div class="kv-row"><div class="kv-label">Postgres database</div><div class="kv-value">auto_tester</div></div>
    <div class="kv-row"><div class="kv-label">Postgres admin</div><div class="kv-value">CelerantAITesting</div></div>
    <div class="kv-row"><div class="kv-label">ACR</div><div class="kv-value">aiplatformautotester</div></div>
    <div class="kv-row"><div class="kv-label">Storage account</div><div class="kv-value">aiplatformautotester (same name OK — different namespace)</div></div>
    <div class="kv-row"><div class="kv-label">File shares</div><div class="kv-value">skylar-runs (→ /app/runs) · skylar-data (→ /app/data)</div></div>
    <div class="kv-row"><div class="kv-label">Container Apps env</div><div class="kv-value">skylar-qa-env</div></div>
    <div class="kv-row"><div class="kv-label">Container App</div><div class="kv-value">ai-platform-auto-tester</div></div>
    <div class="kv-row"><div class="kv-label">Image</div><div class="kv-value">aiplatformautotester.azurecr.io/skylar-qa:latest</div></div>
  </div>

  <h2>Most-used CLI commands</h2>
  <table>
    <thead><tr><th>What</th><th>Command</th></tr></thead>
    <tbody>
      <tr><td>Sign in</td><td><code>az login --use-device-code</code></td></tr>
      <tr><td>Live logs</td><td><code>az containerapp logs show -g ai-platform-auto-tester -n ai-platform-auto-tester --follow</code></td></tr>
      <tr><td>Build new image</td><td><code>az acr build --registry aiplatformautotester --image skylar-qa:latest .</code></td></tr>
      <tr><td>Roll new revision</td><td><code>az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester --image aiplatformautotester.azurecr.io/skylar-qa:latest --revision-suffix "v$(date +%s | tail -c 5)"</code></td></tr>
      <tr><td>Lock signup</td><td><code>az containerapp update -g ai-platform-auto-tester -n ai-platform-auto-tester --set-env-vars SQA_ALLOW_SIGNUP=false</code></td></tr>
      <tr><td>Tear it all down</td><td><code>az group delete -n ai-platform-auto-tester --yes --no-wait</code></td></tr>
    </tbody>
  </table>

  <h2>Test the deployment</h2>
  <ol>
    <li>Open the Container App URL → click <b>Create one</b> → sign up</li>
    <li><b>+ New Run</b> → 🧠 SQL AI Engine → fill tenant URL + creds → upload xlsx → Start</li>
    <li>Or → 🔎 Site Search → upload bundle on Test Pages → Start</li>
    <li>Watch live progress. Open report when done.</li>
  </ol>

  <footer class="legal">
    Skylar IQ QA Tool · Azure Deployment Guide · v3.6 · {DATE}<br>
    Internal documentation. Not for external distribution without permission.
  </footer>
</section>

</body></html>"""

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
            <span>Skylar IQ QA Tool — Azure Deployment Guide · v3.6</span>
            <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
        </div>""",
    )
    browser.close()

import shutil
shutil.copy(OUT, OUT_DESKTOP)
print(f"  Built: {OUT}")
print(f"  Desktop: {OUT_DESKTOP}")
