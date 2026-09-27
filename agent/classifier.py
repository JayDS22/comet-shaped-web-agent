"""Payload classifier: allow / ask / deny for URLs and form fields.

Applied before every browser action. The agent MUST route through this
before touching the page, and MUST surface `ask` decisions to the human.
"""
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class Verdict:
    decision: Decision
    reason: str


URL_DENY = ("banking", "wellsfargo", "chase.com", "paypal.com", "coinbase")
URL_ASK = ("checkout", "signup", "auth", "login", "oauth", "download")

FIELD_DENY = ("password", "ssn", "cvv", "card_number", "cc-number", "cvc")
FIELD_ASK = ("email", "phone", "address", "zip", "dob", "birthday")


def classify_url(url: str) -> Verdict:
    host = (urlparse(url).hostname or "").lower()
    path = urlparse(url).path.lower()
    blob = f"{host}{path}"
    if any(k in blob for k in URL_DENY):
        return Verdict(Decision.DENY, f"URL matches denylist token")
    if any(k in blob for k in URL_ASK):
        return Verdict(Decision.ASK, f"URL matches asklist token (auth/checkout/download)")
    return Verdict(Decision.ALLOW, "URL not flagged")


def classify_field(field_name: str, field_value: str = "") -> Verdict:
    name = (field_name or "").lower()
    if any(k in name for k in FIELD_DENY):
        return Verdict(Decision.DENY, f"Field '{field_name}' matches denylist (secret/PII)")
    if any(k in name for k in FIELD_ASK):
        return Verdict(Decision.ASK, f"Field '{field_name}' matches asklist (PII)")
    return Verdict(Decision.ALLOW, "Field not flagged")


if __name__ == "__main__":
    assert classify_url("https://example.com/search?q=x").decision == Decision.ALLOW
    assert classify_url("https://mybank.wellsfargo.com").decision == Decision.DENY
    assert classify_url("https://shop.example/checkout").decision == Decision.ASK
    assert classify_field("password").decision == Decision.DENY
    assert classify_field("email").decision == Decision.ASK
    assert classify_field("query").decision == Decision.ALLOW
    print("classifier: ok")
