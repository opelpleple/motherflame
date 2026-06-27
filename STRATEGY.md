# Motherflame — Project Strategy & Roadmap

> Grill → Find Gap → Optimize
> Written after real market research (Tana, Augment Code, Anthropic context engineering)

---

## 1. GRILL — Which direction should this project take?

### What the market is telling us (from research)
- **"The models are not the bottleneck anymore"** — a frontier model that doesn't know your company still answers confidently and wrong → **knowledge is the bottleneck**
- **"A stale source is worse than none, because the agent trusts it"** — freshness of context matters most
- **"The hard part is having a current, connected, permissioned source to retrieve from"** — RAG isn't the hard part; maintaining the source is
- Knowledge gets trapped in 6 places: disconnected prompts, isolated sessions, individual configs, fragmented tools, non-transferable workflows, siloed history

### Landscape — competitors
| Player | Position | Weakness |
|---|---|---|
| **Tana** | "company context layer" + MCP server | You must migrate work into their workspace (lock-in, heavy) |
| **Augment Code** | cross-agent org memory | Enterprise dev teams, heavy infra, expensive |
| **Glean / Notion AI** | enterprise knowledge search | You must live inside their ecosystem |

### Motherflame's Wedge (the winning difference)
> **"Harvest context from where it already lives — each person's files and agents — into a central brain, with no migration, using your own AI key, at $1/seat."**

- Tana = migrate into their workspace → Motherflame = **stay where you are, just harvest it up**
- Augment = enterprise dev → Motherflame = **every team, every size, Obsidian-cheap**
- Everyone else = their AI → Motherflame = **bring-your-own-AI (variable cost = 0)**

**Answer: the direction is "the lightweight org-brain that you don't migrate into" — a wedge nobody plays because everyone wants to be the platform you move into.**

---

## 2. FIND GAP — Gaps to fill (ordered by priority)

### 🔴 Gap 1: Freshness — the thing the market says matters most, and we don't have it
Right now harvest is a **one-time snapshot**. Research is clear: "stale source is worse than none."
- No re-scan / incremental update
- No way to know which facts are old vs. new
- No "this file changed → update the brain"

### 🔴 Gap 2: "Collective brain" is just a name — it's actually local-only
The positioning sells a "collective/central brain everyone can access," but today:
- Each person has their own `~/.motherflame/brain.json`
- **No sync, no server, no real sharing**
- This is the gap that makes the whole value prop not yet true

### 🟠 Gap 3: No MCP server — Tana wins here
- Tana: external agents (Claude Code) connect to the brain via MCP
- Motherflame: the brain only works inside its own CLI
- Without MCP it's not truly a "context layer for ANY agent"

### 🟠 Gap 4: Weak harvest quality (keyword regex)
- Currently uses keyword matching (`"pricing"`, `"team of"`) → only catches the surface
- Competitors use real RAG / LLM extraction
- We already have an LLM key (from setup) but harvest doesn't use it

### 🟡 Gap 5: No "capture from work"
- Tana highlights "context captured as work happens"
- Motherflame = manual `/harvest` only
- Missing: watch folder, git hook, or scheduled re-scan

---

## 3. OPTIMIZE — Execute (improve the real thing, in order)

### Phase 1 — Make the value prop real (first two gaps)
**1A. LLM-powered harvest** (fill Gap 4 first — easy + high impact)
- Replace keyword regex → send file content to the LLM for real signal extraction
- Key already exists, just wire the pipeline
- Result: fact quality improves immediately

**1B. Freshness layer** (fill Gap 1)
- Store file hash + mtime in the ledger
- `/refresh` → re-scan only changed files
- Mark facts fresh/stale by source file

### Phase 2 — Make "collective" real (Gap 2)
- Zero-knowledge cloud sync (as planned: Flame Key encrypts client-side)
- `motherflame push` / `motherflame pull` → sync the brain across machines
- Start simple: shared brain.json via cloud storage + client-side encryption

### Phase 3 — Open it to every agent (Gap 3)
- MCP server: `motherflame mcp` → expose the brain as an MCP endpoint
- Claude Code / Cursor / any MCP client can connect
- This is what makes it a "protocol" on the path: Product → Protocol → Platform

### Phase 4 — Capture from work (Gap 5)
- Watch mode / git post-commit hook → auto-harvest
- Scheduled re-scan

---

## Recommended order of execution
1. **1A LLM harvest** ← start here (high impact, low effort, key already exists)
2. **1B Freshness** ← next, fixes the gap the market says matters most
3. **Phase 2 sync** ← makes "collective" real
4. **Phase 3 MCP** ← opens up the ecosystem

> Rationale: 1A + 1B make what we already have *genuinely good* first, then we expand (sync/MCP) — rather than piling new features on a weak foundation.
