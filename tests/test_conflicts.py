"""Tests for the conflict manager — the heart of single-source-of-truth."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import conflicts as cf


def test_claims_never_clobber():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a", owner="al")
    cf.add_claim(b, "P", "pricing", "$50k", source="b", owner="bo")
    assert len(b["claims"]["pricing"]) == 2


def test_dedup_same_value_source():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a")
    cf.add_claim(b, "P", "pricing", "$48k", source="a")
    assert len(b["claims"]["pricing"]) == 1


def test_key_canonicalization():
    assert cf.canonical_key("price") == "pricing"
    assert cf.canonical_key("pricing_model") == "pricing"
    assert cf.canonical_key("Pricing-Tiers") == "pricing"
    assert cf.canonical_key("headcount") == "team_size"


def test_aliases_collapse_to_one_key():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a")
    cf.add_claim(b, "P", "price", "$50k", source="b")
    cf.add_claim(b, "P", "pricing_model", "$52k", source="c")
    assert list(b["claims"].keys()) == ["pricing"]
    assert len(b["claims"]["pricing"]) == 3


def test_value_equality_money():
    assert cf._norm("$48k") == cf._norm("48,000")
    assert cf._norm("$2M") == cf._norm("2,000,000")
    assert cf._norm("USD 48000") == cf._norm("$48k")
    assert cf._norm("$48k") != cf._norm("$50k")


def test_ladder_manual_beats_all():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a", owner="al")
    cf.add_claim(b, "P", "pricing", "$60k", source="b", owner="cfo")
    cf.set_owner(b, "pricing", "cfo")
    assert cf.resolve_key(b, "pricing")["value"] == "$60k"  # owner
    cf.manual_resolve(b, "pricing", "$55k", by="ceo")
    assert cf.resolve_key(b, "pricing")["value"] == "$55k"  # manual wins


def test_ladder_consensus_beats_recency():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a", confidence=0.5)
    cf.add_claim(b, "P", "pricing", "$48k", source="b", confidence=0.5)
    cf.add_claim(b, "P", "pricing", "$99k", source="c", confidence=0.99)
    assert cf.resolve_key(b, "pricing")["value"] == "$48k"


def test_tombstone_survives_and_hides():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a")
    cf.add_claim(b, "P", "pricing", "$50k", source="b")
    n = cf.retract_claim(b, "pricing", value="$48k")
    assert n == 1
    assert cf.resolve_key(b, "pricing")["value"] == "$50k"


def test_bulk_auto_resolve():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a", owner="al")
    cf.add_claim(b, "P", "pricing", "$60k", source="b", owner="cfo")
    cf.set_owner(b, "pricing", "cfo")
    result = cf.auto_resolve_all(b)
    assert any(a["key"] == "pricing" for a in result["auto_resolved"])


def test_rebuild_canonical_single_source():
    b = {"org": "T"}
    cf.add_claim(b, "P", "pricing", "$48k", source="a", owner="al")
    cf.add_claim(b, "P", "pricing", "$50k", source="b", owner="bo")
    cf.rebuild_canonical(b)
    pricing = [i for i in b["items"] if i["key"] == "pricing"]
    assert len(pricing) == 1
    assert pricing[0]["contested"] is True
