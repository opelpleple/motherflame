"""Tests for scaling to large orgs: document store, dynamic categories,
chunked + pluggable retrieval."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import documents as D, conflicts as C, retrieval as R, core, cli, mcp_server


# ── A: documents ────────────────────────────────────────────────────────────

def test_long_doc_not_truncated():
    brain = {}
    plan = "STRATEGY\n\n" + ("We expand into SEA fintech. ARR target 15M THB. " * 60)
    did = D.add_document(brain, "Q3 Plan", plan, source="memo")
    doc = D.get_document(brain, did)
    assert doc["char_len"] > 1000           # the old 300-char cap is gone
    assert len(doc["chunks"]) > 1           # chunked for retrieval
    assert "".join(doc["chunks"]).count("ARR target") > 5


def test_add_document_idempotent():
    brain = {}
    a = D.add_document(brain, "Plan", "same text body here", source="x")
    b = D.add_document(brain, "Plan", "same text body here", source="x")
    assert a == b
    assert len(brain["documents"]) == 1


def test_chunk_prefers_paragraphs():
    text = "\n\n".join(f"Paragraph {i} with some content." for i in range(50))
    chunks = D.chunk_text(text, size=200)
    assert len(chunks) > 1
    assert all(len(c) <= 400 for c in chunks)   # overlap-bounded


def test_list_and_remove_document():
    brain = {}
    did = D.add_document(brain, "Doc", "body text", source="s")
    assert len(D.list_documents(brain)) == 1
    assert D.remove_document(brain, did) is True
    assert D.list_documents(brain) == []


# ── B: dynamic categories ───────────────────────────────────────────────────

def test_category_collapse():
    assert C.canonical_category("Eng") == "Engineering"
    assert C.canonical_category("engineering") == "Engineering"
    assert C.canonical_category("dev") == "Engineering"
    assert C.canonical_category("compliance") == "Legal"


def test_unknown_category_kept_titlecased():
    assert C.canonical_category("procurement") == "Procurement"
    assert C.canonical_category("data science") == "Data Science"


def test_add_claim_canonicalizes_category():
    brain = {}
    C.add_claim(brain, "eng", "stack", "Python", source="chat", confidence=1.0)
    C.rebuild_canonical(brain)
    cats = {i["category"] for i in brain["items"]}
    assert "Engineering" in cats


# ── C/D: retrieval interface ────────────────────────────────────────────────

def test_keyword_retriever_ranks_facts_and_chunks():
    brain = {}
    C.add_claim(brain, "Finance", "arr_target", "15M THB", source="chat", confidence=1.0)
    C.rebuild_canonical(brain)
    D.add_document(brain, "Q3 Plan",
                   "Our SEA expansion plan: hit an ARR target of 15M THB by Q3.",
                   source="memo")
    hits = R.search(brain, "ARR target SEA expansion", k=5)
    types = {h["type"] for h in hits}
    assert "chunk" in types or "fact" in types
    assert all("score" in h for h in hits)


def test_retriever_registry_pluggable():
    @R.register("dummy")
    class Dummy(R.BaseRetriever):
        name = "dummy"
        def search(self, brain, query, k=6):
            return [{"type": "fact", "score": 1.0, "key": "x", "value": "y"}]
    R.set_active("dummy")
    try:
        out = R.search({}, "anything")
        assert out and out[0]["key"] == "x"
    finally:
        R.set_active("keyword")


def test_docs_and_mcp_doc_tools_wired():
    import inspect
    assert callable(core.cmd_docs)
    assert 'cmd == "docs"' in inspect.getsource(cli.main)
    names = {d["name"] for d in mcp_server._tool_defs()}
    assert {"list_documents", "get_document"} <= names
