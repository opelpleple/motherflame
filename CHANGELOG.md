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
- Resolution ladder: manual > owner > consensus > recency×confidence
- Key canonicalization — `pricing` / `price` / `pricing_model` collapse to one fact
- Value equality — `$48k` / `48,000` / `USD 48000` treated as the same number
- Tombstones — deletes survive merges (CRDT-style)
- `/conflicts`, `/resolve` (incl. bulk auto-resolve), `/owner` commands
- Contested facts flagged in every query answer (no false confidence)

### Sync (zero-knowledge)
- Client-side encryption: scrypt key derivation + SHA-256 CTR + HMAC (encrypt-then-MAC)
- `push` / `pull` with **local** (default) and **git** backends for real team sync
- Claim-union merge — no teammate's data is lost

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
