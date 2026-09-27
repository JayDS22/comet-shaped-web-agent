"""Tools exposed to the model via Claude tool_use.

Every tool routes through the payload classifier before touching the page.
Every tool returns a small structured dict the model can act on.
"""
from __future__ import annotations
from typing import Any
from agent.browser import BrowserSession, dom_snapshot, clickable_map
from agent.classifier import classify_url, classify_field, Decision


TOOL_SCHEMAS = [
    {
        "name": "navigate",
        "description": "Load a URL. Routed through the URL payload classifier first.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "read_page",
        "description": "Return page text + a small clickable-elements map.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "click",
        "description": "Click an element by its idx from the clickable map.",
        "input_schema": {
            "type": "object",
            "properties": {"idx": {"type": "integer"}},
            "required": ["idx"],
        },
    },
    {
        "name": "fill",
        "description": "Fill an input by name/selector. Field classifier gates PII/secret fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["field", "value"],
        },
    },
    {
        "name": "finish",
        "description": "Signal task completion with a short summary and any extracted answer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "answer": {"type": "string"},
            },
            "required": ["summary"],
        },
    },
]


def dispatch(session: BrowserSession, name: str, args: dict, allow_ask: bool) -> dict[str, Any]:
    """Execute a tool call. Returns dict with keys: ok, result, classifier (optional)."""
    if name == "navigate":
        url = args["url"]
        v = classify_url(url)
        if v.decision == Decision.DENY:
            return {"ok": False, "result": f"DENIED: {v.reason}", "classifier": v.decision.value}
        if v.decision == Decision.ASK and not allow_ask:
            return {"ok": False, "result": f"ASK: {v.reason}. Set allow_ask=True to proceed.", "classifier": v.decision.value}
        session.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return {"ok": True, "result": f"loaded {url}", "classifier": v.decision.value}

    if name == "read_page":
        return {
            "ok": True,
            "result": {
                "text": dom_snapshot(session.page),
                "clickable": clickable_map(session.page),
                "url": session.page.url,
            },
        }

    if name == "click":
        idx = args["idx"]
        elements = clickable_map(session.page)
        if idx >= len(elements):
            return {"ok": False, "result": f"idx {idx} out of range (0..{len(elements)-1})"}
        selector = f"a, button, input, [role=button]"
        try:
            handle = session.page.locator(selector).nth(idx)
            handle.click(timeout=3000)
            return {"ok": True, "result": f"clicked idx={idx}"}
        except Exception as e:
            return {"ok": False, "result": f"click failed: {e}"}

    if name == "fill":
        field, value = args["field"], args["value"]
        v = classify_field(field, value)
        if v.decision == Decision.DENY:
            return {"ok": False, "result": f"DENIED: {v.reason}", "classifier": v.decision.value}
        if v.decision == Decision.ASK and not allow_ask:
            return {"ok": False, "result": f"ASK: {v.reason}", "classifier": v.decision.value}
        try:
            session.page.fill(f'input[name="{field}"], input#{field}, [placeholder*="{field}" i]', value, timeout=3000)
            return {"ok": True, "result": f"filled {field}", "classifier": v.decision.value}
        except Exception as e:
            return {"ok": False, "result": f"fill failed: {e}"}

    if name == "finish":
        return {"ok": True, "result": args, "finish": True}

    return {"ok": False, "result": f"unknown tool: {name}"}
