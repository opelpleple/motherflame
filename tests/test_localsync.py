"""Tests for local knowledge ingestion (L4/L5)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import localsync, conflicts as C, core, cli


def test_classify_memory_is_confidential(tmp_path):
    p = tmp_path / ".claude" / "projects" / "x" / "memory" / "MEMORY.md"
    meta = localsync.classify(p)
    assert meta["source"] == "local_memory"
    assert meta["sensitivity"] == "confidential"


def test_classify_plain_note_is_internal(tmp_path):
    p = tmp_path / "notes" / "meeting.md"
    meta = localsync.classify(p)
    assert meta["sensitivity"] == "internal"


def test_discover_finds_markdown(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "c.png").write_bytes(b"\x89PNG")
    found = localsync.discover(str(tmp_path))
    names = {p.name for p in found}
    assert "a.md" in names and "b.txt" in names
    assert "c.png" not in names


def test_absorb_stores_document_without_ai(tmp_path):
    (tmp_path / "plan.md").write_text("Our 2026 pivot: done-for-you Listing model. " * 10)
    brain = {}
    summary = localsync.absorb(brain, {}, str(tmp_path), extract=True)  # no AI key
    assert summary["documents"] == 1
    assert summary["facts_staged"] == 0          # no key → docs only
    doc = list(brain["documents"].values())[0]
    assert doc["sensitivity"] == "internal"


def test_absorb_tags_confidential_memory(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "MEMORY.md").write_text("ARR target 15M THB confidential strategy. " * 5)
    brain = {}
    summary = localsync.absorb(brain, {}, str(tmp_path))
    assert summary["confidential_docs"] >= 1
    assert C.has_confidential(brain) is True


def test_absorb_extracts_to_review_with_ai(tmp_path, monkeypatch):
    (tmp_path / "doc.md").write_text("The CEO is Opel. Team is 34 people. " * 5)
    from motherflame import agent
    monkeypatch.setattr(agent, "llm_research_extract",
                        lambda cfg, text, src: [
                            {"category": "Team", "key": "team_size", "value": "34", "confidence": 0.9}])
    brain = {}
    cfg = {"provider": "openai", "agent_api_key": "x"}
    summary = localsync.absorb(brain, cfg, str(tmp_path))
    assert summary["facts_staged"] == 1
    # staged to pending (review), NOT straight into canonical
    assert len(brain.get("pending", [])) == 1
    C.rebuild_canonical(brain)
    assert not any(i["key"] == "team_size" for i in brain.get("items", []))


def test_absorb_wired_in_cli():
    import inspect
    assert callable(core.cmd_absorb)
    assert 'cmd == "absorb"' in inspect.getsource(cli.main)
