"""Tests for OpenAIEmbedding provider (P1.2) — mocked, no live key."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import embeddings, agent


def test_openai_embedding_uses_api_when_key_present(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=60, attempts=4):
        captured["called"] = True
        return json.dumps({"data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]})
    monkeypatch.setattr(agent, "_urlopen_retry", fake_urlopen)

    e = embeddings.OpenAIEmbedding({"agent_api_key": "sk-test"})
    out = e.embed_batch(["a", "b"])
    assert captured.get("called") is True
    assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_openai_embedding_falls_back_without_key():
    e = embeddings.OpenAIEmbedding({})          # no key
    v = e.embed("pricing tiers")
    # falls back to hashing (256-dim), not a crash
    assert len(v) == 256


def test_openai_embedding_falls_back_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(agent, "_urlopen_retry", boom)
    e = embeddings.OpenAIEmbedding({"agent_api_key": "sk-test"})
    v = e.embed("anything")
    assert len(v) == 256                        # hashing fallback dim


def test_get_provider_selects_by_config():
    assert embeddings.get_provider({"embedding": "hashing"}).name == "hashing"
    assert embeddings.get_provider({"embedding": "openai",
                                    "agent_api_key": "x"}).name == "openai"
    assert embeddings.get_provider({}).name == "hashing"   # safe default
