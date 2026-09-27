"""Classifier probe suite. Five expected-PASS, one expected-FAIL.

The XFAIL probe is intentional. See SECURITY.md for why: the classifier is
a substring keyword filter, not a security boundary, and pretending
otherwise would be worse than shipping the gap honestly.
"""
from __future__ import annotations
from agent.classifier import classify_url, classify_field, Decision


PROBES = [
    ("empty_url",       "PASS", lambda: classify_url("").decision == Decision.ALLOW),
    ("password_field",  "PASS", lambda: classify_field("password").decision == Decision.DENY),
    ("unicode_field",   "PASS", lambda: classify_field("naïve_query", "café").decision == Decision.ALLOW),
    ("checkout_ask",    "PASS", lambda: classify_url("https://shop/checkout").decision == Decision.ASK),
    ("banking_deny",    "PASS", lambda: classify_url("https://wellsfargo.com/login").decision == Decision.DENY),
    # Intentionally-failing probe. Homograph URLs escape the ASCII substring match.
    # Documented in SECURITY.md #1. Fix would need unicodedata.normalize + confusables.
    ("homograph_wells_XFAIL", "XFAIL",
        lambda: classify_url("https://weIIsfargo.com").decision == Decision.DENY),
]


def run_probes() -> list[dict]:
    """Returns per-probe dicts with:
       - actual: True if the classifier behaved as the lambda expects
       - status: PASS (met expectation) | FAIL (missed) | XFAIL (expected-fail confirmed)
       - ok:     True if this row is not a regression
    """
    results = []
    for name, kind, fn in PROBES:
        try:
            actual = bool(fn())
        except Exception:
            actual = False

        if kind == "PASS":
            status = "PASS" if actual else "FAIL"
        else:  # kind == "XFAIL"
            status = "XFAIL" if not actual else "UNEXPECTED_PASS"

        ok = status in ("PASS", "XFAIL")
        results.append({"probe": name, "kind": kind, "status": status,
                        "actual": actual, "ok": ok})
    return results


if __name__ == "__main__":
    for r in run_probes():
        note = "" if r["kind"] == "PASS" else "  (classifier does not catch this - see SECURITY.md)"
        print(f"  {r['status']:15s}  {r['probe']}{note}")
