"""Playwright + Chrome DevTools Protocol session wrapper.

Owns the browser lifecycle. Subscribes to CDP events (Network.responseReceived,
Runtime.consoleAPICalled) and buffers them so the eval trace can surface real
browser telemetry, not just LLM tool calls.
"""
from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Browser, Page, CDPSession, Playwright


class BrowserUnavailable(RuntimeError):
    """Raised when neither the Playwright-bundled Chromium nor the system
    chromium binary can be launched. Streamlit Cloud is a common trigger."""


@dataclass
class CDPEvent:
    kind: str          # "network" | "console"
    method: str        # CDP event method name
    summary: str       # short human-readable line
    raw: dict          # trimmed payload


@dataclass
class BrowserSession:
    pw: Playwright
    browser: Browser
    page: Page
    cdp: CDPSession
    events: list[CDPEvent] = field(default_factory=list)

    def close(self):
        try:
            self.browser.close()
        finally:
            self.pw.stop()

    def drain_events(self) -> list[CDPEvent]:
        """Return + clear the buffered CDP events."""
        drained = list(self.events)
        self.events.clear()
        return drained


def _install_chromium() -> bool:
    """Best-effort: run `playwright install chromium` in a subprocess."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=180,
        )
        return r.returncode == 0
    except Exception:
        return False


def _attach_cdp_listeners(cdp: CDPSession, buffer: list[CDPEvent]) -> None:
    """Subscribe to Network + Console + Runtime events. Buffer trimmed payloads."""

    def on_response(params: dict):
        resp = params.get("response", {}) or {}
        status = resp.get("status")
        url = resp.get("url", "")
        mime = resp.get("mimeType", "")
        buffer.append(CDPEvent(
            kind="network",
            method="Network.responseReceived",
            summary=f"{status} {mime}  {url[:100]}",
            raw={"status": status, "url": url, "mime": mime,
                 "remoteIPAddress": resp.get("remoteIPAddress")},
        ))

    def on_console(params: dict):
        msg_type = params.get("type", "log")
        args = params.get("args", []) or []
        text_parts = []
        for a in args[:3]:
            v = a.get("value")
            if v is not None:
                text_parts.append(str(v)[:80])
        text = " ".join(text_parts)
        buffer.append(CDPEvent(
            kind="console",
            method="Runtime.consoleAPICalled",
            summary=f"[{msg_type}] {text[:120]}",
            raw={"type": msg_type, "text": text},
        ))

    def on_exception(params: dict):
        exc = params.get("exceptionDetails", {}) or {}
        buffer.append(CDPEvent(
            kind="console",
            method="Runtime.exceptionThrown",
            summary=f"[exception] {exc.get('text', 'unknown')[:120]}",
            raw={"text": exc.get("text"), "line": exc.get("lineNumber")},
        ))

    cdp.on("Network.responseReceived", on_response)
    cdp.on("Runtime.consoleAPICalled", on_console)
    cdp.on("Runtime.exceptionThrown", on_exception)


def launch(headless: bool = True) -> BrowserSession:
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=headless)
    except Exception as first:
        if _install_chromium():
            try:
                browser = pw.chromium.launch(headless=headless)
            except Exception as second:
                pw.stop()
                raise BrowserUnavailable(
                    f"Chromium not available even after install attempt: {second}"
                ) from second
        else:
            try:
                browser = pw.chromium.launch(headless=headless, channel="chromium")
            except Exception as third:
                pw.stop()
                raise BrowserUnavailable(
                    f"No usable Chromium. Playwright: {first}. System channel: {third}. "
                    "For a working task-run demo, deploy via the Dockerfile "
                    "(mcr.microsoft.com/playwright/python base has Chromium built in) "
                    "on Fly.io / Render / Railway."
                ) from third

    context = browser.new_context()
    page = context.new_page()
    cdp = context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Runtime.enable")

    events: list[CDPEvent] = []
    _attach_cdp_listeners(cdp, events)

    return BrowserSession(pw=pw, browser=browser, page=page, cdp=cdp, events=events)


def dom_snapshot(page: Page, max_chars: int = 8000) -> str:
    """Return a truncated text snapshot of the page for the model."""
    try:
        text = page.inner_text("body", timeout=3000)
    except Exception:
        text = page.content()
    return text[:max_chars]


def clickable_map(page: Page, limit: int = 30) -> list[dict]:
    """Return a small structured list of clickable elements."""
    js = """
    () => {
      const nodes = [...document.querySelectorAll('a, button, input, [role=button]')];
      return nodes.slice(0, %d).map((n, i) => ({
        idx: i,
        tag: n.tagName.toLowerCase(),
        type: n.type || null,
        name: n.name || n.id || null,
        text: (n.innerText || n.value || n.placeholder || '').slice(0, 80),
        href: n.href || null,
      }));
    }
    """ % limit
    try:
        return page.evaluate(js)
    except Exception:
        return []
