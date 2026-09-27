"""CLI: python -m eval.run_eval --tasks T1_form_fill"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loop import run
from tasks.specs import TASKS, get
from tasks.fixtures.serve import ensure as ensure_fixtures
from eval.scorer import score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="all", help="comma-separated task ids or 'all'")
    ap.add_argument("--headless", type=int, default=1)
    ap.add_argument("--out-csv", default="scorecard.csv")
    ap.add_argument("--out-json", default="scorecard.json")
    args = ap.parse_args()

    if args.tasks == "all":
        specs = list(TASKS)
    else:
        requested = [t.strip() for t in args.tasks.split(",") if t.strip()]
        missing = [t for t in requested if get(t) is None]
        if missing:
            print(f"error: unknown task id(s): {', '.join(missing)}", file=sys.stderr)
            print(f"       known: {', '.join(t.id for t in TASKS)}", file=sys.stderr)
            return 2
        specs = [get(t) for t in requested]

    if not specs:
        print("error: no tasks to run", file=sys.stderr)
        return 2

    ensure_fixtures()

    rows = []
    for spec in specs:
        print(f"[run] {spec.id}: {spec.title}")
        result = run(spec.id, spec.prompt, max_steps=spec.max_steps,
                     headless=bool(args.headless), allow_ask=spec.allow_ask)
        sc = score(result, spec)
        rows.append(asdict(sc))
        print(f"       overall={sc.overall}  completion={sc.completion}  "
              f"steps={sc.steps}  cost_tokens={sc.input_tokens}+{sc.output_tokens}")

    with open(args.out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    with open(args.out_json, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"\nWrote {args.out_csv} and {args.out_json} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
