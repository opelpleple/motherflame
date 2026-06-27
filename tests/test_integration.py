"""Integration tests for the two highest-stakes fixes:
#1 interview answers must survive a rebuild (no data loss)
#2 concurrent git push must not lose a teammate's update
"""
import sys, pathlib, subprocess, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import conflicts as cf, sync


# ── #1: interview routed through claims survives rebuild ────────────────────

def test_interview_claim_survives_rebuild():
    """The data-loss bug: interview facts written straight to items[] vanished
    when rebuild_canonical recomputed items from claims. Now they're claims."""
    b = {"org_name": "T"}
    cf.ensure_layers(b)
    # simulate the (fixed) interview path
    cf.add_claim(b, "Company", "tagline", "We do X", source="interview", confidence=1.0)
    cf.rebuild_canonical(b)
    assert any(i["value"] == "We do X" for i in b["items"])
    # a SECOND rebuild (e.g. later harvest) must NOT drop it
    cf.rebuild_canonical(b)
    assert any(i["value"] == "We do X" for i in b["items"])


def test_interview_beats_keyword_noise():
    """Interview (conf 1.0) should win over a low-confidence keyword claim."""
    b = {"org_name": "T"}
    # use the same key so they compete on one canonical key
    cf.add_claim(b, "Company", "tagline", "garbage line", source="doc.md", confidence=0.4)
    cf.add_claim(b, "Company", "tagline", "We do X", source="interview", confidence=1.0)
    cf.rebuild_canonical(b)
    # find the resolved canonical item (key is canonicalized internally)
    ckey = cf.canonical_key("tagline")
    tagline = next(i for i in b["items"] if i["key"] == ckey)
    assert tagline["value"] == "We do X"


# ── #2: concurrent git push merges instead of clobbering ────────────────────

def _make_bare_remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    return str(bare)


def test_concurrent_push_no_lost_update(tmp_path, monkeypatch):
    """Two machines push different facts to the same remote. The second push
    must MERGE the first's data, not overwrite it."""
    # isolate the sync working dirs per "machine"
    bare = _make_bare_remote(tmp_path)
    monkeypatch.setattr(sync.Path, "home", staticmethod(lambda: tmp_path / "homeA"))

    key = "mf_team_sharedkey"
    # Machine A pushes pricing
    brainA = {"org_name": "T", "items": [], "gaps": [], "claims": {}}
    cf.add_claim(brainA, "P", "pricing", "$48k", source="alice", owner="alice")
    cf.rebuild_canonical(brainA)
    rA = sync.push(brainA, key, "team", git_remote=bare)
    assert rA["ok"], rA.get("error")

    # Machine B (separate home dir → separate clone) pushes team_size
    monkeypatch.setattr(sync.Path, "home", staticmethod(lambda: tmp_path / "homeB"))
    brainB = {"org_name": "T", "items": [], "gaps": [], "claims": {}}
    cf.add_claim(brainB, "Team", "team_size", "12", source="bob", owner="bob")
    cf.rebuild_canonical(brainB)
    rB = sync.push(brainB, key, "team", git_remote=bare)
    assert rB["ok"], rB.get("error")

    # B's pushed brain must now contain BOTH facts (merged, not clobbered)
    pulled = sync.pull(key, "team", git_remote=bare)
    keys = {c_key for c_key in pulled.get("claims", {})}
    assert "pricing" in keys, "alice's fact was lost!"
    assert "team_size" in keys, "bob's fact was lost!"
