"""CLI: python -m eval.run_eval --tasks T1_form_fill,T2_pagination_extract"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loop import run
from tasks.specs import TASKS, get
from eval.scorer import score, score_to_dict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="all", help="comma-separated task ids or 'all'")
    ap.add_argument("--headless", type=int, default=1)
    ap.add_argument("--include-stubs", action="store_true")
    ap.add_argument("--out-csv", default="scorecard.csv")
    ap.add_argument("--out-json", default="scorecard.json")
    args = ap.parse_args()

    if args.tasks == "all":
        specs = [t for t in TASKS if args.include_stubs or not t.stub]
    else:
        specs = [get(tid) for tid in args.tasks.split(",")]
        specs = [s for s in specs if s]

    rows = []
    for spec in specs:
        print(f"[run] {spec.id}: {spec.title}")
        result = run(spec.id, spec.prompt, max_steps=spec.max_steps,
                     headless=bool(args.headless), allow_ask=spec.allow_ask)
        sc = score(result, spec)
        rows.append(score_to_dict(sc))
        print(f"       overall={sc.overall}  completion={sc.completion}  "
              f"steps={sc.steps}  cost_tokens={sc.input_tokens}+{sc.output_tokens}")

    if rows:
        with open(args.out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        with open(args.out_json, "w") as f:
            json.dump(rows, f, indent=2)
        print(f"\nWrote {args.out_csv} and {args.out_json} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
