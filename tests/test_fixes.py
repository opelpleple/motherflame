"""Tests for this round's fixes: claims cap, schema version, MCP read-only,
PDF reader fallback, and the runtime/mcp tool paths that had no coverage."""
import sys, pathlib, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import conflicts as cf, mcp_server, runtime


# ── schema version + claims cap (#5/#7) ─────────────────────────────────────

def test_schema_version_stamped():
    b = {}
    cf.ensure_layers(b)
    assert b["schema_version"] == cf.SCHEMA_VERSION


def test_prune_caps_claim_growth():
    b = {"org": "T"}
    # 30 low-value claims for one key from distinct sources
    for i in range(30):
        cf.add_claim(b, "P", "pricing", f"${i}k", source=f"s{i}", confidence=0.5)
    cf.prune_claims(b)
    assert len(b["claims"]["pricing"]) <= cf.MAX_CLAIMS_PER_KEY


def test_prune_protects_owner_and_interview():
    b = {"org": "T"}
    cf.set_owner(b, "pricing", "cfo")
    cf.add_claim(b, "P", "pricing", "$99k", source="x", owner="cfo", confidence=0.9)
    cf.add_claim(b, "P", "pricing", "$50k", source="interview", confidence=1.0)
    for i in range(30):
        cf.add_claim(b, "P", "pricing", f"${i}", source=f"s{i}", confidence=0.4)
    cf.prune_claims(b)
    vals = [c["value"] for c in b["claims"]["pricing"]]
    assert "$99k" in vals      # owner claim survives
    assert "$50k" in vals      # interview claim survives


def test_prune_keeps_tombstones():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$1", source="old")
    cf.retract_claim(b, "pricing", value="$1")
    for i in range(30):
        cf.add_claim(b, "P", "pricing", f"${i}k", source=f"s{i}", confidence=0.4)
    cf.prune_claims(b)
    retracted = [c for c in b["claims"]["pricing"] if c.get("retracted")]
    assert len(retracted) >= 1   # tombstone never pruned


# ── MCP read-only (#10) ─────────────────────────────────────────────────────

def test_mcp_readonly_blocks_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("MOTHERFLAME_MCP_READONLY", "1")
    assert mcp_server._readonly() is True
    # add_fact must refuse
    from motherflame import core
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    out = mcp_server._run_tool("add_fact", {"category": "P", "key": "x", "value": "y"})
    assert "read-only" in out.lower()


def test_mcp_readonly_off_by_default(monkeypatch):
    monkeypatch.delenv("MOTHERFLAME_MCP_READONLY", raising=False)
    # with no env and no config flag, writes allowed
    monkeypatch.setattr("motherflame.core.load_config", lambda: {})
    assert mcp_server._readonly() is False


def test_mcp_query_still_works_readonly(monkeypatch, tmp_path):
    monkeypatch.setenv("MOTHERFLAME_MCP_READONLY", "1")
    from motherflame import core
    monkeypatch.setattr(core, "BRAIN_FILE", tmp_path / "brain.json")
    core.save_brain({"org_name": "T", "items": [
        {"category": "P", "key": "pricing", "value": "$48k"}], "claims": {}})
    out = mcp_server._run_tool("query_brain", {"topic": "pricing"})
    assert "48k" in out


# ── runtime tool paths (#3 — previously untested) ───────────────────────────

def test_runtime_query_brain_finds_match():
    brain = {"items": [{"category": "P", "key": "pricing", "value": "$48k"}], "claims": {}}
    out = runtime._tool_query_brain(brain, "pricing")
    assert "48k" in out


def test_runtime_query_brain_empty():
    out = runtime._tool_query_brain({"items": [], "claims": {}}, "anything")
    assert "empty" in out.lower()


def test_runtime_add_fact():
    brain = {"items": [], "claims": {}}
    runtime._tool_add_fact(brain, "Product", "main_product", "Widget")
    assert any(i["value"] == "Widget" for i in brain["items"])


def test_mcp_tool_defs_shape():
    defs = mcp_server._tool_defs()
    names = {d["name"] for d in defs}
    assert names == {"query_brain", "list_facts", "add_fact", "forget_fact", "verify_fact"}
    for d in defs:
        assert "description" in d and "inputSchema" in d


def test_mcp_handle_initialize():
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["result"]["serverInfo"]["name"] == "motherflame"
