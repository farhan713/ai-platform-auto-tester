// Build Skylar IQ QA Tool User Guide as a polished .docx
// Run: node /tmp/build_userguide_docx.js

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  ExternalHyperlink, InternalHyperlink, Bookmark,
  TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, PageBreak,
} = require('docx');

// --- Theme ---
const THEME = {
  heading: '1A3A6E',     // dark blue
  subheading: '2E5AA8',  // mid blue
  codeBg: 'F4F6FA',      // very light grey-blue
  borderGrey: 'CCCCCC',
  tableHeaderBg: 'D5E1F2',
  bodyFont: 'Calibri',
  monoFont: 'Consolas',
};

// --- Page geometry (US Letter, 1" margins) ---
const PAGE = { W: 12240, H: 15840, MARGIN: 1440, CONTENT_W: 9360 };

// --- Helpers ---------------------------------------------------------------
const cellBorder = {
  style: BorderStyle.SINGLE, size: 4, color: THEME.borderGrey,
};
const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

function txt(s, opts = {}) {
  return new TextRun({ text: s, ...opts });
}
function code(s) {
  return new TextRun({ text: s, font: THEME.monoFont, size: 20, color: '0F172A' });
}
function bold(s) {
  return new TextRun({ text: s, bold: true });
}
function plainP(...runs) {
  return new Paragraph({ children: runs, spacing: { before: 60, after: 60, line: 300 } });
}
function quoteP(...runs) {
  return new Paragraph({
    children: runs,
    indent: { left: 360 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: THEME.subheading, space: 12 } },
    spacing: { before: 120, after: 120, line: 300 },
    shading: { fill: THEME.codeBg, type: ShadingType.CLEAR, color: 'auto' },
  });
}
function h1(text, bookmarkId) {
  const children = [new TextRun({ text, bold: true, color: THEME.heading, size: 36 })];
  if (bookmarkId) {
    return new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 360, after: 180 },
      children: [
        new Bookmark({ id: bookmarkId, children }),
      ],
    });
  }
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 180 },
    children,
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, color: THEME.subheading, size: 28 })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, bold: true, color: THEME.subheading, size: 24 })],
  });
}
function bullet(...runs) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { before: 40, after: 40, line: 280 },
    children: runs,
  });
}

// Code block — implemented as a single-cell shaded table for clear visual separation
function codeBlock(linesText) {
  const lines = linesText.replace(/\n$/, '').split('\n');
  const paras = lines.map(line =>
    new Paragraph({
      spacing: { before: 0, after: 0, line: 240 },
      children: [new TextRun({ text: line === '' ? ' ' : line, font: THEME.monoFont, size: 20 })],
    })
  );
  return new Table({
    width: { size: PAGE.CONTENT_W, type: WidthType.DXA },
    columnWidths: [PAGE.CONTENT_W],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: PAGE.CONTENT_W, type: WidthType.DXA },
            shading: { fill: THEME.codeBg, type: ShadingType.CLEAR, color: 'auto' },
            margins: { top: 120, bottom: 120, left: 200, right: 200 },
            borders: {
              top: { style: BorderStyle.SINGLE, size: 4, color: THEME.borderGrey },
              bottom: { style: BorderStyle.SINGLE, size: 4, color: THEME.borderGrey },
              left: { style: BorderStyle.SINGLE, size: 12, color: THEME.subheading },
              right: { style: BorderStyle.SINGLE, size: 4, color: THEME.borderGrey },
            },
            children: paras,
          }),
        ],
      }),
    ],
  });
}

// Build a styled table from header row + body rows.
// rows: [[header cells], [body row cells], ...]   — each cell is a string OR an array of TextRuns
// columnWidths: array of widths in DXA, must sum to PAGE.CONTENT_W
function dataTable(rows, columnWidths) {
  const totalW = columnWidths.reduce((a, b) => a + b, 0);
  const tRows = rows.map((row, rIdx) => {
    const isHeader = rIdx === 0;
    return new TableRow({
      tableHeader: isHeader,
      children: row.map((cell, cIdx) => {
        let cellRuns;
        if (Array.isArray(cell)) cellRuns = cell;
        else if (cell instanceof TextRun) cellRuns = [cell];
        else cellRuns = [new TextRun({ text: String(cell ?? ''), bold: isHeader })];
        return new TableCell({
          width: { size: columnWidths[cIdx], type: WidthType.DXA },
          shading: isHeader
            ? { fill: THEME.tableHeaderBg, type: ShadingType.CLEAR, color: 'auto' }
            : undefined,
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          borders: cellBorders,
          children: [new Paragraph({ children: cellRuns, spacing: { before: 0, after: 0, line: 260 } })],
        });
      }),
    });
  });
  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    columnWidths,
    rows: tRows,
  });
}

// =============================================================================
// CONTENT
// =============================================================================
const content = [];

// --- Title block ---
content.push(
  new Paragraph({
    spacing: { before: 600, after: 100 },
    children: [new TextRun({ text: 'Skylar IQ QA Tool', bold: true, color: THEME.heading, size: 56 })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 200 },
    children: [new TextRun({ text: 'User Documentation', color: THEME.subheading, size: 36 })],
  }),
  quoteP(
    bold('A self-service automation suite for QA-testing the Celerant Back Office Skylar IQ SQL Agent on any tenant. '),
    txt('Provide a login URL, credentials, and an Excel file of natural-language questions; the tool drives the real Skylar IQ UI through a headless browser, captures every API call, and produces a polished QA report.'),
  ),
  new Paragraph({ spacing: { before: 200 }, children: [
    txt('Version 1.0 · '), txt('Generated for internal QA use', { italics: true }),
  ]}),
  new Paragraph({ children: [new PageBreak()] }),
);

// --- Table of Contents ---
content.push(
  h1('Table of contents'),
  new TableOfContents('Contents', { hyperlink: true, headingStyleRange: '1-2' }),
  new Paragraph({ children: [new PageBreak()] }),
);

// =============================================================================
// 1. What this tool does
// =============================================================================
content.push(
  h1('1. What this tool does'),
  plainP(txt('When testing the Skylar IQ SQL Agent manually, a QA engineer would have to:')),
  bullet(txt('Open the client’s Celerant Back Office login page')),
  bullet(txt('Enter username + password + handle the Machine ID quirk')),
  bullet(txt('Click '), bold('Setup → SQL Agent')),
  bullet(txt('Type a natural-language question into the chat box')),
  bullet(txt('Wait for the result table to appear')),
  bullet(txt('Click '), bold('Generate Visualization'), txt(' if available')),
  bullet(txt('Open browser DevTools to inspect the API calls')),
  bullet(txt('Repeat for every question')),
  bullet(txt('Manually compile a report')),
  plainP(
    txt('This tool '),
    bold('automates that entire workflow'),
    txt(' for any number of questions, against '),
    bold('any client tenant'),
    txt(', and produces a structured QA report with screenshots and raw API data — so you can run regression tests for multiple clients in parallel or as part of a scheduled job.'),
  ),
  h2('What it captures per query'),
  dataTable([
    ['Captured', 'Detail'],
    [[bold('generate_sql API call')], 'The LLM call that converts the natural-language question into SQL — request body, response status, response payload, timing'],
    [[bold('run-sql API call')], 'The actual SQL execution against the client’s database — full request and response'],
    [[bold('generate-viz API call')], 'The chart-generation LLM call — chart type, axes, columns, data points'],
    [[bold('Screenshots')], 'Input box (before submit), result table (after run-sql), chart (after generate-viz)'],
    [[bold('Validations')], 'HTTP status, row counts, column-name sync, chart payload integrity'],
  ], [3000, 6360]),
);

// =============================================================================
// 2. Prerequisites
// =============================================================================
content.push(
  h1('2. Before you start — prerequisites'),
  plainP(txt('You need:')),
  dataTable([
    ['Requirement', 'How to check', 'If missing'],
    [[bold('Python 3.10 or newer')], [code('python3 --version')], 'Install from python.org (Mac/Win) or apt install python3 (Linux)'],
    [[bold('pip')], [code('python3 -m pip --version')], 'Comes with Python 3.4+; otherwise python3 -m ensurepip'],
    [[bold('git command')], [code('git --version')], 'Install from git-scm.com'],
    [[bold('Modern browser')], 'For opening the local web UI', 'Already on your machine'],
    [[bold('~200 MB free disk')], [code('df -h')], 'Free up space'],
    [[bold('Internet access')], 'For downloading deps + reaching client', ''],
  ], [2800, 3300, 3260]),
  quoteP(bold('Note: '), txt('You do NOT need to install Chrome separately for the tool — Playwright downloads its own headless Chromium during install.')),
);

// =============================================================================
// 3. Installation
// =============================================================================
content.push(
  h1('3. Installation (one-time, ~5 minutes)'),
  h2('Step 3.1 — Clone the repository'),
  plainP(txt('In your terminal, run:')),
  codeBlock('git clone https://github.com/farhan713/skylar-qa-tool.git\ncd skylar-qa-tool'),
  plainP(txt('(Replace the URL with whatever your repo URL is.)')),
  quoteP(bold('What this does: '), txt('Downloads the latest version of the tool’s source code into a folder called '), code('skylar-qa-tool'), txt(' and changes your working directory into it.')),

  h2('Step 3.2 — Install Python dependencies'),
  codeBlock('python3 -m pip install -r requirements.txt'),
  quoteP(
    bold('What this does: '),
    txt('Reads the requirements.txt file and installs everything the tool depends on — Playwright (browser automation), Flask (web UI), openpyxl (Excel reading), Jinja2 (HTML templating).'),
  ),
  quoteP(
    bold('Expected duration: '), txt('~30 seconds. You’ll see lines like '),
    code('Successfully installed playwright-1.49.0 flask-3.1.0 ...'),
  ),
  plainP(txt('If you see permission errors on Mac/Linux, prefix with '), code('sudo'), txt(':')),
  codeBlock('sudo python3 -m pip install -r requirements.txt'),
  plainP(txt('On Windows, run the terminal as Administrator.')),

  h2('Step 3.3 — Install the headless browser (one-time)'),
  codeBlock('python3 -m playwright install chromium'),
  quoteP(
    bold('What this does: '),
    txt('Downloads the headless Chromium browser that the tool will use to drive the Skylar IQ UI. It’s stored in your user’s cache folder, not the repo, so it only needs to be done once per machine — not per-clone.'),
  ),
  quoteP(bold('Expected duration: '), txt('~30 seconds. You’ll see a download progress bar reaching 100% of ~150 MB.')),

  h2('Step 3.4 — Verify the install'),
  codeBlock('python3 -c "from app.runner import run; print(\'OK\')"'),
  plainP(
    txt('If you see '), code('OK'),
    txt(', the install succeeded. If you see '),
    code('ModuleNotFoundError: No module named \'playwright\''),
    txt(', go back to Step 3.2.'),
  ),
);

// =============================================================================
// 4. First run
// =============================================================================
content.push(
  h1('4. Your first run (using the sample file)'),
  plainP(
    txt('A 5-question sample ('), code('data/sample_questions.xlsx'),
    txt(') ships with the tool so you can verify everything works before importing your own questions.'),
  ),
  h2('Step 4.1 — Launch the web UI'),
  codeBlock('./run-server.sh'),
  plainP(txt('(On Windows: '), code('python -m app.server'), txt(')')),
  quoteP(
    bold('What you’ll see in the terminal:'),
  ),
  codeBlock('Skylar IQ QA Tool — http://127.0.0.1:5050/\n * Running on http://127.0.0.1:5050'),
  quoteP(
    bold('What happens next: '),
    txt('Your default browser opens automatically to that URL. If it doesn’t, copy/paste the URL into your browser manually.'),
  ),

  h2('Step 4.2 — Fill in the form'),
  plainP(txt('The landing page shows a '), bold('Start a new run'), txt(' form. Fill in:')),
  dataTable([
    ['Field', 'What to enter for the test run'],
    [[bold('Login URL')], 'The full Skylar IQ login URL of the client you want to test, e.g. https://acme-store.com:8443/backoffice/?mid=100'],
    [[bold('Username')], 'The Skylar IQ username for that client'],
    [[bold('Password')], 'The matching password'],
    [[bold('Machine ID')], 'Leave at 100 unless your client uses a different value'],
    [[bold('SQL Agent path')], 'Leave at the default unless told otherwise'],
    [[bold('run-sql timeout (ms)')], '120000 (2 minutes) is fine for most cases'],
    [[bold('generate-viz timeout (ms)')], '120000 (2 minutes)'],
    [[bold('Questions Excel')], 'Click Choose File and pick data/sample_questions.xlsx from the cloned repo'],
  ], [2800, 6560]),
  plainP(txt('Click '), bold('Start QA Run'), txt('.')),

  h2('Step 4.3 — Watch it run'),
  plainP(txt('You’re redirected to the live progress page. You’ll see:')),
  bullet(bold('Configuration table'), txt(' at the top showing exactly what was submitted')),
  bullet(bold('Status badge'), txt(': queued → running → done (or failed)')),
  bullet(bold('Counters'), txt(' for PASS / PARTIAL / FAIL / TIMEOUT updating in real time')),
  bullet(bold('Progress bar'), txt(' filling up as queries complete')),
  bullet(bold('Last 5 queries'), txt(' table showing per-query status and duration')),
  bullet(bold('Event log'), txt(' (a black panel) streaming every action:')),
  codeBlock('[login] navigating https://...\n[login] success — at https://.../wrmsscreen\n[nav] SQL Agent ready\n[q01] Show me a list of all my calibers\n[q01] PASS (5764 ms)\n[q02] ...'),
  quoteP(
    bold('Expected duration for the 5-question sample: '),
    txt('1–10 minutes depending on client LLM speed. Some queries finish in 6 seconds; others (especially aggregate queries with joins) can take 60+ seconds.'),
  ),
  plainP(txt('When the run finishes:')),
  bullet(txt('Status badge turns green: '), bold('done')),
  bullet(txt('An '), bold('Open final report ↗'), txt(' button appears')),
  bullet(txt('The final HTML report opens in a new tab')),
);

// =============================================================================
// 5. Custom questions
// =============================================================================
content.push(
  h1('5. Running with your own questions'),
  plainP(txt('Once you’ve confirmed the sample works, replace it with your own Excel file:')),
  bullet(txt('Prepare your '), code('.xlsx'), txt(' (see Section 6)')),
  bullet(txt('Refresh the web UI at '), code('http://127.0.0.1:5050/')),
  bullet(txt('Fill the form again, but this time upload your own '), code('.xlsx')),
  bullet(txt('Click '), bold('Start QA Run')),
  plainP(txt('There’s no limit on the number of questions — runs of 50, 100, or 500+ are fine. Per-query budget defaults to 2 minutes, so you can size-estimate by:')),
  quoteP(txt('Total runtime ≈ (fast queries × 10 sec) + (slow queries × ~120 sec)')),
);

// =============================================================================
// 6. Excel format
// =============================================================================
content.push(
  h1('6. Excel file format'),
  plainP(txt('Your '), code('.xlsx'), txt(' must look like this (only the '), bold('first sheet'), txt(' is read):')),
  dataTable([
    ['natural_language_query', 'expected_sql (optional)'],
    ['Show me a list of all my calibers', [code('SELECT DISTINCT caliber FROM ...')]],
    ['Top 10 brands by sales this year', [code('SELECT TOP 10 brand, SUM(extended) ...')]],
    ['Which items have the highest return rate?', ''],
  ], [4680, 4680]),
  h2('Rules'),
  bullet(bold('Column A'), txt(' must contain the natural-language question (required, must be non-empty)')),
  bullet(bold('Column B'), txt(' is the expected SQL (optional — used as a reference, not enforced or compared)')),
  bullet(bold('Header row'), txt(' is auto-detected: if the first cell of row 1 is '), code('natural_language_query'), txt(', '), code('question'), txt(', '), code('query'), txt(', or '), code('nl_query'), txt(', that row is treated as headers and skipped')),
  bullet(bold('Empty rows'), txt(' are silently skipped')),
  bullet(txt('Any '), bold('additional columns'), txt(' (C, D, …) are ignored')),
  h2('Tips'),
  bullet(txt('Use clear, business-friendly English (the LLM is trained on natural questions)')),
  bullet(txt('Avoid SQL jargon in column A — that’s not what the agent expects')),
  bullet(txt('Start each run with a small file (5–10 questions) to verify the client’s instance is healthy before unleashing 100+')),
);

// =============================================================================
// 7. Live progress page
// =============================================================================
content.push(
  h1('7. Understanding the live progress page'),
  dataTable([
    ['Element', 'Meaning'],
    [[bold('Configuration table')], 'Snapshot of exactly what you submitted — useful for re-creating the run later'],
    [[bold('Status badge')], 'queued (waiting for browser to start) → running → done / failed'],
    [[bold('Counters row')], 'PASS / PARTIAL / FAIL / TIMEOUT counts; "Done X / Y" totals completed'],
    [[bold('Progress bar')], 'Visual completion'],
    [[bold('Last 5 queries')], 'Most recent results — refreshes every 3 seconds'],
    [[bold('Event log')], 'Live tail of every action the runner takes; useful for debugging stuck runs'],
    [[bold('Open final report')], 'Appears only after the run completes; opens the full HTML deliverable'],
  ], [2800, 6560]),
  plainP(txt('The page '), bold('persists'), txt(' even if you close the browser — the runner keeps going in the background and you can return to the URL (e.g. from the Past runs list on the home page) at any time to check progress.')),
);

// =============================================================================
// 8. Final report
// =============================================================================
content.push(
  h1('8. Understanding the final report'),
  plainP(
    txt('After clicking '),
    bold('Open final report ↗'),
    txt(' (or navigating to '), code('runs/<job-id>/REPORT.html'),
    txt('), you’ll see a structured report with these sections:'),
  ),
  h2('8.1 — Executive summary'),
  plainP(txt('A grid of headline numbers:')),
  bullet(txt('Total queries')),
  bullet(txt('PASS / PARTIAL / FAIL / TIMEOUT counts')),
  bullet(txt('Average per-query duration')),
  bullet(txt('Maximum duration')),

  h2('8.2 — API health table'),
  dataTable([
    ['Endpoint', 'Captured', 'HTTP 2xx', 'Usable payload'],
    [[code('run-sql')], '45 / 55', '39 / 55', '38 / 55 (rows>0)'],
    [[code('generate-viz')], '33 / 55', '33 / 55', '33 / 55 (chart)'],
  ], [2700, 2200, 2200, 2260]),
  plainP(txt('This tells you at a glance:')),
  bullet(txt('How many queries even reached the SQL execution step')),
  bullet(txt('How many returned successful HTTP responses')),
  bullet(txt('How many returned actual data (not empty result sets)')),

  h2('8.3 — Failing queries / Partial / Timed-out queries'),
  plainP(txt('Three lists, with the failing reason next to each query. For example:')),
  quoteP(
    bold('q03 — What firearm brands are my top selling brands for this year?'),
    txt('\n⚠ columns differ between run-sql and generate-viz'),
    txt('\n⚠ run-sql returned 1 column(s) with empty/missing name (SQL aliasing bug)'),
  ),

  h2('8.4 — Per-query detail'),
  plainP(txt('For each of the queries, an expandable section containing:')),
  bullet(bold('run-sql row'), txt(': HTTP method, full URL, status, duration, returned columns, row count')),
  bullet(bold('generate-viz row'), txt(': HTTP method, full URL, status, duration, chart type, x/y axes')),
  bullet(bold('Columns synced'), txt(' indicator (true/false/null)')),
  bullet(bold('Fail / warn reasons')),
  bullet(bold('run-sql request body'), txt(' (collapsed) — what was sent')),
  bullet(bold('run-sql response body'), txt(' (collapsed) — what came back')),
  bullet(bold('generate-viz request body'), txt(' (collapsed)')),
  bullet(bold('generate-viz response body'), txt(' (collapsed)')),
  bullet(bold('Screenshots'), txt(' (collapsed) — input, results table, chart')),
  plainP(txt('You can search the report (Cmd+F / Ctrl+F) to find specific queries.')),
);

// =============================================================================
// 9. Result statuses
// =============================================================================
content.push(
  h1('9. Result statuses explained'),
  dataTable([
    ['Badge', 'Color', 'Meaning'],
    [[bold('PASS')], 'Green', 'Everything green: run-sql returned 2xx with rows; if a chart was expected, generate-viz returned a valid payload; columns synced'],
    [[bold('PARTIAL')], 'Yellow', 'Data was captured but with at least one warning. Common causes: run-sql returned no rows; column names differ between run-sql output and generate-viz axes; SQL had unaliased columns producing empty-string column names'],
    [[bold('FAIL')], 'Red', 'Hard failure. run-sql was missing entirely OR returned an HTTP error (4xx/5xx); or generate-viz was expected but returned an HTTP error'],
    [[bold('TIMEOUT')], 'Purple', 'The configured per-query budget was exceeded. The runner reloads the SQL Agent page automatically and proceeds to the next question. The generate-sql LLM service likely returned HTTP 500 or hung.'],
  ], [1800, 1500, 6060]),
  quoteP(
    bold('Note on PARTIAL: '),
    txt('A PARTIAL is '),
    txt('not', { italics: true }),
    txt(' a tool failure — it means the Skylar IQ SQL Agent returned data, but with a quality issue worth investigating. The "columns differ" warning, in particular, is usually a real bug in the agent’s SQL generation.'),
  ),
);

// =============================================================================
// 10. Configuration
// =============================================================================
content.push(
  h1('10. Configuration options'),
  dataTable([
    ['Option', 'Default', 'When to change'],
    [[bold('Login URL')], '(you supply)', 'Always — different for each client'],
    [[bold('Username / Password')], '(you supply)', 'Always'],
    [[bold('Machine ID')], '100', 'If your client’s Celerant install uses a different MID. Leave blank to skip the localStorage step entirely.'],
    [[bold('SQL Agent path')], '(default route)', 'Rarely. Only if a tenant has a customised SPA route.'],
    [[bold('run-sql timeout')], '120000 (2 min)', 'Increase to 300000 (5 min) or 600000 (10 min) if your client’s LLM is slow'],
    [[bold('generate-viz timeout')], '120000 (2 min)', 'Same — slow chart generation = bump this'],
  ], [2400, 2400, 4560]),
);

// =============================================================================
// 11. CLI
// =============================================================================
content.push(
  h1('11. Command-line mode (advanced)'),
  plainP(txt('If you’d rather skip the web UI (e.g. for CI/CD or scripted batch runs):')),
  codeBlock(
    "python3 -m app.runner \\\n" +
    "  --login-url 'https://client-host:8443/backoffice/?mid=100' \\\n" +
    "  --username myuser \\\n" +
    "  --password 'mypass' \\\n" +
    "  --questions /absolute/path/to/questions.xlsx \\\n" +
    "  --output-dir runs/my-run-2026-04-29 \\\n" +
    "  --machine-id 100 \\\n" +
    "  --run-sql-timeout 120000 \\\n" +
    "  --gen-viz-timeout 120000"
  ),
  plainP(txt('After the run completes, generate the report:')),
  codeBlock('python3 -m app.report --job-dir runs/my-run-2026-04-29'),
  plainP(txt('This writes '), code('REPORT.html'), txt(', '), code('REPORT.md'), txt(', '), code('SUMMARY.json'), txt(' into that folder.')),
  quoteP(
    bold('Tip for CI: '),
    txt('Pass '), code('--no-headless'), txt(' if you want to watch the browser; omit for fully headless (default).'),
  ),
);

// =============================================================================
// 12. Sharing reports
// =============================================================================
content.push(
  h1('12. Sharing reports with stakeholders'),
  plainP(txt('Every run creates a folder '), code('runs/<job-id>/'), txt(' that is '), bold('fully self-contained'), txt(':')),
  codeBlock(
    "runs/<job-id>/\n" +
    "├── REPORT.html         ← THE deliverable — open in any browser\n" +
    "├── REPORT.md           ← Markdown copy\n" +
    "├── SUMMARY.json        ← Top-level stats only\n" +
    "├── job.json            ← Original config (so the run is reproducible)\n" +
    "├── questions.xlsx      ← The input file\n" +
    "├── events.log          ← Every action the runner took\n" +
    "├── all_results.json    ← Aggregate of every per-query record\n" +
    "├── results/            ← One JSON per query\n" +
    "├── network_logs/       ← Raw API call dumps\n" +
    "└── screenshots/        ← All captured screenshots"
  ),
  plainP(txt('To share:')),
  bullet(bold('Just the report'), txt(' → email '), code('REPORT.html'), txt('. It works offline.')),
  bullet(bold('Report + screenshots'), txt(' → zip the whole '), code('runs/<job-id>/'), txt(' folder')),
  bullet(bold('Just summary stats'), txt(' → send '), code('SUMMARY.json')),
);

// =============================================================================
// 13. Troubleshooting
// =============================================================================
content.push(
  h1('13. Troubleshooting'),

  h2('"Login failed: Machine ID is empty"'),
  plainP(txt('The Celerant server requires the '), code('machineid'), txt(' parameter. Two fixes:')),
  bullet(txt('Make sure your '), bold('Login URL includes ?mid=100'), txt(' (or whatever value the client uses)')),
  bullet(txt('Or fill in the '), bold('Machine ID'), txt(' field on the form')),
  plainP(txt('If both are set correctly and you still see this, the client may have a custom Machine ID — check with the Celerant admin.')),

  h2('Lots of TIMEOUTs (everything times out at exactly 2 minutes)'),
  plainP(txt('Two possibilities:')),
  bullet(bold('The client’s LLM service is slow.'), txt(' Bump both timeouts to 600000 (10 minutes) and re-run.')),
  bullet(bold('The LLM service is broken / returning 500.'), txt(' Check the run’s event log for '), code('generate-sql HTTP 500'), txt(' — if you see this, the service-side LLM is errored. Wait an hour, retry. This is a service-side issue, not a tool issue.')),

  h2('"jQuery submit handler not bound" (login times out)'),
  plainP(txt('The Celerant login page failed to load its JavaScript. Open the login URL manually in a browser to verify connectivity. If it loads in a browser but not the tool, check:')),
  bullet(txt('Are you behind a corporate proxy? Set '), code('HTTPS_PROXY'), txt(' env var before launching')),
  bullet(txt('Is the SSL certificate self-signed? The tool ignores cert errors by default; if that’s not working, file a bug')),

  h2('Web UI says "Address already in use" on launch'),
  plainP(txt('Another process has port 5050 occupied. Either:')),
  bullet(txt('Stop the other process: '), code('lsof -i :5050'), txt(' to see what’s using it, then kill it')),
  bullet(txt('Use a different port: '), code('python3 -m app.server --port 5051')),

  h2('Port 5050 not opening in browser'),
  plainP(txt('Manually navigate to '), code('http://127.0.0.1:5050/'), txt(' (sometimes auto-open is blocked).')),

  h2('Excel file rejected: "no usable rows found"'),
  bullet(txt('Make sure column '), bold('A'), txt(' has the questions (not column B or C)')),
  bullet(txt('Make sure rows aren’t all in column B')),
  bullet(txt('Check the file isn’t password-protected')),
  bullet(txt('Try saving as a fresh '), code('.xlsx'), txt(' (not '), code('.xls'), txt(' or '), code('.csv'), txt(')')),

  h2('Report shows with_chart=0 for all queries'),
  plainP(txt('The chart-payload heuristic doesn’t recognise the response format. Inspect a single query:')),
  codeBlock('cat runs/<job-id>/results/q01.json | python3 -m json.tool | less'),
  plainP(txt('If the response shape is different from '), code('responseBody.data.visualizations[0]'), txt(', file a bug or update '), code('inspect_chart_payload()'), txt(' in '), code('app/runner.py'), txt('.')),
);

// =============================================================================
// 14. FAQ
// =============================================================================
content.push(
  h1('14. FAQ'),

  h2('How long does a typical run take?'),
  plainP(txt('For 50 questions with a healthy LLM service:')),
  bullet(bold('Best case'), txt(' (all fast queries): 10 minutes')),
  bullet(bold('Average mix'), txt(': 30–60 minutes')),
  bullet(bold('Worst case'), txt(' (every query hits the 2-min timeout): ~110 minutes (because timeouts skip)')),

  h2('Can I run multiple jobs in parallel?'),
  plainP(txt('Yes — the web UI supports it. Each job runs in its own thread with its own browser context. However, hitting the same Skylar IQ instance with multiple parallel sessions may cause the LLM to rate-limit you. Recommend max 2–3 parallel.')),

  h2('Can I stop a run mid-flight?'),
  plainP(txt('The web UI doesn’t have a stop button yet. To stop:')),
  codeBlock('# Find the runner process\nps -ef | grep "app.runner\\|app.server"\n# Kill it\nkill <pid>'),
  plainP(txt('The per-query JSONs already written to '), code('runs/<job-id>/results/'), txt(' will be preserved.')),

  h2('Where are the credentials stored?'),
  plainP(txt('Credentials are submitted via the form, stored only in:')),
  bullet(txt('The current run’s '), code('job.json'), txt(' file (containing username only — passwords are NOT persisted)')),
  bullet(txt('Memory while the runner is active')),
  plainP(txt('They are not logged. If you want extra safety, run on an isolated machine and '), code('rm -rf runs/'), txt(' after testing.')),

  h2('Does it support headed mode (visible browser)?'),
  plainP(txt('CLI yes — pass '), code('--no-headless'), txt('. Web UI currently always runs headless to keep the server portable.')),

  h2('Can I retry just the failed queries?'),
  plainP(txt('Not yet. You’d have to:')),
  bullet(txt('Open the original '), code('runs/<job-id>/questions.xlsx'), txt(' and the '), code('SUMMARY.json')),
  bullet(txt('Build a new '), code('.xlsx'), txt(' with only the failed/timed-out queries')),
  bullet(txt('Submit a new run')),
);

// =============================================================================
// 15. Architecture
// =============================================================================
content.push(
  h1('15. How the tool works (architecture)'),
  codeBlock(
    "┌─────────────────────┐    POST /jobs      ┌──────────────────────────┐\n" +
    "│ Web UI              │──────────────────▶ │ Flask backend (server.py)│\n" +
    "│ (browser form)      │                    │  - parses .xlsx          │\n" +
    "│                     │◀── SSE events ────│  - spawns runner thread  │\n" +
    "└─────────────────────┘                    │  - serves report         │\n" +
    "                                           └──────────┬───────────────┘\n" +
    "                                                      │ run(cfg)\n" +
    "                                                      ▼\n" +
    "                              ┌────────────────────────────────────────┐\n" +
    "                              │ app/runner.py                          │\n" +
    "                              │  - launches headless Chromium          │\n" +
    "                              │  - performs login + nav                │\n" +
    "                              │  - for each question:                  │\n" +
    "                              │      type, click send, expect_response │\n" +
    "                              │      capture run-sql, click viz,       │\n" +
    "                              │      expect_response capture viz       │\n" +
    "                              │      take screenshots                  │\n" +
    "                              │      validate + save qNN.json          │\n" +
    "                              └────────────────┬───────────────────────┘\n" +
    "                                               │ writes\n" +
    "                                               ▼\n" +
    "                              ┌────────────────────────────────────────┐\n" +
    "                              │ runs/<job-id>/                         │\n" +
    "                              │   results/qNN.json                     │\n" +
    "                              │   screenshots/                         │\n" +
    "                              │   network_logs/                        │\n" +
    "                              │   events.log                           │\n" +
    "                              │   all_results.json                     │\n" +
    "                              └────────────────┬───────────────────────┘\n" +
    "                                               │ feeds\n" +
    "                                               ▼\n" +
    "                              ┌────────────────────────────────────────┐\n" +
    "                              │ app/report.py                          │\n" +
    "                              │   REPORT.html / REPORT.md /            │\n" +
    "                              │   SUMMARY.json                         │\n" +
    "                              └────────────────────────────────────────┘"
  ),
  h2('Key design decisions'),
  dataTable([
    ['Decision', 'Rationale'],
    [[bold('Playwright over Selenium')], 'Faster, more reliable, has built-in expect_response for waiting on specific API calls (which Selenium doesn’t)'],
    [[bold('Event-driven expect_response (not polling)')], 'Earlier polling-based wait missed responses by milliseconds, leading to false TIMEOUT classifications. Event-driven approach catches every response immediately.'],
    [[bold('2-minute per-query budget with auto-recovery')], 'The Skylar IQ LLM has high variance (5s–300s+). A bounded budget keeps total runtime predictable while still capturing slow-but-completing queries. After a timeout, the SQL Agent page is reloaded so the next query has a clean slate.'],
    [[bold('Per-job folder layout')], 'Each run is fully self-contained — easy to zip/share/archive.'],
    [[bold('Flask + SSE for live progress')], 'Lightweight, no WebSocket complexity, works with curl/browser equally.'],
    [[bold('Excel via openpyxl')], 'Most QA teams maintain test cases in Excel. Native .xlsx support avoids a CSV-conversion step.'],
  ], [3000, 6360]),

  h2('Project layout'),
  codeBlock(
    ".\n" +
    "├── app/                     ← the tool (importable Python package)\n" +
    "│   ├── runner.py            Playwright-driven QA runner\n" +
    "│   ├── report.py            HTML / MD / JSON report generator\n" +
    "│   ├── excel_reader.py      .xlsx → list of questions\n" +
    "│   ├── server.py            Flask web UI\n" +
    "│   ├── templates/index.html Landing form\n" +
    "│   ├── templates/job.html   Live progress page\n" +
    "│   └── static/style.css\n" +
    "├── runs/                    ← per-job output folders (created at runtime, gitignored)\n" +
    "├── data/sample_questions.xlsx  ← ships with repo, 5 questions for first-run test\n" +
    "├── tests/legacy/            ← reference scripts from the original 55-question Skylar IQ run\n" +
    "├── requirements.txt\n" +
    "├── run-server.sh            ← one-command launcher\n" +
    "├── README.md                ← short developer docs\n" +
    "├── USER_GUIDE.md            ← this file (markdown source)\n" +
    "└── .gitignore"
  ),
);

// --- Footer ---
content.push(
  h1('Need help?'),
  plainP(txt('For bugs, feature requests, or questions: contact the repo owner.')),
);

// =============================================================================
// Build the document
// =============================================================================
const doc = new Document({
  creator: 'Skylar IQ QA Tool',
  title: 'Skylar IQ QA Tool — User Documentation',
  description: 'End-to-end install + usage guide for the Skylar IQ SQL Agent QA automation tool',
  styles: {
    default: {
      document: { run: { font: THEME.bodyFont, size: 22 } },
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: THEME.bodyFont, color: THEME.heading },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: THEME.bodyFont, color: THEME.subheading },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: THEME.bodyFont, color: THEME.subheading },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [
          {
            level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE.W, height: PAGE.H },
        margin: { top: PAGE.MARGIN, right: PAGE.MARGIN, bottom: PAGE.MARGIN, left: PAGE.MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({ text: 'Skylar IQ QA Tool — User Documentation', italics: true, size: 18, color: '6b7280' })],
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: THEME.borderGrey, space: 4 } },
          }),
        ],
      }),
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: 'Page ', size: 18, color: '6b7280' }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '6b7280' }),
              new TextRun({ text: ' of ', size: 18, color: '6b7280' }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: '6b7280' }),
            ],
          }),
        ],
      }),
    },
    children: content,
  }],
});

// --- Serialize ---
const OUT = '/Users/farhanmemon/Desktop/automationtesting/Skylar_IQ_QA_Tool_User_Guide.docx';
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`Wrote ${OUT} (${buf.length.toLocaleString()} bytes)`);
});
