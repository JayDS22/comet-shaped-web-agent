// Content script: mirrors agent/tools.py in the browser page context.
// Same 5-tool surface (navigate/read_page/click/fill/finish), executed via
// DOM APIs instead of Playwright locators. This is the "third runtime" —
// alongside headless Playwright + Playwright CDP session.

const TOOLS = {
  read_page() {
    const nodes = [...document.querySelectorAll("a, button, input, [role=button]")];
    return {
      url: location.href,
      text: (document.body?.innerText || "").slice(0, 8000),
      clickable: nodes.slice(0, 30).map((n, i) => ({
        idx: i,
        tag: n.tagName.toLowerCase(),
        type: n.type || null,
        name: n.name || n.id || null,
        text: (n.innerText || n.value || n.placeholder || "").slice(0, 80),
        href: n.href || null,
      })),
    };
  },

  click({ idx }) {
    const nodes = document.querySelectorAll("a, button, input, [role=button]");
    if (idx >= nodes.length) return { ok: false, result: `idx ${idx} out of range` };
    nodes[idx].click();
    return { ok: true, result: `clicked idx=${idx}` };
  },

  fill({ field, value }) {
    const el = document.querySelector(
      `input[name="${field}"], input#${field}, [placeholder*="${field}" i]`
    );
    if (!el) return { ok: false, result: `field '${field}' not found` };
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, result: `filled ${field}` };
  },

  navigate({ url }) {
    // Navigation via content_script is limited to same-origin history navigation.
    // Cross-origin navigation is routed through the service_worker (background.js)
    // which owns chrome.tabs.update.
    chrome.runtime.sendMessage({ type: "navigate", url });
    return { ok: true, result: `navigation dispatched to service worker: ${url}` };
  },
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "tool_call") {
    const fn = TOOLS[msg.name];
    if (!fn) {
      sendResponse({ ok: false, result: `unknown tool: ${msg.name}` });
      return true;
    }
    try {
      const result = fn(msg.input || {});
      sendResponse({ ok: true, name: msg.name, ...result });
    } catch (e) {
      sendResponse({ ok: false, result: String(e) });
    }
    return true; // async response
  }
});
