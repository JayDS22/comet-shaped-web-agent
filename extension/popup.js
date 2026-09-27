// Popup: minimal loop wiring content_script (tools) to background (LLM).
// This is a smoke-test surface; the production loop would mirror agent/loop.py
// with per-step tool_use handling and the payload classifier.

const TOOL_SCHEMAS = [
  { name: "read_page", description: "Return page text + clickable map.",
    input_schema: { type: "object", properties: {} } },
  { name: "click", description: "Click element by idx.",
    input_schema: { type: "object", properties: { idx: { type: "integer" } }, required: ["idx"] } },
  { name: "fill", description: "Fill input by name.",
    input_schema: { type: "object", properties: { field: { type: "string" }, value: { type: "string" } }, required: ["field", "value"] } },
  { name: "navigate", description: "Navigate current tab to a URL.",
    input_schema: { type: "object", properties: { url: { type: "string" } }, required: ["url"] } },
  { name: "finish", description: "Signal task completion.",
    input_schema: { type: "object", properties: { summary: { type: "string" }, answer: { type: "string" } }, required: ["summary"] } },
];

const $ = (id) => document.getElementById(id);
const out = $("out");
const log = (s) => { out.textContent += "\n" + s; out.scrollTop = out.scrollHeight; };

$("save").addEventListener("click", async () => {
  await chrome.storage.local.set({ key: $("key").value });
  log("key saved");
});

$("run").addEventListener("click", async () => {
  const task = $("task").value.trim();
  if (!task) return log("enter a task first");
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  log(`\n[task] ${task}`);
  const messages = [{ role: "user", content: task }];

  for (let step = 0; step < 6; step++) {
    log(`\nstep ${step}: calling Claude...`);
    const resp = await chrome.runtime.sendMessage({
      type: "llm_call",
      system: "You are a careful browser agent. Use the tools. Call finish when done.",
      messages, tools: TOOL_SCHEMAS,
    });
    if (!resp?.ok) { log(`llm error: ${resp?.result}`); return; }

    const blocks = resp.response.content || [];
    const toolCalls = blocks.filter((b) => b.type === "tool_use");
    if (!toolCalls.length) { log(`no tool call; stop.`); break; }

    messages.push({ role: "assistant", content: blocks });
    const toolResults = [];
    for (const tu of toolCalls) {
      log(`  -> ${tu.name}(${JSON.stringify(tu.input).slice(0, 80)})`);
      if (tu.name === "finish") {
        log(`  finish: ${JSON.stringify(tu.input)}`);
        return;
      }
      const res = await chrome.tabs.sendMessage(tab.id, {
        type: "tool_call", name: tu.name, input: tu.input,
      });
      toolResults.push({
        type: "tool_result", tool_use_id: tu.id,
        content: JSON.stringify(res).slice(0, 3000),
        is_error: !res?.ok,
      });
    }
    messages.push({ role: "user", content: toolResults });
  }
  log("\nmax steps reached.");
});
