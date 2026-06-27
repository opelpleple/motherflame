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
SERVER_VERSION = "0.1.0"


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
    ]


# ── Tool execution (operates on the persisted brain) ───────────────────────

def _run_tool(name, args):
    from motherflame.core import load_brain, save_brain
    from motherflame.runtime import _tool_query_brain, _tool_add_fact, _tool_list_all_facts

    brain = load_brain()
    if name == "query_brain":
        return _tool_query_brain(brain, args.get("topic", ""))
    elif name == "list_facts":
        return _tool_list_all_facts(brain)
    elif name == "add_fact":
        result = _tool_add_fact(brain, args.get("category", "General"),
                                args.get("key", "fact"), args.get("value", ""))
        save_brain(brain)
        return result
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
