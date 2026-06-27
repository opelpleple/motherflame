"""
Motherflame Ledger — provenance & audit trail.

Records every meaningful event so the user can always answer:
  - "What folders have I scanned?"
  - "What did I send to the Org Brain, and when?"
  - "Where did this fact come from?"
  - "Undo the last change."

Stored at ~/.motherflame/ledger.json as an append-only event log.
"""

import json
from datetime import datetime
from pathlib import Path

LEDGER_FILE = Path.home() / ".motherflame" / "ledger.json"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def load_ledger():
    if LEDGER_FILE.exists():
        try:
            return json.loads(LEDGER_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"events": []}


def save_ledger(ledger):
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))


def record(event_type, **data):
    """Append an event to the ledger. Returns the event dict."""
    ledger = load_ledger()
    event = {"ts": _now(), "type": event_type, **data}
    ledger["events"].append(event)
    save_ledger(ledger)
    return event


# ── Typed recorders ────────────────────────────────────────────────────────

def record_scan(folder, file_count, globs, signals_found):
    """A folder was scanned during harvest."""
    return record("scan",
                  folder=str(folder),
                  file_count=file_count,
                  globs=globs,
                  signals_found=signals_found)


def record_fact_write(category, key, value, source, fact_id=None):
    """A fact was written/updated in the Org Brain."""
    return record("fact_write",
                  category=category,
                  key=key,
                  value=value[:200],
                  source=source,
                  fact_id=fact_id)


def record_fact_remove(key, value):
    """A fact was removed (e.g. undo)."""
    return record("fact_remove", key=key, value=value[:200])


def record_session(summary, n_messages, n_facts_added):
    """A chat session ended."""
    return record("session", summary=summary,
                  n_messages=n_messages, n_facts_added=n_facts_added)


# ── Queries ────────────────────────────────────────────────────────────────

def get_scans(limit=None):
    evs = [e for e in load_ledger()["events"] if e["type"] == "scan"]
    return evs[-limit:] if limit else evs


def get_fact_writes(limit=None):
    evs = [e for e in load_ledger()["events"] if e["type"] == "fact_write"]
    return evs[-limit:] if limit else evs


def get_last_write():
    writes = get_fact_writes()
    return writes[-1] if writes else None


def source_of(key):
    """Return the most recent provenance for a fact key."""
    writes = [e for e in get_fact_writes() if e["key"] == key]
    return writes[-1] if writes else None


def summary_stats():
    """High-level counts for /history header."""
    evs = load_ledger()["events"]
    scans  = [e for e in evs if e["type"] == "scan"]
    writes = [e for e in evs if e["type"] == "fact_write"]
    folders = sorted({e["folder"] for e in scans})
    total_files = sum(e.get("file_count", 0) for e in scans)
    return {
        "total_scans": len(scans),
        "total_folders": len(folders),
        "folders": folders,
        "total_files_seen": total_files,
        "total_writes": len(writes),
        "first_event": evs[0]["ts"] if evs else None,
        "last_event": evs[-1]["ts"] if evs else None,
    }


# ── Freshness tracking (file fingerprints) ─────────────────────────────────

import hashlib

FILESTATE_FILE = Path.home() / ".motherflame" / "filestate.json"


def _load_filestate():
    if FILESTATE_FILE.exists():
        try:
            return json.loads(FILESTATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_filestate(state):
    FILESTATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    FILESTATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def file_fingerprint(path):
    """Return (mtime, sha1-of-first-64KB) for a file, or None if unreadable."""
    try:
        p = Path(path)
        mtime = p.stat().st_mtime
        h = hashlib.sha1()
        with open(p, "rb") as f:
            h.update(f.read(65536))
        return {"mtime": mtime, "hash": h.hexdigest()}
    except (OSError, PermissionError):
        return None


def record_file_seen(path):
    """Remember a file's fingerprint at harvest time."""
    fp = file_fingerprint(path)
    if fp is None:
        return
    state = _load_filestate()
    state[str(path)] = {**fp, "seen_at": _now()}
    _save_filestate(state)


def is_file_changed(path):
    """True if the file changed (or is new) since we last saw it."""
    state = _load_filestate()
    prev = state.get(str(path))
    if prev is None:
        return True  # never seen → counts as new
    cur = file_fingerprint(path)
    if cur is None:
        return False
    return cur["hash"] != prev.get("hash")


def changed_files(paths):
    """Filter a list of paths down to those that are new or changed."""
    return [p for p in paths if is_file_changed(p)]


def seen_files():
    """All files we've fingerprinted, with their last-seen timestamps."""
    return _load_filestate()
