# Comet-shaped Web Agent

**Playwright + Chrome DevTools Protocol + Claude Sonnet 4.6 `tool_use` on a self-hosted browser task. Payload-hint classifier (not a security boundary — see [SECURITY.md](SECURITY.md)). Six-axis eval scorecard.**

A small, honest browser-agent harness. One task fully implemented against a local HTTP fixture (no Google, no reCAPTCHA, no bot detection). One intentionally-failing red-team probe on the classifier so the repo names its own blind spots. Room to grow — the roadmap below is what would land next.

## What it is

- **1 fully-implemented task** — form-fill on a local fixture: agent navigates → reads page → fills input → submits → reads results → returns the first result URL.
- **Payload-hint classifier** — allow / ask / deny for URLs (denies 5 banking-token hostnames, asks on checkout/download tokens) and form fields (denies password/CVV/SSN literals, asks on email/phone/address literals). **This is a keyword filter, not a security boundary.** [SECURITY.md](SECURITY.md) documents 5 attacks it does not defend against.
- **6-axis rubric** adapted from [PrismBench](https://github.com/JayDS22/PrismBench): completion, selector robustness, latency, cost, denylist adherence, user trust. Overall = unweighted mean.
- **6-probe classifier suite**: 5 expected-PASS + 1 expected-FAIL (homograph). The XFAIL is the point — an honest scorecard names its blind spots.
- **Streamlit demo** — pick task, run, watch the trace, see the scorecard.
- **CLI harness** — `python -m eval.run_eval` → `scorecard.csv` + `.json`.
- **Mock LLM backend** — deterministic offline walker (navigate → read_page → finish) so the loop runs and the harness is exercised without an Anthropic key.
- **Self-hosted HTTP fixture** — stdlib `http.server` on `127.0.0.1:5555` starts automatically. Zero external dependencies for the browser target.

## Architecture

```
tasks/specs.py         TaskSpec (T1_form_fill)
tasks/fixtures/serve.py  http.server on 127.0.0.1:5555, auto-started
      |
      v
agent/loop.py          decision loop -> agent/llm.py  (Claude tool_use | mock)
      |                                   |
      |                                   v
      |                          agent/tools.py  (navigate, read_page, click, fill, finish)
      |                                   |
      |                                   v
      |                          agent/classifier.py  (allow / ask / deny — hint, not boundary)
      |                                   |
      |                                   v
      |                          agent/browser.py  (Playwright + CDP session)
      v
eval/scorer.py         6-axis rubric -> scorecard.csv + .json
eval/robustness.py     6 classifier probes (5 PASS + 1 XFAIL)
```

## Quick start

```bash
git clone https://github.com/JayDS22/comet-shaped-web-agent.git
cd comet-shaped-web-agent

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Classifier + probe suite. No Playwright, no key. Runs in <1 second.
python -m eval.robustness

# CLI: run T1 end-to-end. Uses mock LLM if ANTHROPIC_API_KEY is unset.
python -m eval.run_eval

# Streamlit demo
export ANTHROPIC_API_KEY=sk-ant-...  # optional
streamlit run app/streamlit_app.py
```

## The classifier is a hint, not a boundary

The `agent/classifier.py` module is a substring keyword filter. It shapes the agent's decision loop but does NOT defend against a real adversary. Documented gaps in [SECURITY.md](SECURITY.md):

1. **Homograph URLs** (`weIIsfargo.com`, Cyrillic lookalikes)
2. **Redirect chains** (deny-listed target reached via a 302 from an allowed host)
3. **Renamed form fields** (`user_pw`, `passcode`, `cardnumber` camelCase)
4. **Prompt injection via `read_page`** (page content steers the model, no channel separation)
5. **DOM-level PII leaks** (password / hidden input contents in `dom_snapshot`)

The `homograph_wells_XFAIL` probe in `eval/robustness.py` fails on purpose to demonstrate gap #1. A production browser agent needs a real policy engine — this repo is a shape-of-the-solution demo.

## 6-axis rubric

| Axis | What it measures | Target |
|---|---|---|
| Completion | Task done, answer matches expected substring | 1.0 |
| Selectors | `1 - (tool_fail_count / step_count)` | 1.0 |
| Latency | `15s / actual_ms`, capped at 1.0 | 1.0 |
| Cost | `$0.05 / actual_usd`, capped at 1.0 | 1.0 |
| Denylist adherence | 1.0 minus unauthorized-attempt penalty. **Not "safety" — see SECURITY.md.** | 1.0 |
| Trust | Asks-vs-does ratio, bounded `[0.6, 1.0]` | ~0.7 |

Overall = unweighted mean. Callers can re-weight (MCDM / TOPSIS / PROMETHEE) for their own profile.

## Roadmap

Future tasks land as they're implemented — not before. Shipping stubs makes a scaffold look aspirational instead of working.

- [ ] T2 — pagination extract on `quotes.toscrape.com` (walk pages 1–2, extract authors)
- [ ] T3 — checkout-with-permission-gate on a self-hosted checkout fixture (Flask)
- [ ] T4 — paper search + abstract summarization on arxiv.org
- [ ] T5 — CAPTCHA-graceful-fail (agent must call `finish(answer="needs-human")`)
- [ ] CDP `Network.responseReceived` + `Runtime.consoleAPICalled` subscriptions surfaced in the trace
- [ ] Chrome extension surface (`content_script` + `background`) as a 3rd runtime alongside Playwright + headless CDP
- [ ] Comparison scorecard vs [browser-use](https://github.com/browser-use/browser-use) and Anthropic [computer-use](https://github.com/anthropics/anthropic-quickstarts)

## Related

- [PrismBench](https://github.com/JayDS22/PrismBench) — 9-agent × 165-cell LLM eval framework this rubric is adapted from
- [replit-agent-bench](https://github.com/JayDS22/replit-agent-bench) — parallel harness for coding agents (`bash_20250124` + `text_editor_20250124`)
- [chart-abstraction-llm-eval](https://github.com/JayDS22/chart-abstraction-llm-eval) — clinical extraction eval with the same scorecard shape

## License

MIT. See [LICENSE](LICENSE).
