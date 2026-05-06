"""Re-run validate_query against the saved per-query JSON files.

Useful when the validation/heuristic logic in runner.py has been improved AFTER
a long run already completed — we don't want to re-run all 55 queries through
the slow LLM, we just want to re-grade the responses we already captured.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.runner import (  # noqa: E402
    QueryResult,
    CapturedCall,
    validate_query,
)

RESULTS_DIR = ROOT / "reports" / "results"
AGG = ROOT / "reports" / "all_results.json"


def _to_capt(d: dict | None) -> CapturedCall | None:
    if not d:
        return None
    # Filter to only fields CapturedCall accepts
    fields = {f for f in CapturedCall.__dataclass_fields__}
    return CapturedCall(**{k: v for k, v in d.items() if k in fields})


def main() -> None:
    files = sorted(RESULTS_DIR.glob("q*.json"))
    print(f"Re-validating {len(files)} per-query files...")
    out: list[dict] = []
    for f in files:
        d = json.loads(f.read_text())
        qr = QueryResult(
            id=d["id"],
            nl_query=d["nl_query"],
            expected_sql=d.get("expected_sql", ""),
            started_at=d["started_at"],
        )
        qr.finished_at = d.get("finished_at")
        qr.total_duration_ms = d.get("total_duration_ms")
        qr.screenshots = d.get("screenshots", [])
        qr.calls = [_to_capt(c) for c in d.get("calls", []) if c]
        qr.calls = [c for c in qr.calls if c]
        qr.run_sql_call = _to_capt(d.get("run_sql_call"))
        qr.generate_viz_call = _to_capt(d.get("generate_viz_call"))
        # Preserve the timed_out flag from the original run
        qr.timed_out = d.get("timed_out", False)
        # Preserve viz_button_present in validations seed
        old_v = d.get("validations") or {}
        if "viz_button_present" in old_v:
            qr.validations["viz_button_present"] = old_v["viz_button_present"]
        qr.notes = list(d.get("notes", []))
        qr.error = d.get("error")

        validate_query(qr)

        f.write_text(json.dumps(asdict(qr), indent=2, default=str))
        out.append(asdict(qr))
        print(f"  q{qr.id:02d}: {qr.overall_status}")

    AGG.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nWrote {AGG}")


if __name__ == "__main__":
    main()
