"""Regression: two members whose org_name capitalization differs must still
share ONE encrypted blob and sync (bug found via 2-env simulation)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import sync


def test_blob_slug_is_keyed_on_flame_key_not_orgname():
    key = "mf_trustfinance_1c05dcc00b5343ad"
    # same key, differently-cased org names → SAME blob slug
    a = sync._blob_slug("TrustFinance", key)
    b = sync._blob_slug("Trustfinance", key)
    assert a == b


def test_blob_slug_falls_back_to_org_without_key():
    assert sync._blob_slug("Acme", None) == "Acme"
    assert sync._blob_slug("", None) == "org"


def test_two_members_case_mismatch_still_sync(tmp_path, monkeypatch):
    """Full local-backend round trip: member A (TrustFinance) pushes, member B
    (Trustfinance) pulls with the same key — B must see A's data."""
    # isolate the cloud dir
    monkeypatch.setattr(sync, "CLOUD_DIR", tmp_path / "cloud")
    key = "mf_acme_deadbeef"
    brain_a = {"items": [{"key": "ceo", "value": "Opel"}], "claims": {}, "documents": {}}

    sync.push(brain_a, key, "TrustFinance")          # A's capitalization
    pulled = sync.pull(key, "Trustfinance")          # B's capitalization
    assert pulled is not None                        # same blob found
    assert pulled["items"][0]["value"] == "Opel"
