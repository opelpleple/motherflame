"""Tests for universal (OSS-core) features: trust scoring, temporality,
verify, review queue, connector interface, eval harness."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import conflicts as cf, trust, connectors, eval as mf_eval
from datetime import datetime, timedelta


# ── trust scoring ───────────────────────────────────────────────────────────

def test_verified_beats_high_confidence_llm():
    b = {"org_name": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="doc.md", confidence=0.95)
    cf.add_claim(b, "P", "pricing", "$60k", source="chat", confidence=0.9)
    cf.verify_claim(b, "pricing", "$60k", by="ceo")
    assert cf.resolve_key(b, "pricing")["value"] == "$60k"


def test_trust_score_components():
    fresh_verified = {"value": "x", "source": "chat", "confidence": 0.9,
                      "verified": True, "ts": datetime.now().isoformat()}
    old_llm = {"value": "y", "source": "doc.md", "confidence": 0.9,
               "ts": (datetime.now() - timedelta(days=400)).isoformat()}
    assert trust.trust_score(fresh_verified) > trust.trust_score(old_llm)


def test_staleness_decays():
    fresh = {"value": "a", "source": "doc.md", "confidence": 0.8, "ts": datetime.now().isoformat()}
    stale = {"value": "a", "source": "doc.md", "confidence": 0.8,
             "ts": (datetime.now() - timedelta(days=365)).isoformat()}
    assert trust.trust_score(fresh) > trust.trust_score(stale)


def test_keyword_authority_lowest():
    kw = {"value": "x", "source": "notes.md", "confidence": 0.4}
    chat = {"value": "x", "source": "chat", "confidence": 0.4}
    assert trust._source_authority(kw) < trust._source_authority(chat)


# ── temporality ──────────────────────────────────────────────────────────────

def test_as_of_filters_by_validity():
    b = {"org_name": "T"}
    cf.add_claim(b, "P", "pricing", "$40k", source="chat", confidence=1.0,
                 valid_from="2024-01-01", valid_until="2024-12-31")
    cf.add_claim(b, "P", "pricing", "$50k", source="chat", confidence=1.0,
                 valid_from="2025-01-01")
    assert cf.resolve_key(b, "pricing", as_of="2024-06-01")["value"] == "$40k"
    assert cf.resolve_key(b, "pricing", as_of="2025-06-01")["value"] == "$50k"


# ── review queue ─────────────────────────────────────────────────────────────

def test_review_queue_gates_machine_claims():
    b = {"org_name": "T"}
    cf.ensure_layers(b)
    assert cf.stage_or_add(b, "P", "pricing", "$48k", source="doc.md", review=True) == "pending"
    assert cf.stage_or_add(b, "T", "team_size", "12", source="chat", review=True) == "added"
    assert len(cf.list_pending(b)) == 1


def test_review_approve_promotes():
    b = {"org_name": "T"}
    cf.stage_or_add(b, "P", "pricing", "$48k", source="doc.md", review=True)
    assert cf.approve_pending(b) == 1
    assert cf.resolve_key(b, "pricing")["value"] == "$48k"
    assert len(cf.list_pending(b)) == 0


def test_review_reject_discards():
    b = {"org_name": "T"}
    cf.stage_or_add(b, "P", "pricing", "$48k", source="doc.md", review=True)
    assert cf.reject_pending(b) == 1
    assert cf.resolve_key(b, "pricing")["value"] is None


def test_review_off_by_default():
    b = {"org_name": "T"}
    # review=False (default) → machine claim goes straight in
    assert cf.stage_or_add(b, "P", "pricing", "$48k", source="doc.md", review=False) == "added"


# ── connector interface ──────────────────────────────────────────────────────

def test_local_files_connector(tmp_path):
    (tmp_path / "a.md").write_text("# Company\nWe do widgets")
    (tmp_path / "b.txt").write_text("pricing: $99/mo")
    docs = connectors.harvest_documents("local_files",
                                        {"folder": str(tmp_path), "globs": ["*.md", "*.txt"]})
    assert len(docs) == 2
    assert all(isinstance(d, connectors.Document) for d in docs)
    assert {d.title for d in docs} == {"a.md", "b.txt"}


def test_connector_registry():
    assert "local_files" in connectors.available_connectors()
    conn = connectors.get_connector("local_files", {"folder": "."})
    assert conn.name == "local_files"


def test_custom_connector_registration():
    @connectors.register
    class DummyConnector(connectors.BaseConnector):
        name = "dummy_test"
        def fetch(self):
            yield connectors.Document(title="t", text="hello", source_id="dummy:1")
    docs = connectors.harvest_documents("dummy_test")
    assert docs[0].text == "hello"


def test_unknown_connector_raises():
    try:
        connectors.get_connector("nonexistent")
        assert False
    except KeyError:
        pass


# ── eval harness ─────────────────────────────────────────────────────────────

def test_eval_precision_and_recall():
    b = {"org_name": "T", "items": [
        {"category": "P", "key": "pricing", "value": "$48k/year"},
        {"category": "T", "key": "team_size", "value": "12 people"},
        {"category": "S", "key": "market", "value": "SEA fintech"},
    ], "claims": {}}
    golden = [
        {"question": "what is our pricing", "expect": "pricing"},
        {"question": "how big is the team", "expect": "team_size"},
    ]
    report = mf_eval.run(b, golden, k=2)
    assert report["n"] == 2
    assert report["hit_rate"] >= 0.5     # at least pricing should hit on keyword
    assert "precision_at_k" in report and "recall" in report


def test_eval_alias_aware():
    # expecting an alias key should still count as a hit (canonicalized)
    b = {"org_name": "T", "items": [{"category": "P", "key": "pricing", "value": "$48k"}], "claims": {}}
    report = mf_eval.run(b, [{"question": "pricing", "expect": "price"}], k=1)
    assert report["hit_rate"] == 1.0     # 'price' canonicalizes to 'pricing'
