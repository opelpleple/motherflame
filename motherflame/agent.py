"""
Motherflame Agent Runtime
Connect your own AI API → powers intelligent harvest + query
"""

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

def _call_anthropic(api_key: str, model: str, system: str, user: str) -> str:
    payload = json.dumps({
        "model": model,
        "max_tokens": 1024,
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"].strip()


def _call_openai(api_key: str, model: str, system: str, user: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1024,
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def _call_ollama(model: str, system: str, user: str) -> str:
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["response"].strip()


def call_llm(cfg: dict, system: str, user: str) -> str:
    """Route to correct provider based on config."""
    provider = cfg.get("provider", "anthropic")
    model    = cfg.get("model", PROVIDERS[provider]["default_model"])
    api_key  = cfg.get("agent_api_key", "")

    if provider == "anthropic":
        return _call_anthropic(api_key, model, system, user)
    elif provider == "openai":
        return _call_openai(api_key, model, system, user)
    elif provider == "ollama":
        return _call_ollama(model, system, user)
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

ORG CONTEXT:
{context}"""


def query_brain(cfg: dict, brain: dict, question: str) -> str:
    """Answer a question using org brain context + LLM."""
    items = brain.get("items", [])
    if not items:
        return "Org Brain is empty — run `motherflame start` first."

    # Build context string
    lines = []
    for item in items:
        lines.append(f"[{item['category']}] {item['key']}: {item['value']}")
    context = "\n".join(lines)

    org = brain.get("org_name", "the organization")
    system = QUERY_SYSTEM.format(org_name=org, context=context)
    return call_llm(cfg, system=system, user=question)
