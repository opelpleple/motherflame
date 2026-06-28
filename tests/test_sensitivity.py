"""Tests for sensitivity classification + sync guard (L2)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import conflicts as C, documents as D


def test_claim_carries_sensitivity():
    brain = {}
    C.add_claim(brain, "Finance", "arr_target", "15M THB", source="local_memory",
                confidence=0.9, sensitivity="confidential")
    claim = C._live_claims(brain, "arr_target")[0]
    assert claim["sensitivity"] == "confidential"


def test_sensitivity_defaults_public_for_web():
    brain = {}
    C.add_claim(brain, "Company", "tagline", "trust platform",
                source="https://trustfinance.com", confidence=0.8)
    # tagline canonicalizes; fetch by its canonical key
    ck = C.canonical_key("tagline")
    claim = C._live_claims(brain, ck)[0]
    # web → public by default
    assert claim.get("sensitivity", "public") == "public"


def test_canonical_propagates_sensitivity():
    brain = {}
    C.add_claim(brain, "Strategy", "pivot", "Listing model", source="confidential",
                confidence=0.9, sensitivity="confidential")
    C.rebuild_canonical(brain)
    item = next(i for i in brain["items"] if i["key"] == "pivot")
    assert item.get("sensitivity") == "confidential"


def test_document_carries_sensitivity():
    brain = {}
    D.add_document(brain, "Q3 Plan", "internal strategy text", source="memory",
                   sensitivity="confidential")
    doc = list(brain["documents"].values())[0]
    assert doc["sensitivity"] == "confidential"


def test_has_confidential_helper():
    brain = {}
    C.add_claim(brain, "X", "k", "v", source="confidential", confidence=0.9,
                sensitivity="confidential")
    C.rebuild_canonical(brain)
    assert C.has_confidential(brain) is True
