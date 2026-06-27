"""
Motherflame Conflict Manager — make the Org Brain a single source of truth
even when teammates disagree.

THE PROBLEM
-----------
Two people harvest "pricing". Peter's files say $48k, Alice's say $50k.
A naive merge clobbers one. But which is *true*?

THE MODEL
---------
The brain keeps TWO layers:

  claims     — every competing assertion, never overwritten. Each claim records
               who/where/when/how-confident.  (the evidence)
  canonical  — exactly one resolved value per key.                (the truth)

A resolver computes `canonical` from `claims` using a precedence ladder that
mirrors how real orgs decide:

  1. MANUAL    — a human explicitly resolved it → always wins
  2. OWNER     — the key/category has a designated owner → owner's latest claim wins
  3. CONSENSUS — N claims agree on the same value → that value wins
  4. RECENCY×CONFIDENCE — newest, most-confident claim wins (fallback)

A key is "contested" when ≥2 claims hold materially different values and no
higher-precedence rule has settled it. Contested keys surface to the user via
`/conflicts` and can be settled with `/resolve`.
"""

from datetime import datetime


# ── Brain shape helpers (backward compatible) ──────────────────────────────

def ensure_layers(brain: dict) -> dict:
    """Make sure the brain has claims/resolutions/owners structures."""
    brain.setdefault("items", [])          # canonical (existing behavior)
    brain.setdefault("claims", {})         # key -> [claim, ...]
    brain.setdefault("resolutions", {})    # key -> manual resolution
    brain.setdefault("owners", {})         # scope (category or key) -> owner
    return brain


def _norm(value: str) -> str:
    """Normalize a value for equality comparison (consensus / contested check).

    Goes beyond lowercase+whitespace: recognizes that '$48k', '48,000', and
    'USD 48000' refer to the same number, so they don't register as a false
    disagreement. Non-numeric values fall back to lowercased text.
    """
    s = str(value).lower().strip()
    num = _extract_number(s)
    if num is not None:
        # canonical numeric form (drop trailing .0)
        return f"#{num:g}"
    return " ".join(s.split())


def _extract_number(s: str):
    """Pull a single numeric magnitude out of a string, honoring k/m/b suffixes
    and thousands separators. Returns a float, or None if not cleanly numeric."""
    import re
    t = s.lower().strip()
    # strip currency symbols / words and commas
    t = re.sub(r"[$€£฿]|usd|thb|baht|eur|gbp", "", t)
    t = t.replace(",", "").strip()
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([kmb])?", t)
    if not m:
        return None
    val = float(m.group(1))
    mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get(m.group(2) or "", 1)
    return val * mult


# ── Key canonicalization ───────────────────────────────────────────────────
# Without this, LLM-chosen keys drift (pricing / price / pricing_model) and the
# conflict resolver never sees them as the SAME fact — so disagreements slip
# through as separate "facts" and the single-source-of-truth guarantee breaks.

# Curated alias map → canonical key. Extend freely; this is the controlled vocab.
KEY_ALIASES = {
    "pricing": {"price", "prices", "pricing_model", "price_model", "pricing_tier",
                "pricing_tiers", "cost", "costs", "price_point", "price_points",
                "subscription_price", "plan_price"},
    "team_size": {"headcount", "team", "team_count", "employees", "employee_count",
                  "staff_size", "number_of_employees", "people_count"},
    "company_name": {"org_name", "organization_name", "org", "company", "business_name"},
    "what_we_do": {"mission", "description", "company_description", "tagline",
                   "value_proposition", "value_prop", "elevator_pitch", "summary"},
    "product_name": {"product", "main_product", "platform_name", "app_name", "tool_name"},
    "target_customer": {"customer", "customers", "target_market", "audience",
                        "target_audience", "ideal_customer", "icp", "buyer"},
    "goals": {"goal", "objective", "objectives", "okr", "okrs", "kpi", "kpis", "targets"},
    "communication_style": {"voice", "brand_voice", "tone", "tone_of_voice", "style"},
    "current_focus": {"focus", "priority", "priorities", "roadmap", "current_priority"},
}

# Reverse index: alias → canonical (built once)
_ALIAS_INDEX = {}
for _canon, _aliases in KEY_ALIASES.items():
    _ALIAS_INDEX[_canon] = _canon
    for _a in _aliases:
        _ALIAS_INDEX[_a] = _canon


def canonical_key(key: str) -> str:
    """Map a free-form/LLM key to its canonical form.
    1) snake-case normalize  2) alias lookup  3) singularize trailing 's'."""
    if not key:
        return "unknown"
    k = "_".join(str(key).strip().lower().replace("-", "_").replace(" ", "_").split("_"))
    k = "_".join(p for p in k.split("_") if p)  # collapse repeats
    if k in _ALIAS_INDEX:
        return _ALIAS_INDEX[k]
    # try singular form (pricings → pricing)
    if k.endswith("s") and k[:-1] in _ALIAS_INDEX:
        return _ALIAS_INDEX[k[:-1]]
    return k


# ── Recording claims (replaces blind append) ───────────────────────────────

def add_claim(brain: dict, category: str, key: str, value: str,
              source: str = "unknown", owner: str = "", confidence: float = 0.7,
              ts: str = None) -> None:
    """Record a claim about `key`. Never overwrites — appends to the evidence list.
    De-dupes identical (value, source) pairs so re-scans don't pile up.
    The key is canonicalized so aliases (pricing/price/pricing_model) collapse
    to one fact — otherwise disagreements would slip through as separate keys."""
    ensure_layers(brain)
    key = canonical_key(key)
    ts = ts or datetime.now().isoformat()
    claim = {
        "category": category, "key": key, "value": value,
        "source": source, "owner": owner,
        "confidence": float(confidence), "ts": ts,
    }
    claims = brain["claims"].setdefault(key, [])
    # de-dupe: same normalized value from same source → update ts only
    for c in claims:
        if _norm(c["value"]) == _norm(value) and c["source"] == source:
            c["ts"] = ts
            c.pop("retracted", None)   # re-asserting un-retracts
            return
    claims.append(claim)


def retract_claim(brain: dict, key: str, value: str = None, source: str = None) -> int:
    """Tombstone claims for a key (a CRDT-style delete that survives merges).

    A retracted claim stays in the list marked retracted=True so that a later
    merge can't silently resurrect it. Returns how many claims were tombstoned.
    If value/source are given, only matching claims are retracted; otherwise all
    claims for the key are.
    """
    ensure_layers(brain)
    key = canonical_key(key)
    n = 0
    for c in brain.get("claims", {}).get(key, []):
        if value is not None and _norm(c["value"]) != _norm(value):
            continue
        if source is not None and c["source"] != source:
            continue
        if not c.get("retracted"):
            c["retracted"] = True
            c["retracted_at"] = datetime.now().isoformat()
            n += 1
    return n


def _live_claims(brain: dict, key: str) -> list:
    """Claims for a key that haven't been tombstoned."""
    return [c for c in brain.get("claims", {}).get(key, []) if not c.get("retracted")]


# ── Resolution ladder ──────────────────────────────────────────────────────

def _owner_for(brain: dict, category: str, key: str) -> str:
    """Resolve the authority for a key: per-key owner beats per-category owner."""
    owners = brain.get("owners", {})
    return owners.get(key) or owners.get(category) or ""


def resolve_key(brain: dict, key: str) -> dict:
    """Return {value, reason, contested, claim_count, chosen_claim} for one key.
    Tombstoned (retracted) claims are ignored."""
    key = canonical_key(key)
    claims = _live_claims(brain, key)
    if not claims:
        return {"value": None, "reason": "no claims", "contested": False,
                "claim_count": 0, "chosen_claim": None}

    distinct = {_norm(c["value"]) for c in claims}
    contested_raw = len(distinct) > 1
    category = claims[0]["category"]

    # 1. MANUAL — human override wins outright
    res = brain.get("resolutions", {}).get(key)
    if res:
        return {"value": res["value"], "reason": f"manually set by {res.get('by','?')}",
                "contested": False, "claim_count": len(claims),
                "chosen_claim": None}

    # 2. OWNER authority — owner's most recent claim wins
    owner = _owner_for(brain, category, key)
    if owner:
        owned = [c for c in claims if c.get("owner") == owner]
        if owned:
            best = max(owned, key=lambda c: c["ts"])
            # contested only if a NON-owner disagrees AND we surface it
            return {"value": best["value"], "reason": f"owner ({owner})",
                    "contested": contested_raw, "claim_count": len(claims),
                    "chosen_claim": best}

    # 3. CONSENSUS — a value asserted by the most distinct sources
    by_value = {}
    for c in claims:
        by_value.setdefault(_norm(c["value"]), set()).add(c["source"])
    top_val, top_sources = max(by_value.items(), key=lambda kv: len(kv[1]))
    if len(top_sources) >= 2 and len(top_sources) > max(
            (len(s) for v, s in by_value.items() if v != top_val), default=0):
        chosen = next(c for c in claims if _norm(c["value"]) == top_val)
        return {"value": chosen["value"],
                "reason": f"consensus ({len(top_sources)} sources)",
                "contested": False, "claim_count": len(claims),
                "chosen_claim": chosen}

    # 4. RECENCY × CONFIDENCE — newest, most-confident
    best = max(claims, key=lambda c: (c["confidence"], c["ts"]))
    return {"value": best["value"], "reason": "recency×confidence",
            "contested": contested_raw, "claim_count": len(claims),
            "chosen_claim": best}


def rebuild_canonical(brain: dict) -> dict:
    """Recompute brain['items'] from claims using the resolver. Idempotent."""
    ensure_layers(brain)
    items = []
    for key, claims in brain["claims"].items():
        if not claims:
            continue
        r = resolve_key(brain, key)
        if r["value"] is None:
            continue
        items.append({
            "category": claims[0]["category"],
            "key": key,
            "value": r["value"],
            "source": (r.get("chosen_claim") or {}).get("source", "resolved"),
            "confidence": (r.get("chosen_claim") or {}).get("confidence", 1.0),
            "harvested_at": (r.get("chosen_claim") or {}).get("ts", datetime.now().isoformat()),
            "resolution": r["reason"],
            "contested": r["contested"],
        })
    brain["items"] = items
    return brain


# ── User-facing operations ─────────────────────────────────────────────────

def list_conflicts(brain: dict) -> list[dict]:
    """All keys that are currently contested (need attention)."""
    out = []
    for key in brain.get("claims", {}):
        r = resolve_key(brain, key)
        if r["contested"]:
            claims = brain["claims"][key]
            out.append({
                "key": key,
                "category": claims[0]["category"],
                "current": r["value"],
                "reason": r["reason"],
                "candidates": [
                    {"value": c["value"], "owner": c.get("owner") or "—",
                     "source": c["source"], "confidence": c["confidence"], "ts": c["ts"]}
                    for c in claims
                ],
            })
    return out


def manual_resolve(brain: dict, key: str, value: str, by: str = "user", reason: str = "") -> None:
    """A human declares the canonical value for a contested key."""
    ensure_layers(brain)
    brain["resolutions"][canonical_key(key)] = {
        "value": value, "by": by, "reason": reason,
        "ts": datetime.now().isoformat(),
    }


def auto_resolve_all(brain: dict) -> dict:
    """Bulk-settle every contested key that the resolver can decide on its own
    (owner authority or consensus), leaving only genuine ambiguities — those
    decided by the recency×confidence fallback — for manual review.

    Returns {auto_resolved: [...], needs_human: [...]}. Auto-resolved keys are
    pinned as manual resolutions (with by='auto') so they stay stable.
    """
    ensure_layers(brain)
    auto, human = [], []
    for key in list(brain.get("claims", {})):
        r = resolve_key(brain, key)
        if not r["contested"]:
            continue
        # owner/consensus give a defensible winner → pin it automatically
        if r["reason"].startswith("owner") or r["reason"].startswith("consensus"):
            manual_resolve(brain, key, r["value"], by="auto", reason=r["reason"])
            auto.append({"key": key, "value": r["value"], "reason": r["reason"]})
        else:
            human.append({"key": key, "value": r["value"], "reason": r["reason"]})
    rebuild_canonical(brain)
    return {"auto_resolved": auto, "needs_human": human}


def set_owner(brain: dict, scope: str, owner: str) -> None:
    """Assign authority. scope is a category (e.g. 'Product') or a key (e.g. 'pricing')."""
    ensure_layers(brain)
    brain["owners"][scope] = owner


# ── Migration: fold legacy flat items into the claims layer ────────────────

def migrate_items_to_claims(brain: dict) -> dict:
    """One-time: turn pre-existing flat items[] into claims so old brains keep working."""
    ensure_layers(brain)
    for it in list(brain.get("items", [])):
        key = it.get("key")
        if not key:
            continue
        # only migrate if this canonical key has no claims yet
        if not brain["claims"].get(canonical_key(key)):
            add_claim(brain, it.get("category", "General"), key, it.get("value", ""),
                      source=it.get("source", "legacy"),
                      owner=it.get("owner", ""),
                      confidence=it.get("confidence", 0.7),
                      ts=it.get("harvested_at"))
    return brain
