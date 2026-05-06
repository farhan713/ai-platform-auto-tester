"""Parse the input CSV into a clean test_data.json for the runner."""
import csv
import json
from pathlib import Path

CSV_PATH = Path("/Users/farhanmemon/Downloads/Firearm_SQL_Testing_cleaned 1 1.csv")
OUT_PATH = Path(__file__).parent.parent / "data" / "test_data.json"


def main() -> None:
    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for idx, row in enumerate(reader, start=1):
            if not row or not row[0].strip():
                continue
            nl_query = row[0].strip()
            sql_query = row[1].strip() if len(row) > 1 else ""
            rows.append({
                "id": idx,
                "natural_language_query": nl_query,
                "expected_sql": sql_query,
            })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"Wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
