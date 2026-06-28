# Changelog

All notable changes to Motherflame are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] — Unreleased

### Semantic retrieval (P1 — pluggable, opt-in)
- **`embeddings.py`** — text→vector providers. `HashingEmbedding` (pure stdlib,
  offline, zero-dep, the safe default) and `OpenAIEmbedding` (user's own key,
  `text-embedding-3-small`, batched, always falls back to hashing on any error so
  retrieval never breaks). `cosine()` in stdlib math.
- **Embedding cache** — `brain["embeddings"]` keyed by (provider, content) hash;
  unchanged items are never re-embedded.
- **`SemanticRetriever`** (`retrievers/semantic.py`) — ranks facts + document
  chunks by cosine similarity, plugs into the existing `BaseRetriever` seam.
  Registered as `"semantic"`; keyword stays the default. Finds paraphrases that
  share no keywords.
- **`reindex` command** + `config set retrieval semantic` switch; `doctor` shows
  the active retrieval mode and vector count. `query_brain` honors the configured
  retriever.
- Privacy/cost note: OpenAI embeddings send content out + cost money, so semantic
  is **opt-in**; the hashing default keeps everything offline.

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

### Scaling to large orgs (documents, categories, retrieval)
- **Document store** (`documents.py`) — long-form knowledge (plans, memos,
  runbooks) stored as chunked snapshots in `brain["documents"]`, not crammed into
  a 300-char fact. Rule: a document is a *snapshot*, a fact is the *truth* — docs
  never override facts, they're citable reference. `docs list/show/add` command +
  `list_documents`/`get_document` MCP tools. Fact value cap raised 300 → 1000.
- **Dynamic categories** — categories are now open-ended (Legal, Finance, Eng,
  Sales, …) with a `canonical_category` alias map so Eng/Engineering/Dev collapse
  to one instead of fragmenting (the same drift guard facts already had).
- **Retrieval interface** (`retrieval.py`) — pluggable `BaseRetriever` ranking
  over facts AND document chunks. Default `KeywordRetriever` is pure stdlib;
  a semantic/vector retriever can register and take over without touching callers
  (the honest path to scale). `query_brain` now surfaces relevant doc passages.
- Web research keeps each fetched page as a document snapshot, not just the
  short facts squeezed out of it.

### Onboarding & team UX
- **`create` / `join`** — explicit "start a new org" vs "join an existing one".
  `join` actually pulls + merges the team's brain (not just stores the key).
- **`doctor`** — flame-themed readiness checklist (AI · Brain · Encryption ·
  Knowledge · Team sync) with per-item hints and a gradient progress bar.
- **`team`** — dashboard: Flame Key, live remote health check, members, last
  push/pull, and a copy-paste invite block.
- **`sync.check_remote()`** — probes a git remote (`git ls-remote`, no clone, no
  credential prompt) and classifies reachable / auth_failed / not_found /
  no_network, so sync problems surface instead of failing silently.
- **`push` pulls first** — merges teammates' changes before pushing to avoid
  clobbering; records `last_push` / `last_pull`.
- **Launch splash** (`splash.py`) — figlet wordmark + ASCII flame box with live
  status and a context-aware next-step hint, shown on bare `motherflame` / chat.

### Security & reliability
- **AES-256-GCM** client-side encryption via the audited `cryptography` lib
  (replaced a hand-rolled cipher; legacy blobs still decrypt).
- **LLM retry/backoff** on 429/529/503 across all call sites; configurable
  `max_tokens`; tool-loop returns a final answer instead of discarding work.
- **Harvest error visibility** — failed files are counted and reported, not
  silently dropped. Real PDF extraction (`pdftotext`/`pypdf`).
- **Cross-process lock** around brain read-modify-write (prevents lost updates
  when chat + MCP write concurrently).
- **89→ tests**, CI on Python 3.9 / 3.11 / 3.12.

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
