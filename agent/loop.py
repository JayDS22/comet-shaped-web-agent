"""Agent decision loop: model plans, tool call, page state feeds back."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import time

from agent.browser import launch, BrowserSession
from agent.llm import call, LLMResponse
from agent.tools import TOOL_SCHEMAS, dispatch


SYSTEM_PROMPT = """You are a careful browser-navigating agent.

You have five tools: navigate, read_page, click, fill, finish.

Rules:
- Route every action through the tools. Never invent DOM state.
- After navigate, always read_page before deciding what to click.
- If a tool returns `classifier: ask` or `classifier: deny`, STOP and explain to the user.
- Call `finish` with a short summary + extracted answer when the task is done.
- Prefer minimal steps. Ten tool calls is a lot.
"""


@dataclass
class RunResult:
    task_id: str
    steps: int
    finished: bool
    answer: str
    summary: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: int = 0
    classifier_decisions: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    cdp_events: list[dict] = field(default_factory=list)  # Network + Console captures
    error: Optional[str] = None


def run(task_id: str, user_prompt: str, max_steps: int = 10, headless: bool = True,
        allow_ask: bool = False) -> RunResult:
    session = launch(headless=headless)
    result = RunResult(task_id=task_id, steps=0, finished=False, answer="", summary="")
    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    try:
        for step in range(max_steps):
            result.steps = step + 1
            resp: LLMResponse = call(SYSTEM_PROMPT, messages, TOOL_SCHEMAS)
            result.total_input_tokens += resp.input_tokens
            result.total_output_tokens += resp.output_tokens
            result.total_latency_ms += resp.latency_ms

            if not resp.tool_use:
                result.summary = resp.text or "no tool call"
                break

            assistant_content = []
            if resp.text:
                assistant_content.append({"type": "text", "text": resp.text})
            for tu in resp.tool_use:
                assistant_content.append({"type": "tool_use", "id": tu["id"],
                                          "name": tu["name"], "input": tu["input"]})
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for tu in resp.tool_use:
                out = dispatch(session, tu["name"], tu["input"], allow_ask=allow_ask)
                # Drain CDP events accumulated during this tool call.
                for ev in session.drain_events():
                    result.cdp_events.append({
                        "step": step, "kind": ev.kind, "method": ev.method,
                        "summary": ev.summary, "raw": ev.raw,
                    })
                result.trace.append({"step": step, "tool": tu["name"], "input": tu["input"],
                                     "ok": out.get("ok"), "result": str(out.get("result"))[:200]})
                if "classifier" in out:
                    result.classifier_decisions.append(out["classifier"])
                if out.get("finish"):
                    result.finished = True
                    result.answer = out["result"].get("answer", "")
                    result.summary = out["result"].get("summary", "")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": str(out.get("result", "")),
                    "is_error": not out.get("ok", False),
                })
            messages.append({"role": "user", "content": tool_results})

            if result.finished:
                break
    except Exception as e:
        result.error = str(e)
    finally:
        session.close()

    return result
