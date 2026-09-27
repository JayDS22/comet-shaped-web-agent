"""Side-by-side comparison: this harness vs browser-use on the same task.

Reads T1 from tasks.specs, runs it via both harnesses, emits a comparison
CSV with per-axis scores. This is the "baselines" evidence a serious eval
harness needs — a rubric without a baseline is a rubric applied to nothing.

Prerequisites:
    pip install browser-use    # not in requirements.txt to keep the core lean
    export ANTHROPIC_API_KEY=sk-ant-...

Run:
    python -m eval.compare --task T1_form_fill --headless 1

Output: comparison.csv with columns per (task_id, harness, axis).
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loop import run as run_ours
from tasks.specs import get
from tasks.fixtures.serve import ensure as ensure_fixtures
from eval.scorer import score


def _run_ours(task_id: str, headless: bool) -> dict:
    spec = get(task_id)
    t0 = time.time()
    result = run_ours(spec.id, spec.prompt, max_steps=spec.max_steps,
                      headless=headless, allow_ask=spec.allow_ask)
    sc = score(result, spec)
    row = asdict(sc)
    row["harness"] = "comet-shaped-web-agent"
    row["wall_clock_s"] = round(time.time() - t0, 2)
    return row


def _run_browser_use(task_id: str, headless: bool) -> dict:
    """browser-use harness. Returns a scorecard-shaped dict for CSV alignment.

    We measure the subset of axes browser-use exposes cleanly (completion,
    latency, cost). Selector robustness + denylist adherence are marked
    n/a because browser-use has its own state machine and does not expose
    per-tool failure counts in the same way.
    """
    try:
        from browser_use import Agent
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        return {
            "task_id": task_id, "harness": "browser-use",
            "completion": None, "selector_robustness": None, "latency": None,
            "cost": None, "denylist_adherence": None, "user_trust": None,
            "overall": None, "raw_answer": "",
            "steps": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0,
            "classifier_asks": 0, "classifier_denies": 0, "wall_clock_s": 0,
            "note": "browser-use not installed; pip install browser-use",
        }

    spec = get(task_id)
    import asyncio
    llm = ChatAnthropic(model_name="claude-sonnet-4-5-20250929", max_tokens=1024)
    agent = Agent(task=spec.prompt, llm=llm)
    t0 = time.time()
    try:
        history = asyncio.run(agent.run(max_steps=spec.max_steps))
        wall = round(time.time() - t0, 2)
        final = history.final_result() if hasattr(history, "final_result") else str(history)
        completion = 1.0 if spec.expected_answer and spec.expected_answer.lower() in str(final).lower() else 0.5
        return {
            "task_id": task_id, "harness": "browser-use",
            "completion": completion, "selector_robustness": None,
            "latency": max(0.0, min(1.0, 15000 / (wall * 1000 + 1))),
            "cost": None, "denylist_adherence": None, "user_trust": None,
            "overall": None, "raw_answer": str(final)[:200],
            "steps": len(history.history) if hasattr(history, "history") else 0,
            "input_tokens": 0, "output_tokens": 0, "latency_ms": int(wall * 1000),
            "classifier_asks": 0, "classifier_denies": 0, "wall_clock_s": wall,
            "note": "no classifier/denylist axis exposed by browser-use",
        }
    except Exception as e:
        return {
            "task_id": task_id, "harness": "browser-use",
            "completion": 0.0, "selector_robustness": None, "latency": None,
            "cost": None, "denylist_adherence": None, "user_trust": None,
            "overall": None, "raw_answer": "",
            "steps": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0,
            "classifier_asks": 0, "classifier_denies": 0, "wall_clock_s": 0,
            "note": f"error: {e}",
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="T1_form_fill")
    ap.add_argument("--headless", type=int, default=1)
    ap.add_argument("--out", default="comparison.csv")
    args = ap.parse_args()

    ensure_fixtures()
    rows = [_run_ours(args.task, bool(args.headless)),
            _run_browser_use(args.task, bool(args.headless))]

    # Union of keys across rows
    keys = sorted({k for r in rows for k in r.keys()})
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {args.out}: {len(rows)} rows across harnesses.")
    for r in rows:
        print(f"  {r['harness']:24s}  completion={r.get('completion')}  "
              f"wall={r.get('wall_clock_s')}s  steps={r.get('steps')}  "
              f"note={r.get('note', '-')}")


if __name__ == "__main__":
    main()
