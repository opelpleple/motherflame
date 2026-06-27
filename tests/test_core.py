"""Tests for the token budget manager, redaction, sync crypto, and identity."""
import sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import tokens as tk, redact, sync, conflicts as cf


# ── tokens ──────────────────────────────────────────────────────────────────

def test_estimate_tokens():
    assert tk.estimate_tokens("") == 0
    assert tk.estimate_tokens("a" * 40) == 10


def test_fit_respects_budget():
    facts = [{"category": "C", "key": f"k{i}", "value": "x" * 100, "confidence": 0.7}
             for i in range(50)]
    fit = tk.fit_facts(facts, query="k3", budget_tokens=100)
    assert fit["included"] >= 1
    assert fit["dropped"] > 0


def test_relevance_ranking():
    facts = [
        {"category": "Product", "key": "pricing", "value": "$48k", "confidence": 0.9},
        {"category": "Team", "key": "team_size", "value": "12", "confidence": 0.8},
    ]
    terms = tk._tokenize("pricing")
    assert tk.score_fact(facts[0], terms) > tk.score_fact(facts[1], terms)


def test_compress_long_value():
    fit = tk.fit_facts([{"category": "C", "key": "k", "value": "y" * 1000, "confidence": 0.9}],
                       budget_tokens=1500)
    assert "…" in fit["lines"][0]
    assert len(fit["lines"][0]) < 400


def test_big_brain_stays_bounded():
    facts = [{"category": "C", "key": f"f{i}", "value": "detail " * 20, "confidence": 0.7}
             for i in range(500)]
    fit = tk.fit_facts(facts, query="f3", budget_tokens=1500)
    assert fit["tokens_used"] <= 1700  # bounded, not 500 facts


# ── redaction ─────────────────────────────────────────────────────────────

def test_redact_pii():
    txt = "Email john@acme.com, key sk-abcdefghij1234567890, price $99/mo"
    red, counts = redact.redact(txt)
    assert "john@acme.com" not in red
    assert "sk-abcdefghij1234567890" not in red
    assert "99" in red  # business signal kept
    assert counts.get("EMAIL", 0) >= 1


def test_redact_disabled_passthrough():
    txt = "email a@b.com"
    assert redact.redact(txt, enabled=False)[0] == txt


# ── sync crypto ─────────────────────────────────────────────────────────────

def test_crypto_roundtrip():
    blob = sync.encrypt(b"secret data", "mf_key")
    assert b"secret" not in blob
    assert sync.decrypt(blob, "mf_key") == b"secret data"


def test_crypto_wrong_key_fails():
    blob = sync.encrypt(b"secret", "mf_key")
    try:
        sync.decrypt(blob, "wrong_key")
        assert False, "should have raised"
    except ValueError:
        pass


def test_crypto_tamper_detected():
    blob = bytearray(sync.encrypt(b"secret data here", "mf_key"))
    blob[70] ^= 0xFF
    try:
        sync.decrypt(bytes(blob), "mf_key")
        assert False, "should have raised"
    except ValueError:
        pass


def test_merge_unions_no_loss():
    peter = {"items": [{"category": "P", "key": "pricing", "value": "$48k",
                        "source": "p", "harvested_at": "2026-01-01", "confidence": 0.8}], "gaps": []}
    alice = {"items": [{"category": "P", "key": "pricing", "value": "$50k",
                        "source": "a", "harvested_at": "2026-02-01", "confidence": 0.8}], "gaps": []}
    merged, n_new = sync.merge_brains(peter, alice)
    vals = [c["value"] for c in merged["claims"]["pricing"]]
    assert "$48k" in vals and "$50k" in vals
    assert n_new == 1


def test_local_push_pull_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "CLOUD_DIR", tmp_path / "cloud")
    brain = {"org_name": "T", "items": [{"category": "P", "key": "k", "value": "v",
             "harvested_at": "2026-01-01"}], "gaps": []}
    receipt = sync.push(brain, "mf_key", "T")
    assert receipt["ok"]
    pulled = sync.pull("mf_key", "T")
    assert pulled["items"][0]["key"] == "k"
