# Changelog

All notable changes to Motherflame are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — Unreleased

The first usable version. Built as an org-brain CLI agent that any organization
can fork and self-host.

### Core
- Interactive agent chat with a tool-use loop (query / add / list facts, planning)
- LLM-powered harvest with keyword fallback; folder + file-type pickers
- One-off `query`, `brain`, `status`, `start` commands
- Persistent sessions (`chat --resume`) and a provenance ledger

### Single source of truth (conflict manager)
- Two-layer brain: **claims** (evidence, never clobbered) vs **canonical** (truth)
- Resolution ladder: manual > owner > consensus > **trust score**
- Key canonicalization — `pricing` / `price` / `pricing_model` collapse to one fact

### Trust, time & governance (universal — every org's knowledge needs this)
- **Trust scoring** per fact: source authority × human verification × staleness
  decay × confidence — the resolver picks the most *trustworthy* claim, not just
  the newest. (`trust.py`)
- **`verify_fact`** — mark a fact human-verified; ranked above unverified LLM
  claims. Exposed as a chat command, an MCP tool, and `conflicts.verify_claim`.
- **Temporality** — claims carry `valid_from` / `valid_until`; `resolve_key(..., as_of=)`
  answers "what was true on date X" (pricing/regulation that changed over time).
- **Review queue** — with `review_required`, machine-extracted claims stage in a
  pending queue for human approve/reject before entering canonical truth
  (human-sourced claims skip the gate). `/review` command.

### Coverage & quality (universal)
- **Connector interface** (`connectors.py`) — a tiny `BaseConnector` contract +
  registry so any source (Slack, Notion, Drive, …) can feed the harvester. Ships
  a reference `local_files` connector; remote connectors live outside core.
- **Eval harness** (`eval.py`) — golden Q&A → precision@k / recall / hit-rate over
  the brain's own retrieval, so changes are measured, not guessed.
- Value equality — `$48k` / `48,000` / `USD 48000` treated as the same number
- Tombstones — deletes survive merges (CRDT-style)
- `/conflicts`, `/resolve` (incl. bulk auto-resolve), `/owner` commands
- Contested facts flagged in every query answer (no false confidence)

### Sync (zero-knowledge)
- Client-side **AES-256-GCM** (authenticated encryption) via the audited
  `cryptography` library — not hand-rolled. Legacy blobs still decrypt.
- `push` / `pull` with **local** (default) and **git** backends for real team sync
- Claim-union merge — no teammate's data is lost; concurrent push retries+merges

### Integrate
- MCP server (`motherflame mcp`) — connect Claude Code / Cursor / any MCP agent
- Token budget manager — sends only the most relevant facts within a token budget

### Reliability & privacy
- Atomic writes (temp + fsync + `os.replace`) with `.bak` fallback and auto-recovery
- No file cap on harvest (configurable ceiling) with progress feedback
- PII/secret redaction before content is sent to any LLM (on by default)
- Local Flame Key generation — no server or signup required to start

### Tooling
- pytest suite (`tests/`) + GitHub Actions CI on Python 3.9 / 3.11 / 3.12
- Zero runtime dependencies (Python standard library only)
