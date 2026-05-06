"""Generate a small sample.xlsx from the first 5 rows of the existing test_data.json
so new users have something to test with."""
import json
from pathlib import Path
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "test_data.json"
dst = ROOT / "data" / "sample_questions.xlsx"

rows = json.loads(src.read_text())[:5]

wb = Workbook()
ws = wb.active
ws.title = "questions"
ws.append(["natural_language_query", "expected_sql"])
for r in rows:
    ws.append([r["natural_language_query"], r.get("expected_sql", "")])
wb.save(str(dst))
print(f"Wrote {dst} with {len(rows)} rows")
