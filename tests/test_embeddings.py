"""Tests for the embedding layer (P1.1–P1.3)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import embeddings


def test_hashing_embedding_deterministic_and_fixed_dim():
    e = embeddings.HashingEmbedding(dim=256)
    a, b = e.embed("ARR target 15M"), e.embed("ARR target 15M")
    assert a == b
    assert len(a) == 256


def test_cosine_similar_text_scores_higher():
    e = embeddings.HashingEmbedding(dim=256)
    q = e.embed("pricing tiers")
    near = embeddings.cosine(q, e.embed("pricing plan tiers cost"))
    far = embeddings.cosine(q, e.embed("office cat adoption policy"))
    assert near > far


def test_cosine_bounds():
    e = embeddings.HashingEmbedding(dim=64)
    v = e.embed("anything")
    assert abs(embeddings.cosine(v, v) - 1.0) < 1e-6   # identical → 1
    assert embeddings.cosine(v, [0.0] * 64) == 0.0     # zero vector → 0, no crash


def test_empty_text_is_safe():
    e = embeddings.HashingEmbedding(dim=32)
    v = e.embed("")
    assert len(v) == 32
    assert all(x == 0.0 for x in v)


def test_get_or_embed_caches(monkeypatch):
    brain = {}
    e = embeddings.HashingEmbedding(dim=64)
    calls = {"n": 0}
    orig = e.embed
    def counting(text):
        calls["n"] += 1
        return orig(text)
    e.embed = counting
    v1 = embeddings.get_or_embed(brain, e, "same text")
    v2 = embeddings.get_or_embed(brain, e, "same text")
    assert v1 == v2
    assert calls["n"] == 1                      # second call hit the cache
    assert len(brain["embeddings"]) == 1

