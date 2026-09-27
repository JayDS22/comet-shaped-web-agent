# DESIGN.md

Design decisions worth naming out loud, and why they went the way they did.
Notes toward a longer writeup — read alongside [SECURITY.md](SECURITY.md)
and the [blog post](docs/blog-post.md).

## 1. Denylist adherence is not safety

The rubric ships an axis called `denylist_adherence`, not `safety`. That
rename is not cosmetic. A rubric that names a "safety" axis and computes
it from denylist hits is telling you the agent stayed inside the fence
you drew — nothing about whether the fence encloses the right space.

The classifier is deliberately small (~150 lines) and inspectable. It has
been hardened with Unicode NFKC + IDNA canonicalization + confusable
mapping (16 PASS probes), but three attacks still XFAIL:

- **Redirect-chain** — the classifier inspects only the URL the model
  requested. `navigate("https://safe.com/redir?to=wellsfargo.com/login")`
  passes.
- **Novel phishing** — `we11sfarg0-secure-login.com` is not on the
  denylist and cannot be caught by string canonicalization.
- **Semantic PII** — a field labelled `favorite_color` storing a
  mother's maiden name is not caught by field-name taxonomy.

Each of these needs a different tool (HEAD-request pre-classification for
redirects, a novelty detector or blocklist feed for phishing, an LLM-in-
the-loop screen for semantic PII). None of them are the same tool. That
is the point of documenting them as XFAIL rather than pretending the
classifier is a boundary.

## 2. Three runtimes, one tool surface

Browser agents ship in three shapes: headless Playwright, Playwright + CDP
session, and Chrome extension (content_script + service worker). The
tool surface — `navigate`, `read_page`, `click`, `fill`, `finish` — is
identical across all three. What differs is:

- **Where the LLM call happens** (server vs service worker)
- **Where the key lives** (env var vs `chrome.storage.local` vs remote)
- **What telemetry is available** (full CDP vs `chrome.debugger` vs none)
- **How cross-origin navigation is authorized** (Playwright directly vs
  service worker mediation vs same-origin restriction)

Portability requires keeping the tool contract stable and pushing the
runtime differences to the outermost layer. The extension surface at
`extension/` is a stub demonstrating this — the same 5 tools, different
plumbing.

## 3. CDP is the interesting API, not `Network.enable`

The scaffold originally called `cdp.send("Network.enable")` with no
subscribers. Advertising CDP without subscribing to CDP events is
decoration.

The current implementation subscribes to three CDP events and buffers
them into the run trace:

- `Network.responseReceived` — surfaces status + MIME + remote IP for
  every response. Feeds into a future data-exfiltration axis (has the
  agent triggered network activity to a host outside the denylist AND
  outside the task's expected domain set?).
- `Runtime.consoleAPICalled` — captures console.log / console.warn from
  the page. Signals broken client-side scripts + poorly-behaved sites.
- `Runtime.exceptionThrown` — captures unhandled JS exceptions on the
  page, which the model may otherwise miss when reading DOM text.

A trace with 12 tool calls and 40 network responses is more diagnostic
than 12 tool calls alone. That difference is the point of using CDP at all.

## 4. Mock backend + local fixture: honest offline path

The loop runs without an Anthropic key (mock LLM walks navigate → read_page
→ finish) and without an external network (self-hosted `http.server` on
`127.0.0.1:5555`). Both were deliberate:

- **Mock backend** because a repo whose primary demo requires a paid API
  key filters out casual readers.
- **Self-hosted fixture** because Google/reCAPTCHA/CF-turnstile block
  headless Chromium, and a reader who hits that block will conclude the
  author didn't test end-to-end.

T2 (pagination on `quotes.toscrape.com`) hits a real internet site because
`quotes.toscrape.com` is intentionally bot-friendly. The choice of target
matters more than the number of tasks.

## 5. What Option C looked like

The scaffold shipped as Option B (adversary's INTERESTED tier). Option C
was the "IMPRESSED" upgrade — this commit is roughly that:

- Adversarial classifier (16 PASS + 3 documented XFAIL) — done
- Real CDP subscriptions — done
- 2 working tasks (T1 local + T2 real-web) — done
- Comparison scaffold vs browser-use — done
- Extension runtime stub — done
- Blog post + DESIGN.md — done (this file + docs/blog-post.md)

What's left: the extension needs the classifier ported to JS; T3-T5 land
per README roadmap; comparison scorecard needs to be run and its output
committed as an artifact.
