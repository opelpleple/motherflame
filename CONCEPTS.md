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

You do **not** need a server or signup to get one. Run `motherflame create
"<name>"` to start a new brain (it generates and prints the key), or `motherflame
join <key>` to join an existing one. Share that same key with a teammate and you
both read/write the same synced brain.

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
4. **Trust score** — the most *trustworthy* claim wins, ties broken by recency

## Trust score
A 0–1 score per claim: `source_authority × verification_bonus × staleness_decay ×
confidence`. Human/manual/verified sources outrank chat, which outranks files and
keyword guesses; trust decays as a claim ages. This is the ladder's tier-4
tiebreak — so a fresh, human-verified fact beats a confident-but-old LLM guess.

## Verified
A claim a human explicitly confirmed (`/verify` or the `verify_fact` MCP tool).
Verification is a trust signal kept *separate from and above* the LLM's own
confidence — verified claims win conflicts against unverified ones.

## Temporality (valid_from / valid_until)
A claim can be valid only for a time window. `resolve_key(brain, key,
as_of="2024-06-01")` answers "what was true then" — essential when pricing,
headcount, or regulation changes over time.

## Review queue (pending)
With `review_required` enabled, machine-extracted claims don't enter the canonical
truth directly — they wait in `brain["pending"]` for a human to approve or reject
(`/review`). Human-sourced claims (chat / interview / manual) skip the gate.

## Tombstone
A retracted claim. Deletes are tombstoned (not removed) so a teammate's stale
copy can't resurrect them on the next sync. (CRDT-style delete.) Created by
`/forget` or the `forget_fact` MCP tool.

## Harvest
Scanning your files (`.md`, `.html`, `.txt`, `.pdf`) to extract facts. Two modes:
- **LLM extraction** — high quality, needs an AI key (`motherflame setup`)
- **Keyword fallback** — works with no key, lower precision

PDFs are read via `pdftotext`/`pypdf` (never raw bytes). The first AI harvest
asks for explicit consent, because it sends file contents to your AI provider.

## Connector
A pluggable source of context. Anything implementing `BaseConnector.fetch()` can
yield `Document`s into the harvester (Slack, Notion, Drive, …). Core ships a
reference `local_files` connector; others register via `connectors.register`.

## Eval harness
A way to measure retrieval quality: run a golden Q&A set through the brain's own
retrieval and get precision@k / recall / hit-rate (`motherflame.eval.run`). Lets
you tell whether a change improved or regressed answers instead of guessing.

## Member identity
Your name on the team (`motherflame setup` asks for it). It tags every claim you
harvest so **owner authority** can tell teammates apart.

> Honest limit: identity is a self-declared string today — anyone with the Flame
> Key can claim any name. Verified per-member identity (SSO) is on the roadmap.

## Token budget
When the brain feeds an LLM, Motherflame sends only the most relevant facts that
fit a token budget (`context_budget_tokens`, default 1500) — not the whole brain.
Keeps cost bounded as the brain grows.

## Doctor
`motherflame doctor` — a flame-themed readiness checklist (AI agent · Org Brain ·
Encryption · Knowledge · Team sync). Each item is lit or a dim ember, with a hint
to fix what's missing, plus a verdict (cold start / getting warm / fully lit).

## Team dashboard
`motherflame team` — shows the Flame Key, the sync remote with a **live** health
check (reachable / auth_failed / not_found / …), member count, last push/pull, and
a copy-paste invite block for teammates.

## MCP server
`motherflame mcp` exposes the brain over the [Model Context Protocol](https://modelcontextprotocol.io)
so external agents (Claude Code, Cursor) can query and update it. Tools:
`query_brain`, `list_facts`, `add_fact`, `forget_fact`, `verify_fact`. Run with
`MOTHERFLAME_MCP_READONLY=1` to expose read-only (write tools refused).

## Backends (sync)
- **local** (default) — ciphertext in `~/.motherflame/cloud/`, single machine
- **git** — set `sync_remote` to a git URL; `push`/`pull` commit encrypted blobs
  to a repo you control, so a real team shares one brain
