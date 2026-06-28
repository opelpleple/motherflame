"""
Motherflame MCP Server — expose the Org Brain to any MCP-compatible agent
(Claude Code, Cursor, Hermes, etc.) over stdio JSON-RPC.

This is what turns Motherflame from a Product into a Protocol: any external
agent can `query_brain`, `list_facts`, and `add_fact` against your central
Org Brain through the Model Context Protocol.

Implements the MCP subset needed for tools, using only the Python stdlib
(JSON-RPC 2.0 over stdin/stdout). No external SDK required.

Run:  motherflame mcp
Then point an MCP client at:  command = "motherflame", args = ["mcp"]
"""

import json
import sys

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "motherflame"
from motherflame import __version__
SERVER_VERSION = __version__


# ── Tool catalog exposed over MCP ──────────────────────────────────────────

def _tool_defs():
    return [
        {
            "name": "query_brain",
            "description": (
                "Look up authoritative facts about THIS organization/company from its "
                "Org Brain. Call this whenever the user asks about, or you need to know, "
                "company-specific details you can't infer: pricing, plans, team size, who "
                "owns what, the product, target customers, brand voice, strategy, goals, "
                "or internal decisions. Prefer this over guessing. Returns only the most "
                "relevant facts (token-budgeted), and flags any that are CONTESTED."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string",
                              "description": "What to look up, e.g. 'pricing tiers' or 'brand voice'"}
                },
                "required": ["topic"],
            },
        },
        {
            "name": "list_facts",
            "description": (
                "List the Org Brain's facts grouped by category. Use when you need a broad "
                "overview of what the organization has recorded, not a specific lookup."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "add_fact",
            "description": (
                "Record a NEW fact about the organization in the Org Brain, or update an "
                "existing one. Call this when the user states durable company information "
                "worth remembering (a decision, a price change, a new hire count, etc.)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "key":      {"type": "string"},
                    "value":    {"type": "string"},
                },
                "required": ["category", "key", "value"],
            },
        },
        {
            "name": "forget_fact",
            "description": (
                "Retract/delete a fact from the Org Brain. Use when a fact is wrong, "
                "outdated, or should be removed. The deletion is a tombstone that "
                "survives team syncs (won't be resurrected by a teammate's stale copy)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
        {
            "name": "verify_fact",
            "description": (
                "Mark a fact as human-verified — a trust signal ranked above unverified "
                "LLM-extracted claims in conflict resolution. Use when a human confirms "
                "a fact is correct."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
        {
            "name": "setup_team_sync",
            "description": (
                "Bind a git remote URL for zero-knowledge team sync and verify it's "
                "reachable. Use when the user wants to share the Org Brain and has a repo URL."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"git_url": {"type": "string"}},
                "required": ["git_url"],
            },
        },
        {
            "name": "create_team_repo",
            "description": (
                "Create a new private GitHub repo (via the gh CLI) to host the team's "
                "encrypted brain and bind it as the sync remote. Use when the user wants "
                "team sync but has no repo yet. Requires gh installed + authenticated."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "private": {"type": "boolean"},
                },
                "required": [],
            },
        },
        {
            "name": "list_documents",
            "description": (
                "List the long-form documents stored in the Org Brain (plans, memos, "
                "runbooks) with their ids and titles. Use before get_document."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_document",
            "description": (
                "Read the full text of a stored document by its doc_id. Use when the "
                "user asks about a plan/memo/runbook that's too long to be a single fact."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"doc_id": {"type": "string"}},
                "required": ["doc_id"],
            },
        },
    ]


# ── Tool execution (operates on the persisted brain) ───────────────────────

def _readonly() -> bool:
    """MCP write access off-switch. Set MOTHERFLAME_MCP_READONLY=1 (or
    readonly_mcp:true in config) to expose query/list only — no writes.
    Use this when connecting an agent you don't fully trust."""
    import os
    if os.environ.get("MOTHERFLAME_MCP_READONLY", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from motherflame.core import load_config
        return bool(load_config().get("readonly_mcp"))
    except Exception:
        return False


def _run_tool(name, args):
    from motherflame.core import load_brain, update_brain
    from motherflame.runtime import _tool_query_brain, _tool_add_fact, _tool_list_all_facts

    brain = load_brain()
    if name == "query_brain":
        return _tool_query_brain(brain, args.get("topic", ""))
    elif name == "list_facts":
        return _tool_list_all_facts(brain)
    elif name == "add_fact":
        if _readonly():
            return ("⚠️ This Org Brain is connected read-only. Writes are disabled "
                    "(unset MOTHERFLAME_MCP_READONLY to allow add_fact).")
        # Locked read-modify-write: re-load the freshest brain inside the lock so
        # a concurrent chat/MCP write isn't clobbered (lost update).
        return update_brain(lambda b: _tool_add_fact(
            b, args.get("category", "General"), args.get("key", "fact"),
            args.get("value", "")))
    elif name == "forget_fact":
        if _readonly():
            return ("⚠️ This Org Brain is connected read-only. Writes are disabled "
                    "(unset MOTHERFLAME_MCP_READONLY to allow forget_fact).")
        from motherflame.runtime import _tool_forget_fact
        return update_brain(lambda b: _tool_forget_fact(b, args.get("key", "")))
    elif name == "verify_fact":
        if _readonly():
            return ("⚠️ This Org Brain is connected read-only. Writes are disabled "
                    "(unset MOTHERFLAME_MCP_READONLY to allow verify_fact).")
        from motherflame.runtime import _tool_verify_fact
        return update_brain(lambda b: _tool_verify_fact(b, args.get("key", "")))
    elif name == "setup_team_sync":
        if _readonly():
            return ("⚠️ This Org Brain is connected read-only. Team-sync setup is disabled "
                    "(unset MOTHERFLAME_MCP_READONLY to allow).")
        from motherflame.runtime import _tool_setup_team_sync
        return _tool_setup_team_sync(load_brain(), args.get("git_url", ""))
    elif name == "create_team_repo":
        if _readonly():
            return ("⚠️ This Org Brain is connected read-only. Team-sync setup is disabled "
                    "(unset MOTHERFLAME_MCP_READONLY to allow).")
        from motherflame.runtime import _tool_create_team_repo
        return _tool_create_team_repo(load_brain(), args.get("name"), args.get("private", True))
    elif name == "list_documents":
        from motherflame import documents
        docs = documents.list_documents(load_brain())
        if not docs:
            return "No documents stored."
        return "\n".join(f"{d['doc_id']} · {d['title']} ({d['char_len']} chars)" for d in docs)
    elif name == "get_document":
        from motherflame import documents
        doc = documents.get_document(load_brain(), args.get("doc_id", ""))
        if not doc:
            return f"No document with id '{args.get('doc_id','')}'."
        return f"# {doc['title']}\n(source: {doc['source']})\n\n" + "\n\n".join(doc["chunks"])
    else:
        raise ValueError(f"Unknown tool: {name}")


# ── JSON-RPC plumbing ──────────────────────────────────────────────────────

def _response(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_request(req):
    """Dispatch a single JSON-RPC request. Returns a response dict, or None for notifications."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {}) or {}

    if method == "initialize":
        return _response(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "notifications/initialized":
        return None  # notification, no response

    if method == "tools/list":
        return _response(req_id, {"tools": _tool_defs()})

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {}) or {}
        try:
            text = _run_tool(tool_name, tool_args)
            return _response(req_id, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            })
        except Exception as e:
            return _response(req_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    if method == "ping":
        return _response(req_id, {})

    return _error(req_id, -32601, f"Method not found: {method}")


def serve(stdin=None, stdout=None):
    """Run the MCP server loop over stdio (one JSON object per line)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(req)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
