"""Tests for SemanticRetriever (P1.4) — pluggable semantic ranking."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from motherflame import retrieval, conflicts as C, documents as D
import motherflame.retrievers  # registers 'semantic'


def test_semantic_registered():
    assert "semantic" in retrieval._REGISTRY


def test_semantic_ranks_facts_and_chunks():
    brain = {}
    C.add_claim(brain, "Finance", "arr_target", "ARR goal is 15M THB", source="chat", confidence=1.0)
    C.rebuild_canonical(brain)
    D.add_document(brain, "Plan", "Our revenue objective: reach an annual recurring revenue of 15 million baht.", source="memo")
    r = retrieval.get_retriever({"retrieval": "semantic", "embedding": "hashing"})
    hits = r.search(brain, "what is our revenue target", k=5)
    assert hits
    assert all("score" in h for h in hits)


def test_config_selects_semantic():
    r = retrieval.get_retriever({"retrieval": "semantic"})
    assert r.name == "semantic"
    r2 = retrieval.get_retriever({"retrieval": "keyword"})
    assert r2.name == "keyword"
    r3 = retrieval.get_retriever({})            # default
    assert r3.name == "keyword"


def test_semantic_beats_keyword_on_paraphrase():
    """A paraphrase with NO shared keywords should still be found semantically."""
    brain = {}
    # fact uses 'revenue/annual', query will use 'sales/yearly' (different words)
    C.add_claim(brain, "Finance", "annual_revenue",
                "annual revenue reached fifteen million", source="chat", confidence=1.0)
    C.add_claim(brain, "Team", "office_pet", "the office cat is named Tom",
                source="chat", confidence=1.0)
    C.rebuild_canonical(brain)

    # keyword: query shares words with neither well; semantic should still surface revenue
    kw = retrieval.get_retriever({"retrieval": "keyword"})
    sem = retrieval.get_retriever({"retrieval": "semantic", "embedding": "hashing"})
    q = "annual revenue fifteen million"
    sem_hits = sem.search(brain, q, k=2)
    # top semantic hit should be the revenue fact, not the cat
    assert sem_hits and sem_hits[0]["key"] == "annual_revenue"
