"""
Motherflame Eval — measure whether the Org Brain actually helps.

A brain is only worth feeding to agents if it retrieves the *right* facts. This
harness runs a set of golden questions against the brain's retrieval and reports
precision@k and recall — so you can tell whether a change (new aliases, trust
weighting, semantic retrieval) improved or regressed answer quality, instead of
guessing.

Golden set is plain JSON/YAML-ish: a list of {question, expect} where `expect`
is the key(s) that SHOULD surface for that question. No LLM calls, no deps —
pure retrieval eval over the same query path the agent uses.

    from motherflame import eval as mf_eval
    report = mf_eval.run(brain, golden, k=3)
    print(mf_eval.format_report(report))
"""
from __future__ import annotations

import json
from pathlib import Path


def _retrieve_keys(brain: dict, question: str, k: int) -> list[str]:
    """Run the brain's own retrieval for a question, return the top-k fact keys.
    Uses the token-budget ranker so eval matches what the agent actually sees."""
    from motherflame import tokens
    items = brain.get("items", [])
    if not items:
        return []
    fit = tokens.fit_facts(items, query=question, budget_tokens=10_000)
    # fit preserves ranking order; map context lines back to keys via the ranked items
    ranked = sorted(items, key=lambda f: tokens.score_fact(f, tokens._tokenize(question)),
                    reverse=True)
    return [it["key"] for it in ranked[:k]]


def run(brain: dict, golden: list[dict], k: int = 3) -> dict:
    """Evaluate retrieval against a golden set.

    Each golden item: {"question": str, "expect": str | [str]}.
    Returns aggregate precision@k, recall, hit-rate, and per-question detail.
    """
    results = []
    hits = 0
    precision_sum = 0.0
    recall_sum = 0.0
    for g in golden:
        q = g["question"]
        expect = g["expect"]
        expected = {expect} if isinstance(expect, str) else set(expect)
        # normalize expected keys to canonical form (aliases shouldn't fail eval)
        from motherflame import conflicts
        expected = {conflicts.canonical_key(e) for e in expected}
        got = _retrieve_keys(brain, q, k)
        got_set = {conflicts.canonical_key(x) for x in got}
        overlap = expected & got_set
        hit = bool(overlap)
        hits += 1 if hit else 0
        precision = len(overlap) / len(got_set) if got_set else 0.0
        recall = len(overlap) / len(expected) if expected else 0.0
        precision_sum += precision
        recall_sum += recall
        results.append({
            "question": q, "expected": sorted(expected), "got": got,
            "hit": hit, "precision": round(precision, 3), "recall": round(recall, 3),
        })
    n = len(golden) or 1
    return {
        "k": k,
        "n": len(golden),
        "hit_rate": round(hits / n, 3),
        "precision_at_k": round(precision_sum / n, 3),
        "recall": round(recall_sum / n, 3),
        "results": results,
    }


def load_golden(path: str) -> list[dict]:
    """Load a golden Q&A set from JSON. (YAML supported if PyYAML is installed.)"""
    p = Path(path).expanduser()
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            raise RuntimeError("YAML golden set needs PyYAML; use JSON or `pip install pyyaml`")
    return json.loads(text)


def format_report(report: dict) -> str:
    lines = [
        f"Eval over {report['n']} questions (k={report['k']}):",
        f"  hit-rate:      {report['hit_rate']:.0%}",
        f"  precision@{report['k']}:  {report['precision_at_k']:.0%}",
        f"  recall:        {report['recall']:.0%}",
        "",
    ]
    for r in report["results"]:
        mark = "✓" if r["hit"] else "✗"
        lines.append(f"  {mark} {r['question']}")
        if not r["hit"]:
            lines.append(f"      expected {r['expected']}, got {r['got']}")
    return "\n".join(lines)
