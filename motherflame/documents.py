"""
Motherflame Documents — first-class storage for long-form org knowledge.

Facts are short, looked-up values. But a real company also has *documents*: a
3-page strategy memo, a quarter of OKRs, a runbook. Cramming those into a 300-char
fact value loses everything. This module stores full documents alongside facts.

Design rule (important): **a document is a SNAPSHOT, a fact is the TRUTH.**
Documents are reference material — point-in-time text you can re-read and cite.
Facts (in conflicts.py) remain the single resolved source of truth. A doc never
overrides a fact; it's evidence a human/agent can read. This avoids creating a
second, conflicting "truth" layer.

Storage lives in brain["documents"] = { doc_id: {meta + chunks} }. Documents are
chunked on add so retrieval can return only the relevant passage of a long plan
instead of the whole thing.

Pure stdlib.
"""
import re
import hashlib
from datetime import datetime

CHUNK_CHARS = 1200          # ~300 tokens per chunk
CHUNK_OVERLAP = 150         # keep context across chunk boundaries


def ensure_documents(brain: dict) -> dict:
    brain.setdefault("documents", {})
    return brain


def _doc_id(title: str, text: str) -> str:
    h = hashlib.sha1(f"{title}\n{text[:500]}".encode()).hexdigest()[:12]
    return f"doc_{h}"


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks, preferring paragraph boundaries so we
    don't cut a sentence/table in half."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    # split on blank lines first, then pack paragraphs into ~size chunks
    paras = re.split(r"\n\s*\n", text)
    chunks, cur = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            # a single paragraph bigger than size → hard-split it
            if len(p) > size:
                for i in range(0, len(p), size - overlap):
                    chunks.append(p[i:i + size])
                cur = ""
            else:
                cur = p
    if cur:
        chunks.append(cur)
    return chunks


def add_document(brain: dict, title: str, text: str, source: str = "unknown",
                 category: str = "Document", sensitivity: str = None) -> str:
    """Store a long document (chunked). Returns its doc_id. Idempotent by
    content hash — re-adding the same doc updates it in place."""
    ensure_documents(brain)
    text = (text or "").strip()
    if not text:
        return ""
    if not sensitivity:
        s = (source or "").lower()
        sensitivity = "public" if s.startswith(("http://", "https://")) else "internal"
    did = _doc_id(title, text)
    brain["documents"][did] = {
        "doc_id": did,
        "title": title or "(untitled)",
        "source": source,
        "category": category,
        "sensitivity": sensitivity,
        "added_at": datetime.now().isoformat(),
        "char_len": len(text),
        "chunks": chunk_text(text),
    }
    return did


def get_document(brain: dict, doc_id: str) -> dict:
    return brain.get("documents", {}).get(doc_id)


def list_documents(brain: dict) -> list:
    """Lightweight listing (no chunk bodies) for display."""
    out = []
    for d in brain.get("documents", {}).values():
        out.append({k: d[k] for k in ("doc_id", "title", "source", "category",
                                       "added_at", "char_len")})
    return sorted(out, key=lambda d: d["added_at"], reverse=True)


def remove_document(brain: dict, doc_id: str) -> bool:
    return brain.get("documents", {}).pop(doc_id, None) is not None


def iter_chunks(brain: dict):
    """Yield (doc_id, title, chunk_index, chunk_text) across all documents —
    the unit retrieval ranks over."""
    for d in brain.get("documents", {}).values():
        for i, ch in enumerate(d.get("chunks", [])):
            yield d["doc_id"], d["title"], i, ch
