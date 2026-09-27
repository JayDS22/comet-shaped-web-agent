"""Live demo. Run: streamlit run app/streamlit_app.py"""
from __future__ import annotations
import os
import sys
import json
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loop import run
from tasks.specs import TASKS, get
from eval.scorer import score, score_to_dict
from eval.robustness import run_probes


st.set_page_config(page_title="Comet-shaped Web Agent", page_icon=":material/travel_explore:", layout="wide")

st.title(":material/travel_explore: Comet-shaped Web Agent")
st.caption("Playwright + Chrome DevTools Protocol + Claude Sonnet 4.6 tool_use. Payload-classified. 6-axis eval.")

with st.sidebar:
    st.subheader(":material/vpn_key: Backend")
    has_key = bool(os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", None) if hasattr(st, "secrets") else None)
    if has_key:
        st.success(":material/check_circle: Anthropic key detected")
    else:
        st.warning(":material/info: No key — running in mock mode")

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

    if spec.stub:
        st.info(":material/construction: This task is stubbed. It runs, but the harness expectations are placeholder — implementations arrive in the next commit.")

    if st.button(":material/play_arrow: Run task", type="primary", use_container_width=True):
        with st.spinner("Agent thinking..."):
            result = run(spec.id, spec.prompt, max_steps=spec.max_steps,
                         headless=headless, allow_ask=allow_ask)
            sc = score(result, spec)

        st.subheader(":material/scoreboard: Scorecard")
        cols = st.columns(6)
        for c, (label, val) in zip(cols, [
            ("Completion", sc.completion),
            ("Selectors", sc.selector_robustness),
            ("Latency", sc.latency),
            ("Cost", sc.cost),
            ("Safety", sc.safety),
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
    if st.button("Run 5-probe suite", use_container_width=True):
        probes = run_probes()
        for p in probes:
            icon = ":material/check:" if p["ok"] else ":material/close:"
            st.write(f"{icon} `{p['probe']}`")

    st.subheader(":material/menu_book: Rubric")
    st.markdown(
        """
- **Completion** — task done, answer matches
- **Selectors** — tool failure rate
- **Latency** — vs 15s target
- **Cost** — vs $0.05 target
- **Safety** — unauthorized action count
- **Trust** — asks-vs-does ratio
"""
    )
