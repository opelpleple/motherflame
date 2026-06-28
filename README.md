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
| ⚖️ | **Conflict resolution** | Two-layer brain (claims → canonical); a resolution ladder settles contradictions instead of last-write-wins |
| 🏅 | **Trust scoring** | Every fact is scored by source authority × human-verification × staleness × confidence — the most *trustworthy* claim wins, not the newest |
| ✅ | **Human verification** | `verify` marks a fact human-confirmed; ranked above unverified LLM guesses |
| 🕰️ | **Temporality** | Facts carry `valid_from`/`valid_until`; ask "what was true on date X" |
| 📥 | **Review queue** | Optionally gate machine-extracted facts for human approval before they enter the canonical truth |
| 🔐 | **Zero-knowledge team sync** | `push`/`pull` your brain across the team — AES-256-GCM encrypted client-side |
| 🔌 | **MCP server** | Connect Claude Code, Cursor, or any MCP agent to your Org Brain |
| 🧩 | **Connectors** | A pluggable interface so any source (Slack, Notion, Drive…) can feed the brain |
| 📊 | **Eval harness** | Golden Q&A → precision@k / recall, so retrieval changes are measured not guessed |
| 📑 | **Provenance** | `/sources` + `/history` — know exactly what was scanned and where every fact came from |
| 🩺 | **Doctor & Team** | `doctor` (flame-themed readiness checklist) and `team` (sync dashboard + invite) |
| 💾 | **Sessions** | Conversations persist; resume context with `--resume` |

---

## Commands

```
Setup
  motherflame setup              Connect your AI key (Anthropic / OpenAI / Ollama)
  motherflame create [name]      Start a NEW Org Brain (generates a Flame Key)
  motherflame join <key>         Join an EXISTING Org Brain (pulls the team's brain)
  motherflame connect [key]      Low-level: set a Flame Key (prefer create / join)

Core
  motherflame                    Smart entry → splash, or drops into chat when ready
  motherflame doctor             Flame-themed readiness checklist + hints
  motherflame team               Team dashboard: key, remote health, members, invite
  motherflame start              Harvest org context (AI extraction + interview)
  motherflame chat [--resume]    Talk to your Org Brain agent (tool-use, planning)
  motherflame query "<q>"        One-off question (LLM answer, or keyword fallback)
  motherflame brain              View everything in the Org Brain
  motherflame status             Connection & brain status

Sync (zero-knowledge)
  motherflame push               Pull-first, then encrypt & sync your brain to the remote
  motherflame pull               Pull & merge teammates' context
  motherflame config set sync_remote <git-url>   Bind a git remote for team sync

Integrate
  motherflame mcp                Run MCP server (for Claude Code / Cursor / any MCP agent)
```

### In-chat slash commands

Type `/` and pick from a menu, or type the command directly:

```
/plan        Plan a multi-step task, then execute it
/harvest     Scan folders → add facts
/refresh     Re-scan only changed files (freshness)
/optimize    Find gaps, duplicates, coverage + AI suggestions
/conflicts   Show contested facts (teammates disagree)
/resolve     Settle a contested fact — you pick the truth
/verify      Mark a fact as human-verified (trusted above LLM guesses)
/forget      Retract a fact — tombstoned so it won't return on sync
/review      Approve/reject machine-extracted facts in the review queue
/owner       Assign who owns a fact/category (their claim wins)
/sources     Where each fact came from (provenance)
/history     What's been scanned & sent to the brain
/gaps        What's still missing
/brain       Show the full brain
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
| `core.py` | Commands, harvest, display, the interactive REPL, splash/doctor/team |
| `cli.py` | Argument dispatch + flag parsing |
| `runtime.py` | Agentic tool-use loop + planning (OpenAI + Anthropic), retry/backoff |
| `agent.py` | LLM calls, arrow/checkbox TTY pickers, providers, HTTP retry |
| `conflicts.py` | Claims layer, resolution ladder, canonicalization, review queue, verify |
| `trust.py` | Per-fact trust scoring (authority × verification × staleness × confidence) |
| `tokens.py` | Token-budget ranking — fits the most relevant facts into context |
| `connectors.py` | `BaseConnector` contract + registry (pluggable sources) |
| `eval.py` | Golden Q&A retrieval eval (precision@k / recall / hit-rate) |
| `redact.py` | Best-effort PII/secret redaction before text leaves the machine |
| `ledger.py` | Provenance events + file fingerprints (freshness) |
| `sessions.py` | Persistent chat history |
| `sync.py` | Client-side AES-256-GCM encryption, git/local backends, remote health |
| `mcp_server.py` | JSON-RPC MCP server over stdio (query/list/add/forget/verify) |
| `splash.py` | The launch splash screen (figlet + flame box) |

---

## ⚖️ Single source of truth — how contradictions are settled

Most "knowledge bases" do last-write-wins: whoever saved most recently is "right".
That quietly corrupts a shared brain. Motherflame keeps a **two-layer** model:

- **Claims** — every assertion ever made about a key (raw evidence, never overwritten).
- **Canonical** — the single resolved truth, recomputed from claims.

When claims disagree, a **resolution ladder** decides — in order:

1. **Manual** — a human ran `/resolve` and picked the answer. Wins outright.
2. **Owner** — the owner of that fact/category (`/owner`) — their claim wins.
3. **Consensus** — the value the most distinct sources independently assert.
4. **Trust score** — the most *trustworthy* claim (see below), ties broken by recency.

Keys are **canonicalized**, so `pricing` / `price` / `pricing_model` collapse to one
fact instead of drifting into three. Values are normalized too — `$48k`, `48,000`,
and `USD 48000` are treated as the same number.

### 🏅 Trust scoring

Every claim gets a score, so a fresh human-verified fact outranks a confident-but-old
LLM guess:

```
trust = source_authority × verification_bonus × staleness_decay × confidence
```

- **Source authority** — `manual`/`verified` (human) > `chat` > `interview` > file/keyword.
- **Verification** — `verify` a fact and it's ranked above anything unverified.
- **Staleness** — trust decays as a claim ages (configurable half-life).
- **Confidence** — the extractor's own 0–1 score.

### 🕰️ Temporality

Claims can carry `valid_from` / `valid_until`. Ask the brain what was true at a point
in time — essential when pricing, headcount, or policy changes over a year:

```python
resolve_key(brain, "pricing", as_of="2024-06-01")   # → last year's price
```

### 📥 Review queue

Turn on `review_required` and **machine-extracted** facts land in a pending queue for
a human to approve or reject before they enter the canonical truth. Human-sourced
claims (chat / interview / manual) skip the gate. Manage it with `/review`.

### ♻️ Tombstones (CRDT-style delete)

`/forget` doesn't just delete — it tombstones, so a teammate's stale copy can't
resurrect the fact on the next sync.

---

## 🧩 Connectors — feed the brain from anywhere

Local files are one source; real org knowledge also lives in Slack, Notion, Drive,
Jira, email. Rather than hard-code each, Motherflame defines a tiny contract:

```python
from motherflame.connectors import BaseConnector, Document, register

@register
class MyConnector(BaseConnector):
    name = "my_source"
    def fetch(self):
        yield Document(title="Q3 Plan", text="...", source_id="notion:abc")
```

Core ships a reference `local_files` connector; remote connectors live outside core
so the CLI stays lean. Every `Document` flows through the same extraction, redaction,
claims, and review-queue path — so trust/temporality/PII guarantees apply uniformly.

---

## 📊 Eval harness — measure, don't guess

A brain is only worth feeding to agents if it retrieves the *right* facts. Point a
golden Q&A set at it and get precision@k / recall / hit-rate over the brain's own
retrieval — so you can tell whether a change (new aliases, trust weighting) actually
helped:

```python
from motherflame import eval as mf_eval
report = mf_eval.run(brain, golden, k=3)
print(mf_eval.format_report(report))
```

---

## 🩺 Doctor & 👥 Team

```bash
motherflame doctor   # flame-themed readiness checklist: AI · Brain · Encryption ·
                     # Knowledge · Team sync — each lit or a dim ember, with a hint
motherflame team     # dashboard: Flame Key, remote health (live), members, last
                     # sync, and a copy-paste invite block for teammates
```

### Set up team sync from chat (no config commands)

You don't have to run `config set sync_remote` by hand — just ask the agent:

```
you › I want my team to share this brain
ai  › Sure — do you have a git repo for it, or should I create one?
you › create one
ai  › ✓ Created private repo acme/acme-brain and set it as your sync remote (reachable).
      Run `motherflame push` to publish; teammates run
      `motherflame join mf_acme_… --remote https://github.com/acme/acme-brain.git`.
```

Behind the scenes the agent calls `create_team_repo` (via the `gh` CLI) or
`setup_team_sync` (if you give it a URL), then health-checks the remote — the same
tools are available to external agents over MCP.

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

Exposes seven tools to the external agent: `query_brain`, `list_facts`, `add_fact`,
`forget_fact`, `verify_fact`, `setup_team_sync`, and `create_team_repo`. The agent
decides *when* to call them from their descriptions — e.g. it calls `query_brain`
whenever it needs company-specific facts instead of guessing, `add_fact` to write
something it learned back into the brain, or `create_team_repo` to spin up a private
synced repo for the team. Returns are token-budgeted and carry **provenance**
(`[source: …]`), and contested facts are flagged so the agent never states a disputed
value as settled.

> **Read-only mode.** The MCP server has no transport-level auth (it's stdio,
> local by design). If you connect an agent you don't fully trust, run it
> read-only so it can query but not write:
> `MOTHERFLAME_MCP_READONLY=1 motherflame mcp` (or set `readonly_mcp: true` in
> config). All write tools (`add_fact`, `forget_fact`, `verify_fact`) are then refused.

---

## Why Motherflame (vs. the alternatives)

| | Motherflame | Tana | Augment Code | Notion AI |
|---|:---:|:---:|:---:|:---:|
| Harvest from **existing files** | ✅ | ❌ | ❌ | ❌ |
| **No migration** into a new workspace | ✅ | ❌ | ❌ | ❌ |
| **Bring-your-own-AI** key | ✅ | ❌ | ❌ | ❌ |
| **Zero-knowledge** encryption | ✅ | ❌ | ❌ | ❌ |
| **Conflict resolution** (claims → canonical) | ✅ | ❌ | ❌ | ❌ |
| **Trust scoring** on each fact | ✅ | ❌ | ❌ | ❌ |
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

**Shipped**
- [x] Agent chat with tool-use + planning
- [x] LLM-powered harvest + freshness
- [x] Zero-knowledge client-side encryption (AES-256-GCM)
- [x] MCP server (query / list / add / forget / verify)
- [x] Git-based team sync (host the encrypted repo yourself)
- [x] Conflict resolution: claims → canonical, resolution ladder, tombstones
- [x] Trust scoring, human verification, temporality, review queue
- [x] Connector interface + reference local-files connector
- [x] Eval harness (golden Q&A → precision@k)
- [x] `create` / `join` onboarding, `doctor`, `team` dashboard, launch splash
- [x] pytest suite + CI (Python 3.9 / 3.11 / 3.12)

**Planned**
- [ ] Live connectors (Slack / Notion / Drive / Jira) on the connector interface
- [ ] Semantic / vector retrieval (today: keyword + token-budget ranking)
- [ ] Watch mode / git hooks — capture context as work happens
- [ ] Per-member identity & access control (today: one Flame Key = shared access)
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
