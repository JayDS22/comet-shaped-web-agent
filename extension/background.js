// Service worker: owns cross-origin navigation + the LLM call.
// The content_script cannot navigate cross-origin from arbitrary pages,
// so the service worker mediates via chrome.tabs.update.
//
// The LLM call happens here (not in the content_script) because content
// scripts can't reach cross-origin APIs without host_permissions AND
// because keeping the Anthropic key out of page context is a basic
// hygiene move — a compromised page could otherwise exfiltrate it.

const ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929";

async function callClaude(system, messages, tools, apiKey) {
  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: ANTHROPIC_MODEL,
      max_tokens: 1024,
      system,
      tools,
      messages,
    }),
  });
  if (!resp.ok) throw new Error(`Anthropic ${resp.status}: ${await resp.text()}`);
  return await resp.json();
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "navigate" && msg.url) {
    chrome.tabs.update(sender.tab.id, { url: msg.url })
      .then(() => sendResponse({ ok: true }))
      .catch((e) => sendResponse({ ok: false, result: String(e) }));
    return true;
  }

  if (msg?.type === "llm_call") {
    (async () => {
      const { key } = await chrome.storage.local.get("key");
      if (!key) return sendResponse({ ok: false, result: "no ANTHROPIC key set" });
      try {
        const out = await callClaude(msg.system, msg.messages, msg.tools, key);
        sendResponse({ ok: true, response: out });
      } catch (e) {
        sendResponse({ ok: false, result: String(e) });
      }
    })();
    return true;
  }
});
