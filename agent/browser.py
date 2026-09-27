"""Playwright + Chrome DevTools Protocol session wrapper.

Owns the browser lifecycle. Exposes a small surface for tools.py to call.
Enables CDP so we can subscribe to Network / Console events later.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, Page, CDPSession


@dataclass
class BrowserSession:
    browser: Browser
    page: Page
    cdp: CDPSession

    def close(self):
        self.browser.close()


def launch(headless: bool = True) -> BrowserSession:
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
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
