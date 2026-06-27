"""
Motherflame Token Budget Manager — make every token of org context count.

When the Org Brain feeds an LLM (query, chat, or an external MCP agent), naively
dumping every fact wastes tokens and money and drowns the signal. This module
selects the *most relevant* slice that fits a token budget, ranked and compressed.

Pipeline:
  1. SCORE     — relevance of each fact to the query (keyword overlap + category
                 hit + confidence + freshness; contested facts kept, not buried)
  2. RANK      — sort by score, best first
  3. FIT       — greedily pack facts until the token budget is hit
  4. COMPRESS  — trim long values so one verbose fact can't eat the whole budget

No external deps: token counts are estimated (≈4 chars/token, the standard
rule of thumb for English) which is plenty accurate for budgeting.
"""

import re

CHARS_PER_TOKEN = 4          # rule-of-thumb estimate for English text
DEFAULT_BUDGET  = 1500       # tokens of context to spend per query by default
MAX_VALUE_CHARS = 240        # hard cap on a single fact's value (~60 tokens)


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string (≈4 chars/token, min 1 for non-empty)."""
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def score_fact(fact: dict, query_terms: set) -> float:
    """Relevance score for one fact against the query terms. Higher = more relevant."""
    key_terms = _tokenize(fact.get("key", ""))
    val_terms = _tokenize(fact.get("value", ""))
    cat_terms = _tokenize(fact.get("category", ""))

    score = 0.0
    # term overlap — key matches weigh most, then value, then category
    score += 3.0 * len(query_terms & key_terms)
    score += 1.0 * len(query_terms & val_terms)
    score += 1.5 * len(query_terms & cat_terms)
    # confidence nudges ties
    score += 0.5 * float(fact.get("confidence", 0.7))
    # contested facts are worth surfacing (the user may need to resolve them)
    if fact.get("contested"):
        score += 0.4
    # if there are NO query terms (e.g. list_facts), keep confidence ordering
    if not query_terms:
        score = float(fact.get("confidence", 0.7))
    return score


def compress_value(value: str, max_chars: int = MAX_VALUE_CHARS) -> str:
    """Trim a long value to a budget, preserving the start (the headline)."""
    v = " ".join(str(value).split())
    if len(v) <= max_chars:
        return v
    return v[: max_chars - 1].rstrip() + "…"


def fit_facts(facts: list, query: str = "", budget_tokens: int = DEFAULT_BUDGET,
              max_value_chars: int = MAX_VALUE_CHARS) -> dict:
    """Select the highest-value facts that fit within `budget_tokens`.

    Returns {lines, included, dropped, tokens_used, budget}. `lines` is the
    formatted context ready to drop into a prompt.
    """
    query_terms = _tokenize(query)
    ranked = sorted(facts, key=lambda f: score_fact(f, query_terms), reverse=True)

    lines, included, used = [], 0, 0
    for f in ranked:
        val = compress_value(f.get("value", ""), max_value_chars)
        line = f"[{f.get('category','?')}] {f.get('key','?')}: {val}"
        if f.get("contested"):
            line += "  ⚠️CONTESTED"
        cost = estimate_tokens(line)
        if used + cost > budget_tokens and included > 0:
            break  # budget exhausted (always allow at least one fact)
        lines.append(line)
        used += cost
        included += 1

    return {
        "lines": lines,
        "context": "\n".join(lines),
        "included": included,
        "dropped": len(facts) - included,
        "tokens_used": used,
        "budget": budget_tokens,
    }


def budget_report(result: dict) -> str:
    """One-line human summary of a fit_facts result."""
    return (f"{result['included']} facts · ~{result['tokens_used']}/{result['budget']} tokens"
            + (f" · {result['dropped']} dropped (low relevance)" if result['dropped'] else ""))
