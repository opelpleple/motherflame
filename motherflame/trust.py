"""
Motherflame Trust — a trust score for the org's own knowledge.

Ironic-but-true: a tool built to feed *trustworthy* context to agents should
score the trustworthiness of each fact, not just pass through an LLM's
self-reported `confidence`. This module computes a composite trust score per
claim from signals that actually predict reliability:

  • SOURCE AUTHORITY — a human interview/manual entry or a designated owner is
    worth more than an LLM keyword guess from a random file.
  • HUMAN VERIFICATION — a fact a person explicitly verified is trusted above
    any model confidence (kept as a separate signal, not conflated).
  • STALENESS DECAY — knowledge rots. A claim loses trust as it ages; finance
    facts (pricing, regulation) especially.
  • RAW CONFIDENCE — the LLM/extractor's own score, as one input among several.

Score is in [0, 1]. Pure stdlib (no deps). Used by the resolution ladder's
fallback tier so the *most trustworthy* claim wins, not merely the most recent.
"""
from __future__ import annotations

from datetime import datetime

# Source authority weights — how much we trust a claim by where it came from.
SOURCE_AUTHORITY = {
    "manual": 1.0,        # a human ran /resolve
    "interview": 0.95,    # a human answered the onboarding interview
    "chat": 0.9,          # a human typed it to the agent / via MCP
    "verified": 1.0,      # explicitly human-verified (see verify)
}
DEFAULT_SOURCE_AUTHORITY = 0.6   # an extracted fact from a document
KEYWORD_AUTHORITY = 0.35         # low-precision keyword fallback guess

# Half-life for staleness decay, in days. After this long, the age component of
# trust has halved. Tuned for business facts that drift over a quarter.
STALENESS_HALFLIFE_DAYS = 180.0


def _source_authority(claim: dict) -> float:
    if claim.get("verified"):
        return SOURCE_AUTHORITY["verified"]
    src = (claim.get("source") or "").lower()
    if src in SOURCE_AUTHORITY:
        return SOURCE_AUTHORITY[src]
    # keyword-fallback claims are tagged with low confidence (0.4) by harvest
    if claim.get("confidence", 0.7) <= 0.4 and "." in src:
        return KEYWORD_AUTHORITY
    return DEFAULT_SOURCE_AUTHORITY


def _age_days(claim: dict, now: datetime | None = None) -> float:
    ts = claim.get("ts") or claim.get("harvested_at") or claim.get("valid_from")
    if not ts:
        return 0.0
    try:
        when = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return 0.0
    now = now or datetime.now()
    return max(0.0, (now - when).total_seconds() / 86400.0)


def _staleness_factor(claim: dict, now: datetime | None = None) -> float:
    """Exponential decay: 1.0 fresh → 0.5 at one half-life → →0 as it ages."""
    age = _age_days(claim, now)
    return 0.5 ** (age / STALENESS_HALFLIFE_DAYS)


def trust_score(claim: dict, now: datetime | None = None) -> float:
    """Composite trust in a single claim, in [0, 1].

    A human-verified claim floors high regardless of age (verification is a
    deliberate, dated act). Otherwise trust = authority × confidence, attenuated
    by staleness.
    """
    authority = _source_authority(claim)
    confidence = float(claim.get("confidence", 0.7))
    stale = _staleness_factor(claim, now)

    if claim.get("verified"):
        # Verified facts stay highly trusted but still decay slowly so a
        # years-old "verified" fact doesn't outrank a fresh correction forever.
        return round(min(1.0, 0.85 + 0.15 * stale), 4)

    base = authority * confidence
    return round(base * (0.4 + 0.6 * stale), 4)   # staleness never zeroes it fully


def explain(claim: dict, now: datetime | None = None) -> dict:
    """Break down the trust score for display / debugging."""
    return {
        "trust": trust_score(claim, now),
        "authority": round(_source_authority(claim), 3),
        "confidence": round(float(claim.get("confidence", 0.7)), 3),
        "age_days": round(_age_days(claim, now), 1),
        "staleness_factor": round(_staleness_factor(claim, now), 3),
        "verified": bool(claim.get("verified")),
    }
