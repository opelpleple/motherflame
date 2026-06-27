<div align="center">

# 🔥 Motherflame

### The Org Brain for teams that use AI

**Harvest your company's context once. Let every AI agent — yours, Claude, Cursor — draw on it forever.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#-zero-dependencies)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-8A2BE2.svg)](https://modelcontextprotocol.io)
[![Zero-Knowledge](https://img.shields.io/badge/sync-zero--knowledge-orange.svg)](#-zero-knowledge-sync)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v0.1.0-success.svg)](#)

*Bring your own AI key. $1/seat economics. Your data never leaves your control.*

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

🔥 TrustFinance Org Brain · 18 items
Connected: openai/gpt-4o-mini  ·  session 20260628-005937
Type a message, '/' for commands, or /exit to quit.

you › what are our pricing tiers?
  ⚙ query_brain(topic=pricing) → [Product] pricing: 18k/48k/100k THB/year...
ai  › Three Listing tiers: 18,000 / 48,000 / 100,000 THB per year.

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
# 1. Install
git clone https://github.com/opelpleple/motherflame
cd motherflame && pip install -e .

# 2. Connect your own AI (Anthropic / OpenAI / Ollama — arrow-key picker)
motherflame setup

# 3. Connect your Org Brain
motherflame connect mf_yourcompany

# 4. Harvest context — pick folders from a checkbox list (with file counts)
motherflame start

# 5. Just run it — drops you straight into the agent
motherflame
```

That's it. Type `/` any time to see every command.

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

**Modules** (all pure-stdlib Python):

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
- **Cipher:** SHA-256 keystream in CTR mode
- **Authentication:** HMAC-SHA256, encrypt-then-MAC

Wrong key? Tampered bytes? Decryption **fails loudly** — never silently returns garbage. All built from the Python standard library, no `cryptography` dependency.

```bash
motherflame push    # encrypt locally → upload ciphertext
motherflame pull    # download ciphertext → decrypt locally → merge (newest fact wins)
```

---

## 🔌 Connect any agent (MCP)

Motherflame speaks the [Model Context Protocol](https://modelcontextprotocol.io). Point Claude Code, Cursor, or any MCP client at it:

```jsonc
// MCP client config
{
  "mcpServers": {
    "motherflame": {
      "command": "motherflame",
      "args": ["mcp"]
    }
  }
}
```

Exposes three tools to the external agent: `query_brain`, `list_facts`, `add_fact`. This is what turns Motherflame from a *product* into a *protocol* — your company context, available to the whole agent ecosystem.

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
| Pricing | **$1/seat** | $$$ | $$$$ | $$$ |

---

## 🪶 Zero dependencies

The entire CLI — agent loop, encryption, MCP server, TTY pickers — is built on the **Python standard library**. Nothing to `pip install` but Motherflame itself. Clone it, read it, audit it, fork it.

```python
requires-python = ">=3.9"
dependencies = []   # yes, really
```

---

## Roadmap

- [x] Agent chat with tool-use + planning
- [x] LLM-powered harvest + freshness
- [x] Zero-knowledge client-side encryption
- [x] MCP server
- [ ] HTTP cloud backend (currently a local stand-in)
- [ ] Watch mode / git hooks — capture context as work happens
- [ ] Per-fact access control
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
