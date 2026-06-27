# Concepts

A quick glossary so the rest of the docs (and the CLI) make sense.

## Org Brain
The structured knowledge base Motherflame builds about *your* organization —
facts grouped into Company, Product, Team, Voice, and Strategy. Stored locally at
`~/.motherflame/brain.json`. This is the thing every agent queries.

## Flame Key
The identifier + encryption key for an Org Brain. It does two jobs:
- **Identity** — which brain you're working with (`mf_acme_a1b2c3…`)
- **Encryption** — it's the key that encrypts your brain before any sync

You do **not** need a server or signup to get one. Run `motherflame connect`
with no argument and Motherflame generates a local key for you. Share that same
key with a teammate and you both read/write the same synced brain.

## Fact
A single piece of knowledge: `category · key · value` (e.g. `Product · pricing ·
$48k/year`). Facts have a `confidence` and a `source`.

## Claim vs. Canonical
Motherflame separates **evidence** from **truth**:
- **Claims** — every assertion anyone harvested, kept forever, never overwritten.
  Two teammates can hold different `pricing` claims and both survive.
- **Canonical** — exactly one resolved value per key (the "single source of
  truth"), computed from the claims by the resolver.

## Contested
A key is *contested* when ≥2 live claims hold materially different values and no
higher rule has settled it. Contested facts are flagged everywhere (query
answers, `/conflicts`) so you never state a disputed number as fact.

## Resolution ladder
How the canonical value is chosen, highest priority first:
1. **Manual** — a human ran `/resolve`
2. **Owner** — the key/category has a designated owner (set via `/owner`)
3. **Consensus** — the value the most distinct sources agree on
4. **Recency × confidence** — newest, most-confident claim (fallback)

## Tombstone
A retracted claim. Deletes are tombstoned (not removed) so a teammate's stale
copy can't resurrect them on the next sync. (CRDT-style delete.)

## Harvest
Scanning your files (`.md`, `.html`, `.txt`, `.pdf`) to extract facts. Two modes:
- **LLM extraction** — high quality, needs an AI key (`motherflame setup`)
- **Keyword fallback** — works with no key, lower precision

## Member identity
Your name on the team (`motherflame setup` asks for it). It tags every claim you
harvest so **owner authority** can tell teammates apart.

## Token budget
When the brain feeds an LLM, Motherflame sends only the most relevant facts that
fit a token budget (`context_budget_tokens`, default 1500) — not the whole brain.
Keeps cost bounded as the brain grows.

## MCP server
`motherflame mcp` exposes the brain over the [Model Context Protocol](https://modelcontextprotocol.io)
so external agents (Claude Code, Cursor) can query and update it.

## Backends (sync)
- **local** (default) — ciphertext in `~/.motherflame/cloud/`, single machine
- **git** — set `sync_remote` to a git URL; `push`/`pull` commit encrypted blobs
  to a repo you control, so a real team shares one brain
