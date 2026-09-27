"""Claude Sonnet 4.6 client. Mock fallback so the loop runs without an API key."""
from __future__ import annotations
import os
import re
import time
import json
from dataclasses import dataclass


ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))


@dataclass
class LLMResponse:
    text: str
    tool_use: list[dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def call_claude(system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
    """Real Claude call with tool_use. Raises RuntimeError with the underlying message on failure."""
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError(f"anthropic sdk missing: {e}")

    client = Anthropic()
    t0 = time.time()
    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,
            messages=messages,
        )
    except Exception as e:
        raise RuntimeError(f"anthropic call failed: {e}")
    latency_ms = int((time.time() - t0) * 1000)

    text_parts = [b.text for b in resp.content if b.type == "text"]
    tool_uses = [
        {"id": b.id, "name": b.name, "input": b.input}
        for b in resp.content if b.type == "tool_use"
    ]
    return LLMResponse(
        text="\n".join(text_parts),
        tool_use=tool_uses,
        stop_reason=resp.stop_reason,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        latency_ms=latency_ms,
    )


_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            c = m["content"]
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return json.dumps(c)
    return ""


def call_mock(system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
    """Deterministic mock for offline runs. Walks: navigate -> read_page -> finish."""
    assistant_turns = sum(1 for m in messages if m["role"] == "assistant")

    if assistant_turns == 0:
        url_match = _URL_RE.search(_last_user_text(messages))
        if url_match:
            tool = {"id": "mock-1", "name": "navigate",
                    "input": {"url": url_match.group(0).rstrip(".,);]")}}
        else:
            tool = {"id": "mock-1", "name": "read_page", "input": {}}
    elif assistant_turns == 1:
        tool = {"id": "mock-2", "name": "read_page", "input": {}}
    else:
        tool = {"id": "mock-3", "name": "finish",
                "input": {"summary": "mock-done", "answer": "mock-answer"}}
    return LLMResponse(text="[mock]", tool_use=[tool], stop_reason="tool_use",
                       input_tokens=0, output_tokens=0, latency_ms=1)


def call(system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
    if os.getenv("ANTHROPIC_API_KEY"):
        return call_claude(system, messages, tools)
    return call_mock(system, messages, tools)
