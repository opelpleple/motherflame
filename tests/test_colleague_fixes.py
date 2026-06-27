"""Tests for the colleague-flagged round: chat/MCP claims-routing (data loss),
locking, LLM retry/backoff, forget tool, provenance, finance/Thai aliases."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import runtime, conflicts as cf, agent


# ── #1: chat/MCP add_fact must survive rebuild (the data-loss bug) ──────────

def test_chat_add_fact_survives_rebuild():
    brain = {"org_name": "T", "items": [], "claims": {}}
    cf.ensure_layers(brain)
    runtime._tool_add_fact(brain, "Funding", "seed_round", "we raised $2M seed")
    assert "seed_round" in brain["claims"]          # it's a CLAIM now, not just an item
    cf.rebuild_canonical(brain)                      # next harvest/pull
    assert any(i["value"].startswith("we raised $2M") for i in brain["items"])


def test_chat_add_fact_updates_in_place():
    brain = {"org_name": "T", "items": [], "claims": {}}
    runtime._tool_add_fact(brain, "Product", "pricing", "$48k")
    msg = runtime._tool_add_fact(brain, "Product", "pricing", "$60k")
    assert "Updated" in msg
    assert cf.resolve_key(brain, "pricing")["value"] == "$60k"  # newest chat wins


# ── #9b: forget tool ────────────────────────────────────────────────────────

def test_forget_fact_tool():
    brain = {"org_name": "T", "items": [], "claims": {}}
    runtime._tool_add_fact(brain, "Product", "pricing", "$48k")
    out = runtime._tool_forget_fact(brain, "pricing")
    assert "Forgot" in out
    assert cf.resolve_key(brain, "pricing")["value"] is None


def test_forget_unknown_key():
    brain = {"org_name": "T", "items": [], "claims": {}}
    cf.ensure_layers(brain)
    assert "No live fact" in runtime._tool_forget_fact(brain, "nonexistent")


def test_forget_dispatch_marks_mutated():
    brain = {"org_name": "T", "items": [], "claims": {}}
    runtime._tool_add_fact(brain, "P", "pricing", "$1")
    _, mutated = runtime._dispatch_tool("forget_fact", {"key": "pricing"}, brain)
    assert mutated is True


# ── #c: finance / Thai aliases canonicalize ─────────────────────────────────

def test_finance_aliases():
    assert cf.canonical_key("license") == "license_tier"
    assert cf.canonical_key("regulatory_body") == "regulator"
    assert cf.canonical_key("trust_rating") == "trust_score"
    assert cf.canonical_key("kyc") == "compliance"


def test_thai_aliases():
    assert cf.canonical_key("ราคา") == "pricing"
    assert cf.canonical_key("ใบอนุญาต") == "license_tier"
    assert cf.canonical_key("หน่วยงานกำกับ") == "regulator"


def test_pricing_aliases_not_lost():
    # the original English pricing aliases must still work after the finance merge
    assert cf.canonical_key("price") == "pricing"
    assert cf.canonical_key("pricing_model") == "pricing"
    assert cf.canonical_key("listing_fee") == "pricing"


# ── #b: provenance in query_brain ───────────────────────────────────────────

def test_query_brain_includes_source():
    brain = {"org_name": "T", "items": [
        {"category": "P", "key": "pricing", "value": "$48k", "source": "pricing.md"}],
        "claims": {}}
    out = runtime._tool_query_brain(brain, "pricing")
    assert "source" in out and "pricing.md" in out


# ── #4: LLM retry/backoff ───────────────────────────────────────────────────

def test_retryable_status_set():
    assert 429 in agent._RETRYABLE_STATUS    # rate limit
    assert 529 in agent._RETRYABLE_STATUS    # Anthropic overload
    assert 503 in agent._RETRYABLE_STATUS


def test_max_tokens_configurable():
    assert agent._max_tokens({"max_tokens": 4096}) == 4096
    assert agent._max_tokens({}) == agent.DEFAULT_MAX_TOKENS
    assert agent._max_tokens(None) == agent.DEFAULT_MAX_TOKENS
    assert agent._max_tokens({"max_tokens": "bad"}) == agent.DEFAULT_MAX_TOKENS


def test_urlopen_retry_gives_up_after_attempts(monkeypatch):
    import urllib.error
    calls = {"n": 0}
    def boom(req, timeout=0):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 529, "overload", {}, None)
    monkeypatch.setattr(agent.urllib.request, "urlopen", boom)
    monkeypatch.setattr(agent, "_RETRYABLE_STATUS", {529})
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)   # don't actually wait
    try:
        agent._urlopen_retry("req", attempts=3)
        assert False, "should have raised"
    except urllib.error.HTTPError:
        pass
    assert calls["n"] == 3   # retried exactly `attempts` times


# ── #2: locking primitives exist ────────────────────────────────────────────

def test_brain_lock_and_update(tmp_path, monkeypatch):
    from motherflame import core
    monkeypatch.setattr(core, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    core.save_brain({"org_name": "T", "items": [], "claims": {}})
    with core.brain_lock():
        pass  # acquires + releases without error
    core.update_brain(lambda b: b.setdefault("items", []).append(
        {"category": "C", "key": "x", "value": "1"}))
    assert len(core.load_brain()["items"]) == 1
