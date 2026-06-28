"""
Motherflame Local Sync — absorb the knowledge already on your machine.

The gap users hit: a web-research brain is thin and ~a year behind the deep,
current, confidential knowledge sitting in local memory files, vault notes, and
project docs. This module ingests those into the brain with the RIGHT authority
and sensitivity so local truth outranks public marketing copy and confidential
notes are tagged (never silently synced).

Pure stdlib. Reads files, never the network. Extraction reuses the agent's
research extractor (LLM) when a key is present, else stores documents as-is.

Authority + sensitivity are inferred from the path so the resolver treats
internal knowledge correctly:
  - .../memory/*.md, vault notes     → source='local_memory', sensitivity='internal'
  - paths hinting confidential/private→ sensitivity='confidential'
"""
import re
from pathlib import Path

# file types we read as text
_TEXT_EXTS = {".md", ".markdown", ".txt", ".mdx"}

# path hints → confidential
_CONFIDENTIAL_HINTS = (
    "confidential", "private", "secret", "memory", "internal",
    "strategy", "pivot", "finance", "salary", "comp",
)


def classify(path: Path, root: Path = None) -> dict:
    """Infer source authority + sensitivity from a file path. Only the portion
    BELOW `root` is inspected (so the absolute prefix like /private/var/... on
    macOS doesn't trigger false 'confidential' hits)."""
    if root is not None:
        try:
            rel = path.relative_to(root)
        except (ValueError, TypeError):
            rel = Path(path.name)
        p = str(rel).lower()
    else:
        p = path.name.lower() + " " + "/".join(path.parts[-3:]).lower()
    if "/memory/" in p or p.endswith("memory.md") or "/.claude/" in p or ".claude" in p.split("/"):
        source, sensitivity = "local_memory", "confidential"
    elif any(h in p for h in _CONFIDENTIAL_HINTS):
        source, sensitivity = "local_memory", "confidential"
    else:
        source, sensitivity = "local_memory", "internal"
    return {"source": source, "sensitivity": sensitivity}


def discover(root: str, max_files: int = 200) -> list:
    """Find readable knowledge files under root (recursive)."""
    base = Path(root).expanduser()
    if base.is_file():
        return [base] if base.suffix.lower() in _TEXT_EXTS else []
    out = []
    if not base.exists():
        return out
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix.lower() in _TEXT_EXTS:
            # skip noise
            if any(seg.startswith(".") and seg not in (".claude",) for seg in p.parts):
                continue
            out.append(p)
            if len(out) >= max_files:
                break
    return out


def read_text(path: Path, max_chars: int = 50_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def absorb_file(brain, cfg, path: Path, extract=True, root: Path = None) -> dict:
    """Absorb one file: store as a document (with inferred sensitivity) and,
    if an AI key is present and extract=True, pull concrete facts into the
    review queue (machine-sourced) rather than straight into canonical.

    Returns {doc_id, facts_staged, sensitivity, source}.
    """
    from motherflame import documents, conflicts
    meta = classify(path, root=root)
    text = read_text(path)
    if not text.strip():
        return {"doc_id": "", "facts_staged": 0, **meta}

    did = documents.add_document(
        brain, title=path.name, text=text,
        source=str(path), category="Document", sensitivity=meta["sensitivity"],
    )

    staged = 0
    has_ai = bool(cfg.get("agent_api_key")) or cfg.get("provider") == "ollama"
    if extract and has_ai:
        from motherflame import agent
        for f in agent.llm_research_extract(cfg, text, str(path)):
            # machine-extracted → stage to review queue, tagged local authority
            conflicts.stage_or_add(
                brain, f["category"], f["key"], f["value"],
                source=meta["source"], confidence=f.get("confidence", 0.75),
                review=True, sensitivity=meta["sensitivity"], via="local_sync",
                original_source=str(path),
            )
            staged += 1
    return {"doc_id": did, "facts_staged": staged, **meta}


def absorb(brain, cfg, root: str, max_files: int = 200, extract=True) -> dict:
    """Absorb a folder/file tree. Returns a summary."""
    files = discover(root, max_files=max_files)
    base = Path(root).expanduser()
    root_dir = base if base.is_dir() else base.parent
    docs, facts, confidential = 0, 0, 0
    for p in files:
        res = absorb_file(brain, cfg, p, extract=extract, root=root_dir)
        if res["doc_id"]:
            docs += 1
        facts += res["facts_staged"]
        if res["sensitivity"] == "confidential":
            confidential += 1
    return {
        "files": len(files), "documents": docs,
        "facts_staged": facts, "confidential_docs": confidential,
    }
