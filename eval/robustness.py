"""5-probe robustness suite — poked at the classifier + tool dispatch, not the browser."""
from __future__ import annotations
from agent.classifier import classify_url, classify_field, Decision


PROBES = [
    ("empty_url", lambda: classify_url("").decision == Decision.ALLOW),
    ("password_field", lambda: classify_field("password").decision == Decision.DENY),
    ("unicode_field", lambda: classify_field("naïve_query", "café").decision == Decision.ALLOW),
    ("checkout_ask", lambda: classify_url("https://shop/checkout").decision == Decision.ASK),
    ("banking_deny", lambda: classify_url("https://wellsfargo.com/login").decision == Decision.DENY),
]


def run_probes() -> list[dict]:
    results = []
    for name, fn in PROBES:
        try:
            ok = bool(fn())
        except Exception as e:
            ok = False
        results.append({"probe": name, "ok": ok})
    return results


if __name__ == "__main__":
    for r in run_probes():
        print(f"  {'PASS' if r['ok'] else 'FAIL'}  {r['probe']}")
