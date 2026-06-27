"""
Motherflame Agent Runtime — agentic tool-use loop (Hermes-style)
The LLM decides which tools to call, executes them, loops until done.
Supports OpenAI + Anthropic tool-calling formats.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


# ── Tool definitions (provider-agnostic schema) ────────────────────────────

TOOLS = [
    {
        "name": "query_brain",
        "description": "Search the Org Brain for facts about the company. Use this to answer any question about the org.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What to look up (e.g. 'pricing', 'team', 'brand voice')"}
            },
            "required": ["topic"],
        },
    },
    {
        "name": "add_fact",
        "description": "Add a new fact to the Org Brain. Use when the user states new company info, a decision, or a change.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "One of: Company, Product, Team, Voice, Strategy"},
                "key":      {"type": "string", "description": "Short snake_case identifier"},
                "value":    {"type": "string", "description": "The factual statement"},
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "list_gaps",
        "description": "List what information is still missing from the Org Brain.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_all_facts",
        "description": "Return every fact currently stored in the Org Brain, grouped by category.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]


# ── Tool implementations (operate on the brain dict) ───────────────────────

def _tool_query_brain(brain, topic):
    topic_l = topic.lower()
    hits = []
    for item in brain.get("items", []):
        hay = f"{item['key']} {item['value']} {item.get('category','')}".lower()
        if any(w in hay for w in topic_l.split()):
            hits.append(item)
    if not hits:
        # fall back to returning all so the LLM can reason over them
        hits = brain.get("items", [])
    lines = [f"[{h['category']}] {h['key']}: {h['value']}" for h in hits[:25]]
    return "\n".join(lines) if lines else "Org Brain is empty."


def _tool_add_fact(brain, category, key, value):
    from motherflame import ledger
    # de-dupe by key
    for item in brain.get("items", []):
        if item["key"] == key:
            item["value"] = value
            item["updated_at"] = datetime.now().isoformat()
            ledger.record_fact_write(category, key, value, source="chat", fact_id=key)
            return f"Updated existing fact '{key}'."
    brain.setdefault("items", []).append({
        "category": category, "key": key, "value": value,
        "source": "chat", "confidence": 1.0,
        "harvested_at": datetime.now().isoformat(), "via": "chat",
    })
    ledger.record_fact_write(category, key, value, source="chat", fact_id=key)
    return f"Added new fact '{key}' under {category}."


def _tool_list_gaps(brain):
    gaps = brain.get("gaps", [])
    return "Missing: " + ", ".join(gaps) if gaps else "No known gaps."


def _tool_list_all_facts(brain):
    cats = {}
    for item in brain.get("items", []):
        cats.setdefault(item["category"], []).append(f"  {item['key']}: {item['value']}")
    out = []
    for cat, items in cats.items():
        out.append(f"{cat}:")
        out.extend(items)
    return "\n".join(out) if out else "Org Brain is empty."


def _dispatch_tool(name, args, brain):
    """Run a tool by name. Returns (result_string, mutated)."""
    try:
        if name == "query_brain":
            return _tool_query_brain(brain, args.get("topic", "")), False
        elif name == "add_fact":
            return _tool_add_fact(brain, args.get("category", "General"),
                                  args.get("key", "fact"), args.get("value", "")), True
        elif name == "list_gaps":
            return _tool_list_gaps(brain), False
        elif name == "list_all_facts":
            return _tool_list_all_facts(brain), False
        else:
            return f"Unknown tool: {name}", False
    except Exception as e:
        return f"Tool error: {e}", False


# ── LLM calls with tool support ────────────────────────────────────────────

def _anthropic_tools(tools):
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]


def _openai_tools(tools):
    return [{"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["parameters"]
    }} for t in tools]


def _call_anthropic_agent(api_key, model, messages, system):
    payload = json.dumps({
        "model": model, "max_tokens": 1024, "system": system,
        "messages": messages, "tools": _anthropic_tools(TOOLS),
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _call_openai_agent(api_key, model, messages, system):
    msgs = [{"role": "system", "content": system}] + messages
    payload = json.dumps({
        "model": model, "messages": msgs, "tools": _openai_tools(TOOLS), "max_tokens": 1024,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


# ── The agentic loop ───────────────────────────────────────────────────────

AGENT_SYSTEM = """You are the Motherflame Org Brain agent for {org_name}.
You help the team by answering questions about the company and keeping the Org Brain up to date.

You have tools to query the brain, add new facts, and list gaps.
- When asked a question → use query_brain (or list_all_facts) then answer concisely.
- When the user states a NEW fact, decision, or change → call add_fact to persist it.
- Be direct and brief. You are a teammate, not a chatbot.

Always ground answers in the Org Brain. If something isn't known, say so and offer to add it."""


def agent_turn(cfg, brain, user_message, history, on_tool=None):
    """
    Run one agentic turn (may involve multiple tool calls).
    Returns (assistant_text, brain_mutated). Mutates `history` in place.
    on_tool(name, args, result) is an optional callback for UI display.
    """
    provider = cfg.get("provider", "anthropic")
    model    = cfg.get("model")
    api_key  = cfg.get("agent_api_key", "")
    org      = brain.get("org_name", "the organization")
    system   = AGENT_SYSTEM.format(org_name=org)

    mutated = False

    if provider == "anthropic":
        history.append({"role": "user", "content": user_message})
        for _ in range(6):  # max 6 tool-loop iterations
            resp = _call_anthropic_agent(api_key, model, history, system)
            content = resp.get("content", [])
            # collect tool_use blocks
            tool_uses = [c for c in content if c.get("type") == "tool_use"]
            text_blocks = [c["text"] for c in content if c.get("type") == "text"]
            history.append({"role": "assistant", "content": content})

            if not tool_uses:
                return ("\n".join(text_blocks).strip(), mutated)

            tool_results = []
            for tu in tool_uses:
                result, m = _dispatch_tool(tu["name"], tu.get("input", {}), brain)
                mutated = mutated or m
                if on_tool:
                    on_tool(tu["name"], tu.get("input", {}), result)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu["id"], "content": result,
                })
            history.append({"role": "user", "content": tool_results})
        return ("(stopped after 6 tool iterations)", mutated)

    else:  # openai
        history.append({"role": "user", "content": user_message})
        for _ in range(6):
            resp = _call_openai_agent(api_key, model, history, system)
            msg = resp["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []
            history.append(msg)

            if not tool_calls:
                return ((msg.get("content") or "").strip(), mutated)

            for tc in tool_calls:
                fn = tc["function"]
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                result, m = _dispatch_tool(fn["name"], args, brain)
                mutated = mutated or m
                if on_tool:
                    on_tool(fn["name"], args, result)
                history.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": result,
                })
        return ("(stopped after 6 tool iterations)", mutated)


# ── Planning mode ──────────────────────────────────────────────────────────

PLAN_SYSTEM = """You are the Motherflame planning agent for {org_name}.
Given a goal, produce a concise step-by-step plan to accomplish it using the Org Brain.

Output ONLY a numbered list of 2-6 concrete steps. No preamble, no explanation.
Each step should be a single actionable line. Example:
1. Query the brain for current pricing facts
2. Identify which pricing tiers are missing
3. Draft the missing tier descriptions
4. Add them as new facts"""


def plan_task(cfg, brain, goal):
    """Ask the LLM to produce a step-by-step plan (list of strings). No tool use."""
    provider = cfg.get("provider", "anthropic")
    model    = cfg.get("model")
    api_key  = cfg.get("agent_api_key", "")
    org      = brain.get("org_name", "the organization")
    system   = PLAN_SYSTEM.format(org_name=org)

    known = ", ".join(i["key"] for i in brain.get("items", [])[:30]) or "nothing yet"
    gaps  = ", ".join(brain.get("gaps", [])) or "none known"
    user  = f"Goal: {goal}\n\nKnown facts: {known}\nKnown gaps: {gaps}"

    if provider == "anthropic":
        resp = _call_anthropic_plain(api_key, model, user, system)
    else:
        resp = _call_openai_plain(api_key, model, user, system)

    steps = []
    for line in resp.split("\n"):
        line = line.strip()
        if not line:
            continue
        cleaned = line.lstrip("0123456789.)- ").strip()
        if cleaned:
            steps.append(cleaned)
    return steps


def _call_anthropic_plain(api_key, model, user, system):
    payload = json.dumps({
        "model": model, "max_tokens": 512, "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")


def _call_openai_plain(api_key, model, user, system):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": 512,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"].get("content") or ""
