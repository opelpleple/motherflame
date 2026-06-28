"""Tests for source-authority tiers + the public-web-can't-override-confidential rule (L1)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import trust, conflicts as C


def test_local_memory_outranks_public_web():
    local = {"source": "local_memory", "confidence": 0.8, "ts": "2026-06-01T00:00:00"}
    web = {"source": "https://trustfinance.com", "confidence": 0.9, "ts": "2026-06-01T00:00:00"}
    assert trust.trust_score(local) > trust.trust_score(web)


def test_confidential_interview_is_top_tier():
    conf = {"source": "confidential", "confidence": 0.8, "ts": "2026-06-01T00:00:00"}
    web = {"source": "web", "confidence": 1.0, "ts": "2026-06-01T00:00:00"}
    assert trust.trust_score(conf) > trust.trust_score(web)


def test_public_web_cannot_override_confidential_in_resolution():
    """A fresh public-web claim must NOT beat an older confidential one for the
    same key — public marketing copy shouldn't overwrite internal truth."""
    brain = {}
    # confidential says the company pivoted; older
    C.add_claim(brain, "Strategy", "business_model",
                "done-for-you Listing (SaaS retired)", source="confidential",
                confidence=0.85, ts="2026-01-01T00:00:00")
    # public web says subscription; newer but low authority
    C.add_claim(brain, "Strategy", "business_model",
                "subscription SaaS", source="https://trustfinance.com",
                confidence=0.9, ts="2026-06-01T00:00:00")
    C.rebuild_canonical(brain)
    val = next(i["value"] for i in brain["items"] if i["key"] == "business_model")
    assert "Listing" in val          # confidential wins despite being older
    assert "subscription" not in val.split("⚠")[0]


def test_authority_from_source_prefix():
    assert trust._source_authority({"source": "local_memory"}) >= 0.9
    assert trust._source_authority({"source": "confidential"}) >= 0.95
    assert trust._source_authority({"source": "https://x.com"}) <= 0.6
