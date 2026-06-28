# Motherflame v0.2 Architecture Guide

## Overview

Motherflame is a **distributed, encrypted team knowledge system** that bridges shallow web facts (~30, ~1 year stale) with deep local knowledge (8+ memory files, confidential, current).

**Core innovation:** Team members work independently on local files, sync via encrypted push/pull, and reach consensus through authority tiers & conflict resolution — no silent data loss, no server-side plaintext exposure.

---

## The 8 Architectural Gaps (All Closed in v0.2)

### Gap A: Freshness — Local Knowledge Ingestion ✅

**Problem:** Web facts are 1 year stale. Local markdown files are current but scattered.

**Solution:**
- `motherflame absorb <path>` scans local files
- Auto-extracts facts via LLM (if AI key present)
- Sensitivity classifier tags by path (`.claude/` → confidential, `/memory/` → confidential)
- Facts queued for review before merge

**Implementation:** `motherflame/localsync.py`

```python
# Example: absorb ~/.claude/memory/funding.md
resolver = CoreferenceResolver()
items = resolver.build_from_facts(extracted_items)
# Now "Series A" from local file beats "Series A (rumor)" from web
```

---

### Gap B: Authority — 5-Tier Confidence Model ✅

**Problem:** Which fact wins when people disagree? "Series A" vs "Series B"?

**Solution:** Tiered authority — higher tiers override lower, always

| Tier | Source | Confidence | Notes |
|------|--------|------------|-------|
| 1 | manual (you typed it) | 1.0 | Highest authority |
| 2 | verified (team signed off) | 1.0 | - |
| 3 | confidential (internal doc) | 0.97 | Can't be overridden by web |
| 4 | interview (team meeting) | 0.95 | - |
| 5 | local_memory (your files) | 0.92 | - |
| 6 | chat (conversation) | 0.9 | - |
| 7 | document (public doc) | 0.6 | - |
| 8 | web (public website) | **0.5 capped** | Never overrides confidential |

**When conflicts arise:** System picks the fact with highest confidence.

**Implementation:** `motherflame/trust.py`

```python
# stage: Series A (confidence 0.95, confidential)
# vs
# stage: Series B (confidence 0.6, chat)
# → Winner: Series A (higher confidence)
```

---

### Gap H: Sensitivity — Public vs Confidential ✅

**Problem:** Confidential facts (funding, contracts, salaries) shouldn't leak to remote.

**Solution:**
- Every fact tagged: `public | internal | confidential`
- Auto-classified by path (`.claude/` → confidential)
- Encrypted during sync (ChaCha20-Poly1305)
- Push warns before sharing confidential items

**Implementation:** `motherflame/documents.py`, `motherflame/conflicts.py`

```python
# fact: "Funding stage: Series A"
# sensitivity: confidential (from .claude/funding.md)
# → encrypt on push, decrypt on pull (team members only)
```

---

### Gap D: Local-Ingest — File Absorption ✅

**Problem:** Manual harvesting is tedious & incomplete.

**Solution:**
- Scan directories (MD, HTML, PDF, TXT)
- Extract facts via LLM
- Validate before merge
- Track document lineage

**Implementation:** `motherflame/localsync.py`

```bash
motherflame absorb ~/.claude/
motherflame absorb ~/Documents/contracts/
# Extracts & validates facts automatically
```

---

### Gap G: Documents — Dynamic Store ✅

**Problem:** Where do facts come from? Lost without source tracking.

**Solution:**
- Dynamic document store (categories, metadata)
- Fact-to-doc linkage
- Semantic indexing for retrieval
- Search by source

**Implementation:** `motherflame/documents.py`

```python
{
  "documents": [
    {
      "id": "doc:funding_2026",
      "title": "Series A Closing",
      "source": "local:~/.claude/funding.md",
      "category": "Finance",
      "sensitivity": "confidential",
      "facts": ["stage:Series A", "amount:$5M", "date:2026-Q2"]
    }
  ]
}
```

---

### Gap C: Entity Graph — Relationship Mapping ✅

**Problem:** Can't visualize org structure or find "who is CEO?"

**Solution:**
- Entity nodes: org, person, product, team, role
- Relationships: is_ceo_of, works_at, owns, is_same_as
- Auto-build from canonical facts
- Export to GraphML (Gephi-compatible)

**Implementation:** `motherflame/graph.py`

```python
# From canonical items:
# name: MyOrg
# ceo: Alice
# cto: Bob
#
# Generates:
# - Entity(org:myorg)
# - Entity(person:alice)
# - Entity(person:bob)
# - Relationship(alice → myorg, is_ceo_of)
# - Relationship(bob → myorg, is_cto_of)
```

**Visualization:**
```bash
motherflame export --format graphml
# Open in Gephi: org at center, people as nodes, roles as edges
```

---

### Gap E: Semantic Contradictions — Conflict Detection ✅

**Problem:** "Series A" and "Series B" both in brain. Which is right?

**Solution:** Detect & flag contradictions, suggest resolution

| Type | Example | Detection |
|------|---------|-----------|
| **Conflicting values** | stage: A vs B | Same key, different values |
| **Cardinality** | 2 CEOs | Only 1 CEO allowed |
| **Temporal** | Founded 2025, Series A 2022 | Founded must be < Series A |
| **Mutual exclusion** | public_company AND private_company | Can't both be true |

**Implementation:** `motherflame/semantic_validator.py`

```python
validator = SemanticValidator()
contradictions = validator.validate_facts(items)
# Returns: [
#   Contradiction(
#     type=CONFLICTING_VALUES,
#     key='stage',
#     values=['Series A', 'Series B'],
#     resolution_hint='Series A (confidence 0.95 > 0.6)'
#   )
# ]
```

---

### Gap F: Entity Coreference — Mention Linking ✅

**Problem:** "Alice", "alice", "CEO" = same person but looks like 3 entities.

**Solution:** Link mentions to canonical form via:
- Exact match (case-insensitive)
- Fuzzy string matching (Levenshtein)
- Email domain clustering
- Abbreviation detection

**Implementation:** `motherflame/coreference.py`

```python
resolver = CoreferenceResolver()
is_same, confidence = resolver.link_entities("Alice", "alice")
# → (True, 0.95) — linked!

resolver.resolve("CEO")
# → "person:alice" (canonical form)
```

---

## Integration: How C, E, F Work Together

Scenario: MyOrg brain has 12 items from 3 team members (CEO + product lead + engineer).

**Step 1: Build entity graph (C)**
```
5 entities: MyOrg, Alice (CEO), Bob (product), Carol (engineering), investor
4 relationships: Alice is CEO of MyOrg, Bob works at MyOrg, Carol is engineer, etc.
```

**Step 2: Validate semantics (E)**
```
Contradictions detected:
  - stage: "Series A" vs "Series B" (conflicting values)
Resolution hints: Series A wins (0.95 > 0.6)
```

**Step 3: Resolve coreference (F)**
```
4 coreference chains:
  - Alice + alice + alice@myorg.com → canonical: person:alice
  - Bob → canonical: person:bob
  - Carol → canonical: person:carol
  - MyOrg + myorg.io → canonical: org:myorg
```

**Result:** Single canonical brain, 3 machines aligned, 0 data loss.

---

## Team Sync Protocol

### 1. Create Org (Founder)

```bash
$ motherflame create MyOrg --remote git@github.com:myteam/org-brain.git
✓ Created org brain
✓ Flame Key: mf_myorg_a7f3b9c2d1e6f4a8
✓ Invite teammates: motherflame join mf_myorg_... --remote <url>
```

### 2. Join Org (Teammates)

```bash
$ motherflame join mf_myorg_a7f3b9c2d1e6f4a8 --remote <url>
✓ Joined MyOrg org
✓ Downloaded brain from remote (encrypted)
```

### 3. Add Local Data & Push

Each member:
```bash
motherflame absorb ~/my-local-docs/
motherflame push
# Encrypts brain with Flame Key, uploads to remote
```

### 4. Pull & Sync

All members:
```bash
motherflame pull
# Downloads latest brain from all teammates
# Merges via conflict resolution (authority tiers)
# All machines converge to same canonical state
```

### 5. Verify Sync

```bash
$ motherflame status
Org Brain: TrustFinance · 9 items (3 from teammates)
Brain hash: 7f0b9f438bbb6a1b (all machines aligned ✓)
Teammates: Aphola (CEO), UT (Legal)
Contradictions: 2 (stage, team_size) → auto-resolved
```

---

## Zero-Knowledge Encryption

**How it works:**

1. **Flame Key derivation:** `org_id + random_seed → stable team key`
2. **Encryption:** Each fact + metadata → ChaCha20-Poly1305
3. **Remote storage:** Encrypted blob (server sees no plaintext)
4. **Decryption:** Only members with Flame Key can decrypt

```python
# On push: brain → encrypt with Flame Key → upload to remote
# On pull: download from remote → decrypt with Flame Key → merge

# Server (GitHub/GitLab) sees: encrypted binary blob
# No member's data is ever exposed, even to server admins
```

---

## Test Coverage

**All 8 gaps verified:**

```
Gap A (Freshness):         ✅ test_localsync.py (7 tests)
Gap B (Authority):         ✅ test_authority.py (5 tests)
Gap H (Sensitivity):       ✅ test_sensitivity.py (6 tests)
Gap D (Local-Ingest):      ✅ test_localsync.py (7 tests)
Gap G (Documents):         ✅ test_documents.py (8 tests)
Gap C (Graph):             ✅ test_graph_cef.py (4 tests)
Gap E (Semantic):          ✅ test_graph_cef.py (7 tests)
Gap F (Coreference):       ✅ test_graph_cef.py (7 tests)
Integration (C+E+F):       ✅ test_integration_cef.py (2 tests)
Team Sync (3 machines):    ✅ test_sync_blob_key.py (3 tests)

Total: 167/167 tests passing (100%)
CI: Python 3.9, 3.11, 3.12 all green
```

---

## Deployment

### Installation

```bash
git clone https://github.com/opelpleple/motherflame.git
cd motherflame-cli
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Quick Start

```bash
# Create org brain
motherflame create MyOrg --remote <git-url>

# Add local knowledge
motherflame absorb ~/.claude/

# Team sync
motherflame push
motherflame pull

# Analyze
motherflame status      # Summary
motherflame doctor      # Detailed diagnostics
motherflame export --format graphml  # Entity graph
```

### With AI (Optional)

```bash
motherflame setup   # Anthropic / OpenAI / Ollama
motherflame start   # Drop into agent with full context
```

---

## Next Steps (Future)

- **v0.3:** Multi-org federations (share subgraphs across teams)
- **v0.4:** Vector search + RAG (semantic retrieval at scale)
- **v0.5:** Temporal facts (facts that expire or change seasonally)

---

## References

- [CONCEPTS.md](../CONCEPTS.md) — Glossary (Flame Key, claims, contested, etc.)
- [API.md](./API.md) — Function reference
- [DEPLOY.md](./DEPLOY.md) — Production checklist
