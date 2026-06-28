"""
Motherflame Embeddings — pluggable text→vector providers for semantic search.

Core stays dependency-free: the default `HashingEmbedding` is pure stdlib (hashes
character n-grams into a fixed-dim bag, L2-normalized). It's lower quality than a
real model but needs no key, no network, no cost — so semantic retrieval works
offline out of the box. `OpenAIEmbedding` (in this module) upgrades quality using
the user's own key, and always falls back to hashing on any error so retrieval
never crashes.

Vectors are plain lists of floats; cosine similarity uses stdlib `math`.
"""
import re
import math
import hashlib


def _tokens(text: str):
    return re.findall(r"[a-zA-Z0-9ก-๙]+", (text or "").lower())


def cosine(a, b) -> float:
    """Cosine similarity of two equal-length vectors. 0.0 for a zero vector
    (no direction) instead of a divide-by-zero."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _l2_normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class BaseEmbedding:
    """Contract: embed(text) -> list[float] of fixed length `dim`."""
    name = "base"
    dim = 256

    def embed(self, text: str):
        raise NotImplementedError

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


class HashingEmbedding(BaseEmbedding):
    """Deterministic, dependency-free embedding. Hashes word unigrams + bigrams
    into `dim` buckets (signed hashing trick), then L2-normalizes. Good enough to
    beat keyword overlap on paraphrases; no key, no network."""
    name = "hashing"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str):
        vec = [0.0] * self.dim
        toks = _tokens(text)
        if not toks:
            return vec
        grams = list(toks) + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        return _l2_normalize(vec)


class OpenAIEmbedding(BaseEmbedding):
    """Higher-quality embeddings via the user's own OpenAI key. Batches up to 100
    inputs. ANY failure (no key, network, rate limit) falls back to HashingEmbedding
    so retrieval is never broken by the embedding layer."""
    name = "openai"
    dim = 1536  # text-embedding-3-small

    def __init__(self, cfg: dict, model: str = "text-embedding-3-small"):
        self.cfg = cfg or {}
        self.model = model
        self._fallback = HashingEmbedding(dim=256)

    def _api_key(self):
        return self.cfg.get("agent_api_key") or self.cfg.get("embedding_api_key")

    def embed(self, text: str):
        out = self.embed_batch([text])
        return out[0] if out else self._fallback.embed(text)

    def embed_batch(self, texts):
        key = self._api_key()
        if not key or not texts:
            return [self._fallback.embed(t) for t in texts]
        try:
            import json
            import urllib.request
            from motherflame.agent import _urlopen_retry
            req = urllib.request.Request(
                "https://api.openai.com/v1/embeddings",
                data=json.dumps({"model": self.model, "input": list(texts)}).encode(),
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
            )
            raw = _urlopen_retry(req, timeout=60)
            data = json.loads(raw)
            rows = sorted(data["data"], key=lambda r: r["index"])
            self.dim = len(rows[0]["embedding"]) if rows else self.dim
            return [r["embedding"] for r in rows]
        except Exception:
            # never let embedding failure break retrieval
            return [self._fallback.embed(t) for t in texts]


def get_provider(cfg: dict) -> BaseEmbedding:
    """Pick an embedding provider from config. Default = hashing (safe, offline).
    Set cfg['embedding'] = 'openai' to use the user's key."""
    cfg = cfg or {}
    choice = (cfg.get("embedding") or "hashing").lower()
    if choice == "openai":
        return OpenAIEmbedding(cfg)
    return HashingEmbedding(dim=cfg.get("embedding_dim", 256))


def _cache_key(provider: BaseEmbedding, text: str) -> str:
    return hashlib.sha1(f"{provider.name}:{provider.dim}:{text}".encode()).hexdigest()


def get_or_embed(brain: dict, provider: BaseEmbedding, text: str):
    """Return the embedding for `text`, caching it in brain['embeddings'] keyed by
    a (provider, content) hash so unchanged items are never re-embedded."""
    store = brain.setdefault("embeddings", {})
    ck = _cache_key(provider, text)
    if ck in store:
        return store[ck]
    vec = provider.embed(text)
    store[ck] = vec
    return vec

