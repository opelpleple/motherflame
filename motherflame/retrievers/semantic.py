"""Semantic retriever (P1.4) — ranks facts + document chunks by embedding
cosine similarity instead of keyword overlap. Plugs into retrieval.BaseRetriever.

Registered as 'semantic'; keyword stays the default. Activated via
config['retrieval'] = 'semantic'. Uses the embedding provider from config
(hashing by default, openai if the user opts in) with a per-brain vector cache.
"""
from motherflame import retrieval, embeddings, documents


@retrieval.register("semantic")
class SemanticRetriever(retrieval.BaseRetriever):
    name = "semantic"

    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.provider = embeddings.get_provider(self.cfg)

    def search(self, brain: dict, query: str, k: int = 6) -> list:
        if not query.strip():
            return []
        qv = self.provider.embed(query)
        results = []

        # facts
        for it in brain.get("items", []):
            text = f"{it.get('key','')} {it.get('value','')} {it.get('category','')}"
            vec = embeddings.get_or_embed(brain, self.provider, text)
            score = embeddings.cosine(qv, vec)
            if score > 0:
                results.append({
                    "type": "fact", "score": score,
                    "category": it.get("category", ""), "key": it.get("key", ""),
                    "value": it.get("value", ""), "source": it.get("source", ""),
                    "contested": it.get("contested", False),
                })

        # document chunks
        for doc_id, title, idx, chunk in documents.iter_chunks(brain):
            vec = embeddings.get_or_embed(brain, self.provider, f"{title} {chunk}")
            score = embeddings.cosine(qv, vec)
            if score > 0:
                results.append({
                    "type": "chunk", "score": score,
                    "doc_id": doc_id, "title": title, "chunk_index": idx,
                    "text": chunk,
                })

        results.sort(key=lambda r: -r["score"])
        return results[:k]
