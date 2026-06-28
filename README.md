<div align="center">

# 🔥 Motherflame

### The Org Brain for teams that use AI

**Harvest your company's context once. Let every AI agent — yours, Claude, Cursor — draw on it forever.**

[![CI](https://github.com/opelpleple/motherflame/actions/workflows/ci.yml/badge.svg)](https://github.com/opelpleple/motherflame/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Dependencies](https://img.shields.io/badge/deps-1%20(audited%20crypto)-brightgreen.svg)](#-almost-zero-dependencies)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-8A2BE2.svg)](https://modelcontextprotocol.io)
[![Zero-Knowledge](https://img.shields.io/badge/sync-zero--knowledge-orange.svg)](#-zero-knowledge-sync)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

*Bring your own AI key. Self-hosted. Your data never leaves your control.*

</div>

---

## The problem

> *"The models are not the bottleneck anymore. A frontier model that knows nothing about your company still writes a confident, generic, **wrong** answer."*

Every AI agent your team uses starts from **zero**. It doesn't know your pricing, your customers, your decisions, your voice. So everyone re-explains the same context, in every chat, forever — and the knowledge stays trapped in scattered files, individual configs, and dead Slack threads.

**Motherflame fixes this.** It harvests the context that already exists — your markdown, your docs, your notes — into one **Org Brain** that any agent can query. No migrating into a new workspace. No re-typing context. Just point it at your files and go.

---

## See it in 20 seconds

```console
$ motherflame
  🔥 Motherflame  v0.1.0
  The Org Brain for teams that use AI

🔥 Acme Org Brain · 18 items
Connected: openai/gpt-4o-mini  ·  session 20260628-005937
Type a message, '/' for commands, or /exit to quit.

you › what are our pricing tiers?
  ⚙ query_brain(topic=pricing) → [Product] pricing: Starter/Pro/Enterprise...
ai  › Three tiers: Starter $29/mo, Pro $99/mo, Enterprise custom.

you › we just raised a $2M seed round
  ⚙ add_fact(category=Company, key=seed_round, value=$2M seed) → Added
ai  › Got it — added the $2M seed round to the Org Brain.
  ✓ Org Brain updated

you › /optimize
  🔍 Org Brain Optimization Report
  Coverage by category:
    Company    ██████ 6
    Product    ████ 4
    Team       ██ 2
    ...
```

---

## Quickstart (under a minute)

```bash
# 1. Install (zero dependencies — just Python 3.9+)
git clone https://github.com/opelpleple/motherflame
cd motherflame
python3 -m venv .venv && source .venv/bin/activate   # recommended
pip install -e .
```

> **No virtualenv?** On modern macOS/Linux a bare `pip install` may be blocked
> (PEP 668). Either use the venv above, or `pipx install -e .`, or
> `pip install -e . --break-system-packages`. There are no third-party deps to
> install — only Motherflame itself.

```bash
# 2. Try it immediately — no API key, no signup
motherflame connect          # generates a local Flame Key for you
motherflame start            # harvest your files (keyword mode works key-free)
motherflame                  # drop into the agent

# 3. (Optional) Connect your own AI for high-quality extraction + chat
motherflame setup            # pick Anthropic / OpenAI / Ollama, paste your key
```

That's it. Type `/` any time to see every command. See [`CONCEPTS.md`](CONCEPTS.md)
for a glossary of terms (Flame Key, claims, contested, etc.).

### Create a new org, or join an existing one

The **Flame Key** (`mf_<org>_<hex>`) both names *and* encrypts your Org Brain.
Whoever holds it can decrypt and sync the same brain — so it's how teams share.

```bash
# Start a NEW Org Brain (you're the first member):
motherflame create "Acme"                              # solo
motherflame create "Acme" --remote git@github.com:acme/brain.git   # team-synced

#   → prints your Flame Key. Share it with teammates.

# JOIN an existing Org Brain (a teammate gave you their key):
motherflame join mf_acme_1a2b3c4d --remote git@github.com:acme/brain.git
#   → sets the key, binds the remote, AND pulls + merges the team's brain
#     so you see their knowledge right away (not an empty brain).
```

The git remote is any repo you control — the host only ever stores **ciphertext**
(zero-knowledge). Solo users can skip `--remote` and add it later with
`motherflame config set sync_remote <git-url>`.

### Two ways to run

| | No API key | With your AI key (`setup`) |
|---|---|---|
| Harvest | keyword extraction (works, lower precision) | LLM extraction (high quality) |
| Chat / query | — | full agentic chat |
| Everything else | ✅ | ✅ |

---

## What it does

| | Feature | What it means |
|---|---|---|
| 🧠 | **Org Brain** | One structured knowledge base — company, product, team, voice, strategy |
| 🤖 | **Agent chat** | A real tool-using agent (not Q&A) that reads *and writes* the brain |
| 📋 | **Planning** | `/plan` breaks a goal into steps, then executes them autonomously |
| 🌾 | **Smart harvest** | LLM extraction from your files (keyword fallback when offline) |
| ♻️ | **Freshness** | `/refresh` re-scans only files that changed since last time |
| 🔐 | **Zero-knowledge sync** | `push`/`pull` your brain across the team — encrypted client-side |
| 🔌 | **MCP server** | Connect Claude Code, Cursor, or any MCP agent to your Org Brain |
| 📑 | **Provenance** | `/sources` + `/history` — know exactly what was scanned and where every fact came from |
| 💾 | **Sessions** | Conversations persist; resume context with `--resume` |

---

## Commands

```
Setup
  motherflame setup              Connect your AI key (Anthropic/OpenAI/Ollama)
  motherflame connect <key>      Connect to your Org Brain (Flame Key)

Core
  motherflame                    Smart entry → drops into agent chat when ready
  motherflame start              Harvest org context (AI extraction + interview)
  motherflame chat [--resume]    Talk to your Org Brain agent
  motherflame query "<q>"        One-off question
  motherflame brain              View everything in the Org Brain
  motherflame status             Connection & brain status

Sync (zero-knowledge)
  motherflame push               Encrypt & sync your brain to the cloud
  motherflame pull               Pull & merge teammates' context

Integrate
  motherflame mcp                Run MCP server (for Claude Code / Cursor)
```

### In-chat slash commands

Type `/` and pick from a menu, or type the command directly:

```
/plan       Plan a multi-step task, then execute it
/harvest    Scan folders → add facts
/refresh    Re-scan only changed files (freshness)
/optimize   Find gaps, duplicates, coverage + AI suggestions
/sources    Where each fact came from (provenance)
/history    What's been scanned & sent to the brain
/gaps       What's still missing
/brain      Show the full brain
```

---

## Architecture

```
                        ┌──────────────────────────┐
   your files  ───────► │   harvest (LLM / keyword)│
   (md/html/txt/pdf)    └────────────┬─────────────┘
                                     │  fingerprints (freshness)
                                     ▼
   ┌─────────────────────────────────────────────────┐
   │                  ORG BRAIN                        │
   │   facts · gaps · provenance ledger · sessions     │
   └───────┬───────────────┬──────────────────┬───────┘
           │               │                  │
     agent chat       MCP server         push / pull
     (tool-use)    (Claude/Cursor)   (zero-knowledge sync)
```

**Modules** (stdlib Python; `sync` uses the audited `cryptography` lib):

| Module | Responsibility |
|---|---|
| `core.py` | Commands, harvest, display, the interactive REPL |
| `runtime.py` | Agentic tool-use loop + planning (OpenAI + Anthropic) |
| `agent.py` | LLM calls, arrow/checkbox TTY pickers, providers |
| `ledger.py` | Provenance events + file fingerprints (freshness) |
| `sessions.py` | Persistent chat history |
| `sync.py` | Client-side encryption + cloud backend |
| `mcp_server.py` | JSON-RPC MCP server over stdio |

---

## 🔐 Zero-knowledge sync

Your Org Brain is encrypted **on your machine** before it ever touches the network. The backend only ever sees ciphertext.

- **Key derivation:** `scrypt(flame_key, salt)` → 32-byte key
- **Cipher:** **AES-256-GCM** (authenticated encryption) via the audited
  [`cryptography`](https://cryptography.io) library — we deliberately do **not**
  hand-roll crypto.
- **Backward compat:** brains written by older versions (a hand-rolled cipher)
  are still decryptable, but everything new is AES-GCM.

Wrong key? Tampered bytes? Decryption **fails loudly** (GCM tag check) — never silently returns garbage.

> **On dependencies:** Motherflame's only runtime dependency is `cryptography`.
> For security-sensitive code, a single audited, widely-used crypto library is
> the *right* call — "no crypto dependency" would mean hand-rolling primitives,
> which is exactly what you don't want from a tool that stores company secrets.

```bash
# Solo / single machine (default — zero setup):
motherflame push    # encrypt locally → store ciphertext in ~/.motherflame/cloud/
motherflame pull    # decrypt locally → merge

# Real team sync — point at a git repo you control:
motherflame config set sync_remote git@github.com:yourco/org-brain.git
motherflame push    # commits the encrypted blob to that repo
motherflame pull    # teammates pull + merge (their claims survive, never clobbered)
```

The git backend stores **only ciphertext** in your repo — the host (GitHub/GitLab/
self-hosted) never sees your data. Merges union everyone's claims, so conflicting
values surface as *contested* rather than overwriting each other.

---

## 🔌 Connect any agent (MCP)

Motherflame speaks the [Model Context Protocol](https://modelcontextprotocol.io). Add it to your MCP client's config:

```jsonc
{
  "mcpServers": {
    "motherflame": {
      "command": "motherflame",
      "args": ["mcp"]
    }
  }
}
```

**Where that config lives:**
- **Claude Code** — run `claude mcp add motherflame -- motherflame mcp`, or edit `~/.claude.json`
- **Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
- **Cursor** — `~/.cursor/mcp.json` (or Settings → MCP)

> If `motherflame` isn't on your PATH (e.g. it's in a venv), use the absolute
> path to the executable as `command` — find it with `which motherflame`.

Exposes three tools to the external agent: `query_brain`, `list_facts`, `add_fact`. The agent decides *when* to call them from their descriptions — e.g. it calls `query_brain` whenever it needs company-specific facts instead of guessing. Returns are token-budgeted, and contested facts are flagged so the agent never states a disputed value as settled.

> **Read-only mode.** The MCP server has no transport-level auth (it's stdio,
> local by design). If you connect an agent you don't fully trust, run it
> read-only so it can query but not write:
> `MOTHERFLAME_MCP_READONLY=1 motherflame mcp` (or set `readonly_mcp: true` in
> config). `add_fact` is then refused.

---

## Why Motherflame (vs. the alternatives)

| | Motherflame | Tana | Augment Code | Notion AI |
|---|:---:|:---:|:---:|:---:|
| Harvest from **existing files** | ✅ | ❌ | ❌ | ❌ |
| **No migration** into a new workspace | ✅ | ❌ | ❌ | ❌ |
| **Bring-your-own-AI** key | ✅ | ❌ | ❌ | ❌ |
| **Zero-knowledge** encryption | ✅ | ❌ | ❌ | ❌ |
| **MCP** server for any agent | ✅ | ✅ | ⚠️ | ❌ |
| Runs as a **CLI** (scriptable) | ✅ | ❌ | ⚠️ | ❌ |
| Cost model | **Self-hosted + your own AI key** | $$$ | $$$$ | $$$ |

---

## 🪶 Almost zero dependencies

The entire CLI — agent loop, MCP server, TTY pickers, conflict engine — is built on the **Python standard library**. The **one** runtime dependency is [`cryptography`](https://cryptography.io) for AES-256-GCM, because security code should use audited primitives, not hand-rolled ones. Clone it, read it, audit it, fork it.

```python
requires-python = ">=3.9"
dependencies = ["cryptography>=42"]   # audited AES-256-GCM — the only one
```

---

## 🔒 Privacy: what leaves your machine

Be deliberate about this — it's the difference between safe and sorry:

- **Encrypted sync** (`push`/`pull`) only ever transmits **ciphertext**. Safe.
- **AI harvest** sends the **contents** of the files you scan to your AI provider
  (OpenAI/Anthropic/etc). **Bringing your own key does NOT make this private** —
  the text leaves your machine. Motherflame masks emails/keys/cards/SSNs with
  regex first, but **regex redaction is best-effort, not a guarantee**.
- Motherflame asks for explicit consent before the first AI harvest, and you can
  always choose **local keyword extraction** (nothing leaves your machine).

**Do not point AI harvest at folders containing real customer PII or
credentials.** Use keyword mode, or a local model (Ollama), for sensitive data.

---

## Roadmap

- [x] Agent chat with tool-use + planning
- [x] LLM-powered harvest + freshness
- [x] Zero-knowledge client-side encryption
- [x] MCP server
- [x] Git-based team sync (host the encrypted repo yourself)
- [x] pytest suite + CI
- [ ] Watch mode / git hooks — capture context as work happens
- [ ] Per-member access control (today: one Flame Key = shared access)
- [ ] Web dashboard

See [`STRATEGY.md`](STRATEGY.md) for the full product thesis and gap analysis.

---

## Contributing

PRs welcome. The codebase is small, readable, and dependency-free by design.

```bash
git clone https://github.com/opelpleple/motherflame
cd motherflame && pip install -e .
```

---

## License

MIT — see [`LICENSE`](LICENSE). Use it, fork it, ship it.

<div align="center">

**🔥 Light your org's flame.**

</div>
