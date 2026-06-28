"""
Motherflame Retrieval — pluggable ranking over facts + document chunks.

Why an interface: keyword ranking is fine for a small brain, but a big company's
brain (thousands of facts + long documents) needs semantic search to find the
*right* passage. Rather than bake one strategy in, retrieval goes through a
`BaseRetriever` contract. The default `KeywordRetriever` is pure stdlib (works
offline, zero deps). A semantic/vector retriever can register and take over
without touching the rest of the code — that's the honest path to scale.

A retriever ranks over two unit types:
  - facts        (short canonical key→value)
  - doc chunks   (passages of long documents, from documents.iter_chunks)
and returns a unified, ranked list the agent/query layer can use.
"""
import re
from collections import Counter

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
    "and", "or", "our", "we", "what", "which", "how", "do", "does", "this", "that",
    "with", "as", "by", "at", "it", "its", "be", "i", "you", "your",
}

_REGISTRY = {}
_ACTIVE = "keyword"


def register(name):
    def deco(cls):
        _REGISTRY[name] = cls
        return cls
    return deco


def set_active(name: str):
    global _ACTIVE
    if name in _REGISTRY:
        _ACTIVE = name


def get_retriever(cfg=None):
    # lazy-import the retrievers package so 'semantic' registers without a cycle
    try:
        import motherflame.retrievers  # noqa: F401
    except Exception:
        pass
    cfg = cfg or {}
    name = (cfg.get("retrieval") or _ACTIVE)
    cls = _REGISTRY.get(name, _REGISTRY["keyword"])
    # semantic retriever takes cfg (for the embedding provider); keyword doesn't
    try:
        return cls(cfg)
    except TypeError:
        return cls()


def search(brain: dict, query: str, k: int = 6, cfg=None) -> list:
    """Convenience: rank with the active retriever (or the one named in cfg)."""
    return get_retriever(cfg).search(brain, query, k=k)


def _tokens(text: str) -> list:
    toks = re.findall(r"[a-zA-Z0-9ก-๙]+", (text or "").lower())
    return [t for t in toks if t not in _STOPWORDS and len(t) > 1]


class BaseRetriever:
    """Contract: rank facts + document chunks against a query.
    Implement `search`; return a list of dicts each like
    {type: 'fact'|'chunk', score, ...payload}."""
    name = "base"

    def search(self, brain: dict, query: str, k: int = 6) -> list:
        raise NotImplementedError


@register("keyword")
class KeywordRetriever(BaseRetriever):
    """Default: lexical overlap with stopword filtering. Ranks facts and doc
    chunks together so a long plan's relevant passage can outrank a thin fact."""
    name = "keyword"

    def search(self, brain: dict, query: str, k: int = 6) -> list:
        from motherflame import documents
        q = Counter(_tokens(query))
        if not q:
            return []
        results = []

        # facts
        for it in brain.get("items", []):
            text = f"{it.get('key','')} {it.get('value','')} {it.get('category','')}"
            score = self._overlap(q, _tokens(text))
            if score > 0:
                results.append({
                    "type": "fact", "score": score,
                    "category": it.get("category", ""), "key": it.get("key", ""),
                    "value": it.get("value", ""), "source": it.get("source", ""),
                    "contested": it.get("contested", False),
                })

        # document chunks
        for doc_id, title, idx, chunk in documents.iter_chunks(brain):
            score = self._overlap(q, _tokens(f"{title} {chunk}"))
            if score > 0:
                results.append({
                    "type": "chunk", "score": score,
                    "doc_id": doc_id, "title": title, "chunk_index": idx,
                    "text": chunk,
                })

        results.sort(key=lambda r: -r["score"])
        return results[:k]

    @staticmethod
    def _overlap(qcount: Counter, doc_tokens: list) -> float:
        if not doc_tokens:
            return 0.0
        dset = set(doc_tokens)
        hits = sum(c for t, c in qcount.items() if t in dset)
        # normalize a little by query size so longer queries don't inflate
        return hits / (sum(qcount.values()) ** 0.5)
