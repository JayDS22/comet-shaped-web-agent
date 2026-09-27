"""Playwright + Chrome DevTools Protocol session wrapper.

Owns the browser lifecycle. Exposes a small surface for tools.py to call.
Enables CDP so we can subscribe to Network / Console events later.
"""
from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, Page, CDPSession


class BrowserUnavailable(RuntimeError):
    """Raised when neither the Playwright-bundled Chromium nor the system
    chromium binary can be launched. Streamlit Cloud is a common trigger:
    the deploy image ships without Chromium and Playwright's postinstall
    step is not run. Caller should show a friendly message and skip the
    browser-dependent path."""


@dataclass
class BrowserSession:
    browser: Browser
    page: Page
    cdp: CDPSession

    def close(self):
        self.browser.close()


def _install_chromium() -> bool:
    """Best-effort: run `playwright install chromium` in a subprocess.
    Returns True on success. Used as a one-shot self-heal on first launch."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=180,
        )
        return r.returncode == 0
    except Exception:
        return False


def launch(headless: bool = True) -> BrowserSession:
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=headless)
    except Exception as first:
        # Self-heal: try installing Chromium, then retry once.
        if _install_chromium():
            try:
                browser = pw.chromium.launch(headless=headless)
            except Exception as second:
                pw.stop()
                raise BrowserUnavailable(
                    f"Chromium not available even after install attempt: {second}"
                ) from second
        else:
            # Fall back to system chromium via the channel API.
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
    return BrowserSession(browser=browser, page=page, cdp=cdp)


def dom_snapshot(page: Page, max_chars: int = 8000) -> str:
    """Return a truncated text snapshot of the page for the model."""
    try:
        text = page.inner_text("body", timeout=3000)
    except Exception:
        text = page.content()
    return text[:max_chars]


def clickable_map(page: Page, limit: int = 30) -> list[dict]:
    """Return a small structured list of clickable elements (buttons, links, inputs).

    Small and structured beats a full DOM dump — model plans faster on a menu.
    """
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
