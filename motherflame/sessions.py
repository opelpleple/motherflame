"""
Motherflame Sessions — persistent chat history across runs.

Each chat session is saved to ~/.motherflame/sessions/<id>.json so the user
can resume context, review past conversations, and the agent keeps long-term
memory of what was discussed.
"""

import json
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".motherflame" / "sessions"


def _new_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def save_session(session_id, history, meta=None):
    """Persist a chat session's message history + metadata."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "id": session_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "meta": meta or {},
        "history": _serialize(history),
    }
    (SESSIONS_DIR / f"{session_id}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False))
    return session_id


def _serialize(history):
    """History may contain non-JSON-safe objects (openai message dicts are fine).
    Keep only role + a text preview to stay portable across providers."""
    out = []
    for msg in history:
        role = msg.get("role", "?") if isinstance(msg, dict) else "?"
        content = msg.get("content") if isinstance(msg, dict) else str(msg)
        # content can be a string, list of blocks, or None
        if isinstance(content, list):
            texts = []
            for c in content:
                if isinstance(c, dict):
                    if c.get("type") == "text":
                        texts.append(c.get("text", ""))
                    elif c.get("type") == "tool_result":
                        texts.append(f"[tool_result] {str(c.get('content',''))[:100]}")
                    elif c.get("type") == "tool_use":
                        texts.append(f"[tool_use:{c.get('name')}]")
            content = " ".join(t for t in texts if t)
        elif content is None:
            content = ""
        out.append({"role": role, "text": str(content)[:1000]})
    return out


def load_session(session_id):
    f = SESSIONS_DIR / f"{session_id}.json"
    if f.exists():
        return json.loads(f.read_text())
    return None


def list_sessions(limit=20):
    """Return recent sessions (newest first) as light summaries."""
    if not SESSIONS_DIR.exists():
        return []
    out = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(f.read_text())
            hist = d.get("history", [])
            user_msgs = [m for m in hist if m.get("role") == "user"]
            first = user_msgs[0]["text"][:60] if user_msgs else "(empty)"
            out.append({
                "id": d.get("id"),
                "updated_at": d.get("updated_at"),
                "n_messages": len(hist),
                "n_facts": d.get("meta", {}).get("facts_added", 0),
                "preview": first,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return out


def latest_session_id():
    sessions = list_sessions(limit=1)
    return sessions[0]["id"] if sessions else None
