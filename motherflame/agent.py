"""
Motherflame Agent Runtime
Connect your own AI API → powers intelligent harvest + query
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
import tty
import termios
from pathlib import Path


# ── Arrow-key selector ─────────────────────────────────────────────────────

def arrow_select(prompt: str, options: list[str], default: int = 0) -> int:
    """Interactive arrow-key menu. Returns selected index."""
    import sys, tty, termios

    selected = default
    n = len(options)
    total_lines = n + 1   # 1 prompt line + n option lines

    def _render(first: bool):
        if not first:
            # Move cursor back up to the prompt line
            sys.stdout.write(f"\033[{total_lines}A")
        # prompt line (\r resets to column 0 in raw mode, \033[K clears the line)
        sys.stdout.write(f"\r\033[K\033[2m  {prompt}\033[0m\n")
        for i, opt in enumerate(options):
            sys.stdout.write("\r\033[K")
            if i == selected:
                sys.stdout.write(f"  \033[38;5;208m❯\033[0m \033[1m{opt}\033[0m\n")
            else:
                sys.stdout.write(f"    \033[2m{opt}\033[0m\n")
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        _render(first=True)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                ch3 = sys.stdin.read(1)
                if ch2 == "[":
                    if ch3 == "A":   selected = (selected - 1) % n
                    elif ch3 == "B": selected = (selected + 1) % n
            elif ch in ("\r", "\n"):
                break
            elif ch == "\x03":
                raise KeyboardInterrupt
            _render(first=False)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        # Move back to top of menu and clear everything below
        sys.stdout.write(f"\033[{total_lines}A\r\033[J")
        sys.stdout.flush()

    return selected


def checkbox_select(prompt: str, options: list[str], defaults: list[int] = None) -> list[int]:
    """Multi-select checkbox menu. Space=toggle, Enter=confirm. Returns list of selected indices."""
    import sys, tty, termios

    n        = len(options)
    cursor   = 0
    selected = set(defaults or [])
    total_lines = n + 1   # 1 prompt line + n option lines

    def _render(first: bool):
        if not first:
            sys.stdout.write(f"\033[{total_lines}A")
        sys.stdout.write(f"\r\033[K\033[2m  {prompt}  (Space=select  Enter=confirm)\033[0m\n")
        for i, opt in enumerate(options):
            sys.stdout.write("\r\033[K")
            checked     = "✓" if i in selected else " "
            check_color = "\033[92m" if i in selected else "\033[2m"
            if i == cursor:
                sys.stdout.write(f"  \033[38;5;208m❯\033[0m {check_color}[{checked}]\033[0m \033[1m{opt}\033[0m\n")
            else:
                sys.stdout.write(f"    {check_color}[{checked}]\033[0m \033[2m{opt}\033[0m\n")
        sys.stdout.flush()

    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        _render(first=True)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                ch3 = sys.stdin.read(1)
                if ch2 == "[":
                    if ch3 == "A":   cursor = (cursor - 1) % n
                    elif ch3 == "B": cursor = (cursor + 1) % n
            elif ch == " ":
                if cursor in selected: selected.discard(cursor)
                else:                  selected.add(cursor)
            elif ch in ("\r", "\n"):
                break
            elif ch == "\x03":
                raise KeyboardInterrupt
            _render(first=False)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write(f"\033[{total_lines}A\r\033[J")
        sys.stdout.flush()

    return sorted(selected)

# ── Provider registry ──────────────────────────────────────────────────────

PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "models": ["claude-haiku-4-5", "claude-sonnet-4", "claude-opus-4"],
        "default_model": "claude-haiku-4-5",
        "key_prefix": "sk-ant-",
        "key_hint": "sk-ant-...",
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
        "default_model": "gpt-4o-mini",
        "key_prefix": "sk-",
        "key_hint": "sk-...",
    },
    "ollama": {
        "label": "Ollama (local, no key needed)",
        "models": ["llama3.2", "mistral", "phi3"],
        "default_model": "llama3.2",
        "key_prefix": "",
        "key_hint": "(no key needed)",
    },
}


# ── LLM call ──────────────────────────────────────────────────────────────

# Default output budget; callers can override via cfg["max_tokens"].
DEFAULT_MAX_TOKENS = 2048
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 529}


def _urlopen_retry(req, timeout=60, attempts=4):
    """POST with exponential backoff on transient failures (429/529 overload,
    5xx, network blips). Honors Retry-After when present. Raises the last error
    after `attempts` tries so the caller can degrade gracefully."""
    import time as _t
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in _RETRYABLE_STATUS or i == attempts - 1:
                raise
            retry_after = e.headers.get("Retry-After") if e.headers else None
            delay = float(retry_after) if (retry_after or "").isdigit() else (2 ** i)
            _t.sleep(min(delay, 30))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if i == attempts - 1:
                raise
            _t.sleep(2 ** i)
    if last:
        raise last


def _max_tokens(cfg, default=DEFAULT_MAX_TOKENS):
    try:
        return int((cfg or {}).get("max_tokens", default))
    except (TypeError, ValueError):
        return default


def _call_anthropic(api_key: str, model: str, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST"
    )
    data = _urlopen_retry(req, timeout=60)
    return data["content"][0]["text"].strip()


def _call_openai(api_key: str, model: str, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    data = _urlopen_retry(req, timeout=60)
    return data["choices"][0]["message"]["content"].strip()


def _call_ollama(model: str, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": f"{system}\n\n{user}",
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    data = _urlopen_retry(req, timeout=120)
    return data["response"].strip()


def call_llm(cfg: dict, system: str, user: str) -> str:
    """Route to correct provider based on config."""
    provider = cfg.get("provider", "anthropic")
    model    = cfg.get("model", PROVIDERS[provider]["default_model"])
    api_key  = cfg.get("agent_api_key", "")
    mt       = _max_tokens(cfg)

    if provider == "anthropic":
        return _call_anthropic(api_key, model, system, user, mt)
    elif provider == "openai":
        return _call_openai(api_key, model, system, user, mt)
    elif provider == "ollama":
        return _call_ollama(model, system, user, mt)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ── Test connection ────────────────────────────────────────────────────────

def test_connection(cfg: dict) -> tuple[bool, str]:
    """Returns (ok, message)"""
    try:
        reply = call_llm(cfg,
            system="You are a helpful assistant. Reply with exactly: OK",
            user="Reply with exactly: OK"
        )
        ok = "OK" in reply.upper()
        return ok, reply[:40]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:200]
        return False, f"HTTP {e.code}: {body}"
    except urllib.error.URLError as e:
        return False, f"Cannot reach provider: {e.reason}"
    except Exception as e:
        return False, str(e)[:120]


# ── Intelligent extract ────────────────────────────────────────────────────

EXTRACT_SYSTEM = """You are an org-context extractor for Motherflame.
Given a text from a company's internal docs, extract structured org facts.

Return ONLY valid JSON (no markdown, no extra text) with this shape:
{
  "items": [
    {"category": "Company|Product|Team|Voice|Strategy",
     "key": "short_snake_case_key",
     "value": "concise factual value",
     "confidence": 0.0-1.0}
  ]
}

Focus on: company purpose, product/service, pricing, team size, target customers,
communication style, current goals, strategic direction.
Skip navigation menus, boilerplate, headers, legal disclaimers.
Max 8 items per call. Return empty items:[] if no org facts found."""


RESEARCH_SYSTEM = """You are a company researcher for Motherflame. You read text
scraped from a company's public website and extract SPECIFIC, CONCRETE org facts —
the kind a teammate would actually need, not vague summaries.

Return ONLY valid JSON (no markdown) with this shape:
{
  "items": [
    {"category": "Company|Product|Team|Voice|Strategy",
     "key": "short_snake_case_key",
     "value": "a concrete, specific fact",
     "confidence": 0.0-1.0}
  ]
}

RULES — be specific, not generic:
- BAD:  {"key":"pricing","value":"subscription"}
- GOOD: {"key":"pricing_tiers","value":"Listing plans at $18k / $48k / $100k+ per year"}
- BAD:  {"key":"problem_solved","value":"trust and decisions"}
- GOOD: {"key":"problem_solved","value":"Helps investors verify which financial brokers are licensed and trustworthy before investing"}
- Capture: what the company does, exact products/features, pricing/tiers with numbers,
  named customers/segments, founders/leadership names, headcount, locations,
  regulators/licenses, differentiators, taglines, and stated strategy.
- Prefer many specific facts over a few vague ones. Up to 12 items per call.
- Mark confidence lower (0.5-0.7) for things implied rather than stated.
- Skip nav menus, cookie banners, legal boilerplate. Return items:[] if nothing real."""


def llm_research_extract(cfg: dict, text: str, source_url: str) -> list:
    """Deeper extraction tuned for website text — concrete facts, more context.
    Returns the same item shape as llm_extract_signals, tagged via='research'."""
    excerpt = text[:6000]   # websites are denser; give the model more to work with
    try:
        raw = call_llm(cfg, system=RESEARCH_SYSTEM,
                       user=f"Company website page: {source_url}\n\nText:\n{excerpt}")
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)
        items = data.get("items", [])
        from datetime import datetime
        cleaned = []
        for item in items:
            if not isinstance(item, dict): continue
            if not all(k in item for k in ("category", "key", "value")): continue
            cleaned.append({
                "category":     str(item.get("category", "Company")),
                "key":          str(item.get("key", "unknown")),
                "value":        str(item.get("value", ""))[:300],
                "confidence":   float(item.get("confidence", 0.75)),
                "source":       source_url,
                "harvested_at": datetime.now().isoformat(),
                "via":          "research",
            })
        return cleaned
    except Exception:
        return []


def llm_extract_signals(cfg: dict, text: str, source: str) -> list[dict]:
    """Use LLM to extract org signals from text. Returns list of items."""
    # Truncate to ~3000 chars to stay within token budget
    excerpt = text[:3000]
    try:
        raw = call_llm(cfg, system=EXTRACT_SYSTEM,
                       user=f"Source: {source}\n\nText:\n{excerpt}")
        # Parse JSON — strip any accidental markdown fences
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)
        items = data.get("items", [])
        # Validate + stamp each item
        from datetime import datetime
        cleaned = []
        for item in items:
            if not isinstance(item, dict): continue
            if not all(k in item for k in ("category","key","value")): continue
            cleaned.append({
                "category":     str(item.get("category","General")),
                "key":          str(item.get("key","unknown")),
                "value":        str(item.get("value",""))[:300],
                "confidence":   float(item.get("confidence", 0.85)),
                "source":       source,
                "harvested_at": datetime.now().isoformat(),
                "via":          "llm",
            })
        return cleaned
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


# ── Query Org Brain ────────────────────────────────────────────────────────

QUERY_SYSTEM = """You are the Org Brain assistant for {org_name}.
Answer questions using ONLY the org context provided below.
Be concise and direct. If the answer isn't in the context, say so clearly.

IMPORTANT: If a fact is marked "⚠️ CONTESTED", teammates disagree on its value.
Do NOT state it as settled fact. Say the value is disputed, give the current
best pick AND the competing value(s), and suggest running /resolve to settle it.

ORG CONTEXT:
{context}"""


def query_brain(cfg: dict, brain: dict, question: str) -> str:
    """Answer a question using org brain context + LLM.
    Uses the token budget manager to send only the most relevant facts that fit
    the budget — not the whole brain — so cost stays bounded as the brain grows."""
    from motherflame import tokens

    items = brain.get("items", [])
    if not items:
        return "Org Brain is empty — run `motherflame start` first."

    # annotate contested facts with their competing values so the LLM can caveat
    enriched = []
    for item in items:
        it = dict(item)
        if item.get("contested"):
            claims = brain.get("claims", {}).get(item["key"], [])
            alts = sorted({c["value"] for c in claims if c["value"] != item["value"]})
            if alts:
                it["value"] = f"{item['value']} (disputed; also: {', '.join(a[:40] for a in alts)})"
        enriched.append(it)

    budget = int(cfg.get("context_budget_tokens", tokens.DEFAULT_BUDGET))
    fit = tokens.fit_facts(enriched, query=question, budget_tokens=budget)
    context = fit["context"]

    org = brain.get("org_name", "the organization")
    system = QUERY_SYSTEM.format(org_name=org, context=context)
    return call_llm(cfg, system=system, user=question)
