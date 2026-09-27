# Extension surface (MV3)

Third runtime for the comet-shaped-web-agent harness. Same 5-tool surface
(`navigate` / `read_page` / `click` / `fill` / `finish`) as the Python
Playwright + CDP runtime, executed from inside the browser as a Chrome
extension instead.

**Why this matters:** browser agents ship in three shapes:
1. **Headless Playwright** (server-side, no UI) — this repo's default
2. **Playwright + CDP session** (server-side, deeper telemetry) — this repo's `agent/browser.py`
3. **Browser extension** (client-side, same-session as the user) — this dir

Perplexity's Comet ships in shape 3. Knowing how the tool surface, permission
model, and LLM-call routing differ across the three is the actual depth signal.

## Install (developer mode)

1. Open `chrome://extensions/`
2. Toggle **Developer mode** (top-right)
3. Click **Load unpacked**, select this `extension/` directory
4. Pin the extension in the toolbar
5. Click the pinned icon → paste Anthropic key → Save
6. Navigate to any bot-friendly page (e.g. `https://quotes.toscrape.com/`)
7. Enter a task prompt → **Run on current tab**

## Architecture

```
popup.html + popup.js         user-facing controls, orchestrates the loop
       |
       v  chrome.runtime.sendMessage(type="llm_call")
background.js (service worker)  owns the Anthropic API call + cross-origin navigate
       |
       v  chrome.tabs.sendMessage(type="tool_call", ...)
content_script.js (in page)     executes read_page / click / fill / finish via DOM
```

## Compared to the Playwright runtime

| Concern | Playwright + CDP | Chrome extension |
|---|---|---|
| Headless | ✓ | ✗ (runs alongside user) |
| CDP subscriptions | Full (Network, Runtime, DOM, ...) | Not available (would need `chrome.debugger` API + `debugger` permission) |
| Permission model | Process-scoped | Manifest + user-installed; page can request via prompt |
| Anthropic key location | Server env | Local storage (visible only to extension) |
| Cross-origin navigate | Direct | Via service worker `chrome.tabs.update` |
| Payload classifier | Applied in `agent/tools.py` | **Not yet wired here — port from Python to JS** |

## Roadmap

- Port `agent/classifier.py` logic to JS (URL canon + field taxonomy + observation scan) so all three runtimes share one policy
- Emit per-step trace to `chrome.storage.local` so the Streamlit UI can load a replay
- Wire the `chrome.debugger` API to capture Network events (closer parity with the Playwright CDP runtime)
