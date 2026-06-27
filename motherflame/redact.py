"""
Motherflame Redaction — strip obvious PII/secrets from text BEFORE it is sent
to a third-party LLM during harvest.

Bring-your-own-key does NOT make harvest private: the file contents still leave
the machine and hit OpenAI/Anthropic. For a company brain built from internal
docs (customer data, financials, credentials), that's a real leak. This module
masks the highest-risk patterns with stdlib regex — no external deps.

It is intentionally conservative: it targets credentials, contact PII, and
financial identifiers that should never train or transit, while leaving the
business signal (pricing, team size, strategy) intact so harvest still works.
"""

import re

# (label, compiled pattern) — order matters; more specific first.
_PATTERNS = [
    ("EMAIL",     re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("API_KEY",   re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}\b")),
    ("AWS_KEY",   re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("BEARER",    re.compile(r"\b(?:Bearer|token|api[_-]?key)\s*[:=]\s*\S{12,}", re.I)),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("SSN",       re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE",     re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?){2,4}\d{2,4}\b")),
    ("IP",        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


def redact(text: str, enabled: bool = True) -> tuple[str, dict]:
    """Return (redacted_text, counts). counts maps label -> n_hits.

    Each match is replaced with a [LABEL_REDACTED] placeholder so the LLM still
    sees the surrounding structure but never the sensitive value.
    """
    if not enabled or not text:
        return text, {}
    counts = {}

    def _sub(label):
        def repl(_m):
            counts[label] = counts.get(label, 0) + 1
            return f"[{label}_REDACTED]"
        return repl

    out = text
    for label, pat in _PATTERNS:
        out = pat.sub(_sub(label), out)
    return out, counts


def summarize(counts: dict) -> str:
    """Human-readable one-liner, e.g. '3 EMAIL, 1 API_KEY redacted'."""
    if not counts:
        return ""
    return ", ".join(f"{n} {label}" for label, n in sorted(counts.items()))
