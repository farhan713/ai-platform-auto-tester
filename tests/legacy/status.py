"""Quick live-status snapshot of the in-progress run."""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "reports" / "results"
TOTAL_PLANNED = 55


def main() -> None:
    files = sorted(RESULTS.glob("q*.json")) if RESULTS.exists() else []
    print(f"Completed: {len(files)}/{TOTAL_PLANNED} ({100*len(files)//TOTAL_PLANNED if TOTAL_PLANNED else 0}%)")
    if not files:
        print("(no results yet)")
        return
    statuses = Counter()
    durations = []
    for f in files:
        try:
            r = json.loads(f.read_text())
            statuses[r.get("overall_status", "?")] += 1
            if r.get("total_duration_ms"):
                durations.append(r["total_duration_ms"])
        except Exception as e:
            print(f"warn: {f.name}: {e}")
    print(f"Status: {dict(statuses)}")
    if durations:
        print(f"Avg per-query duration: {int(sum(durations)/len(durations))/1000:.1f}s")
        print(f"Max: {max(durations)/1000:.1f}s, Min: {min(durations)/1000:.1f}s")
    print("\nLast 5 queries:")
    for f in files[-5:]:
        r = json.loads(f.read_text())
        rs = r.get("run_sql_call") or {}
        gv = r.get("generate_viz_call") or {}
        print(f"  q{r['id']:02d} [{r['overall_status']}] {r['nl_query'][:60]}")
        print(f"      run-sql HTTP {rs.get('status', '-')}, viz HTTP {gv.get('status', '-')}, dur={r.get('total_duration_ms','?')}ms")


if __name__ == "__main__":
    main()
