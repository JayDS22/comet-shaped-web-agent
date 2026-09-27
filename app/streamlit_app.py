"""Live demo. Run: streamlit run app/streamlit_app.py"""
from __future__ import annotations
import os
import sys
import json
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loop import run
from agent.browser import BrowserUnavailable
from tasks.specs import TASKS, get
from tasks.fixtures.serve import ensure as ensure_fixtures
from eval.scorer import score
from eval.robustness import run_probes

ensure_fixtures()

st.set_page_config(page_title="Comet-shaped Web Agent", page_icon=":material/travel_explore:", layout="wide")

st.title(":material/travel_explore: Comet-shaped Web Agent")
st.caption("Playwright + Chrome DevTools Protocol + Claude Sonnet 4.6 tool_use. Payload-classified. 6-axis eval.")

with st.sidebar:
    st.subheader(":material/vpn_key: Backend")
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    if has_key:
        st.success(":material/check_circle: Anthropic key detected")
    else:
        st.warning(":material/info: No key - running in mock mode")

    st.subheader(":material/task_alt: Task")
    task_ids = [t.id for t in TASKS]
    task_id = st.selectbox("Pick a task", task_ids, index=0)

    st.subheader(":material/tune: Controls")
    headless = st.toggle("Headless browser", value=True)
    allow_ask = st.toggle("Auto-approve ASK", value=False,
                          help="If off, the classifier's ASK verdicts halt the agent.")

col1, col2 = st.columns([2, 1])

with col1:
    spec = get(task_id)
    st.markdown(f"**{spec.title}**")
    st.code(spec.prompt, language="text")

    if st.button(":material/play_arrow: Run task", type="primary", use_container_width=True):
        try:
            with st.spinner("Agent thinking..."):
                result = run(spec.id, spec.prompt, max_steps=spec.max_steps,
                             headless=headless, allow_ask=allow_ask)
                sc = score(result, spec)
        except BrowserUnavailable as e:
            st.error(
                ":material/warning: **Chromium is not available in this environment.**\n\n"
                f"Details: `{e}`\n\n"
                "The classifier + probe suite still work below. For a full "
                "task-run demo, deploy this repo via the included `Dockerfile` "
                "(the base image `mcr.microsoft.com/playwright/python:v1.47.0-jammy` "
                "ships Chromium) on **Fly.io, Render, or Railway**. "
                "Streamlit Community Cloud does not ship Chromium and Playwright's "
                "post-install step is skipped there."
            )
            st.stop()

        st.subheader(":material/scoreboard: Scorecard")
        cols = st.columns(6)
        for c, (label, val) in zip(cols, [
            ("Completion", sc.completion),
            ("Selectors", sc.selector_robustness),
            ("Latency", sc.latency),
            ("Cost", sc.cost),
            ("Denylist", sc.denylist_adherence),
            ("Trust", sc.user_trust),
        ]):
            c.metric(label, f"{val:.2f}")
        st.metric(":material/summarize: Overall", f"{sc.overall:.3f}")

        st.subheader(":material/route: Trace")
        for i, step in enumerate(result.trace):
            icon = ":material/check:" if step.get("ok") else ":material/error:"
            with st.expander(f"{icon} step {i}: {step['tool']}"):
                st.json({"input": step["input"], "result": step["result"]})

        if result.error:
            st.error(f"Runtime error: {result.error}")

with col2:
    st.subheader(":material/security: Classifier Probes")
    st.caption("5 expected-PASS + 1 intentional XFAIL. See SECURITY.md.")
    if st.button("Run probe suite", use_container_width=True):
        for p in run_probes():
            icon = {"PASS": ":material/check:",
                    "XFAIL": ":material/warning:",
                    "FAIL": ":material/close:",
                    "UNEXPECTED_PASS": ":material/help:"}.get(p["status"], ":material/help:")
            st.write(f"{icon} `{p['probe']}` — {p['status']}")

    st.subheader(":material/menu_book: Rubric")
    st.markdown(
        """
- **Completion** — task done, answer matches
- **Selectors** — 1 - tool-failure rate
- **Latency** — vs 15s target
- **Cost** — vs $0.05 target
- **Denylist** — unauthorized-action attempts intercepted (NOT "safety" — see SECURITY.md)
- **Trust** — asks-vs-does ratio
"""
    )
