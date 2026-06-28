# Motherflame v0.2 API Reference

## Core Functions

### `enhance_brain_with_graph(brain: dict) -> dict`

Builds entity graph from canonical facts in brain.

**Parameters:**
- `brain` (dict): Brain state with `items` list

**Returns:** Same brain with `brain["graph"]` containing:
- `entities`: List of entity nodes
- `relationships`: List of relationship edges
- `hierarchy`: Org structure (CEO → reports)

**Example:**
```python
from motherflame.core import enhance_brain_with_graph

brain = {
    "items": [
        {"key": "name", "value": "MyOrg"},
        {"key": "ceo", "value": "Alice"},
    ]
}

brain = enhance_brain_with_graph(brain)
print(brain["graph"]["entities"])
# [Entity(id='org:myorg', type='org', name='MyOrg'),
#  Entity(id='person:alice', type='person', name='Alice')]
```

---

### `validate_semantic_consistency(brain: dict) -> dict`

Detects contradictions in brain facts.

**Parameters:**
- `brain` (dict): Brain state with `items` list

**Returns:** Same brain with:
- `brain["contradictions"]`: List of Contradiction objects
- `brain["contradiction_summary"]`: Stats (total, warnings, errors)

**Example:**
```python
from motherflame.core import validate_semantic_consistency

brain = {
    "items": [
        {"key": "ceo", "value": "Alice", "confidence": 0.95},
        {"key": "ceo", "value": "Bob", "confidence": 0.9},
    ]
}

brain = validate_semantic_consistency(brain)
print(brain["contradiction_summary"])
# {'total': 1, 'warnings': 1, 'errors': 0}

for c in brain["contradictions"]:
    print(f"{c.contradiction_type}: {c.resolution_hint}")
    # CARDINALITY_VIOLATION: Only 1 CEO allowed; pick Alice (0.95 > 0.9)
```

---

### `resolve_coreference(brain: dict) -> dict`

Links duplicate entity mentions to canonical forms.

**Parameters:**
- `brain` (dict): Brain state with `items` list

**Returns:** Same brain with:
- `brain["coreference"]["chains"]`: List of coreference chains
- `brain["coreference"]["stats"]`: Count of chains, mentions, etc.

**Example:**
```python
from motherflame.core import resolve_coreference

brain = {
    "items": [
        {"key": "ceo", "value": "Alice"},
        {"key": "founder", "value": "alice"},
        {"key": "contact", "value": "alice@myorg.com"},
    ]
}

brain = resolve_coreference(brain)
print(brain["coreference"]["stats"])
# {'chains': 1, 'total_mentions': 3, 'avg_confidence': 0.95}

# All 3 mentions resolved to canonical: person:alice
```

---

## EntityGraph Class

### `class EntityGraph`

Represents organization structure as directed graph.

```python
from motherflame.graph import EntityGraph, Entity, Relationship

graph = EntityGraph()
```

#### Methods

**`add_entity(entity: Entity) -> None`**

Add a node to the graph.

```python
org = Entity(id="org:trustfinance", type="org", name="TrustFinance")
graph.add_entity(org)
```

**`add_relationship(rel: Relationship) -> None`**

Add an edge (relationship) to the graph.

```python
rel = Relationship(
    source_id="person:opel",
    target_id="org:trustfinance",
    rel_type="is_ceo_of",
    confidence=0.95
)
graph.add_relationship(rel)
```

**`build_from_brain(brain: dict) -> None`**

Auto-extract entities & relationships from canonical brain items.

```python
brain = {"items": [...]}
graph.build_from_brain(brain)
# Now graph.entities and graph.relationships are populated
```

**`export_graphml() -> str`**

Export as GraphML (Gephi-compatible).

```python
graphml = graph.export_graphml()
with open("org-structure.graphml", "w") as f:
    f.write(graphml)
```

**`get_hierarchy() -> dict`**

Extract org hierarchy (CEO, reports, etc.).

```python
hierarchy = graph.get_hierarchy()
# {"ceo": "Opel", "cto": "Bombay", "reports": [...]}
```

**`stats() -> dict`**

Get summary statistics.

```python
stats = graph.stats()
# {'entities_count': 4, 'relationships_count': 3, ...}
```

---

## SemanticValidator Class

### `class SemanticValidator`

Detects logical contradictions in facts.

```python
from motherflame.semantic_validator import SemanticValidator, ContradictionType

validator = SemanticValidator()
```

#### Methods

**`validate_facts(items: list) -> list[Contradiction]`**

Check facts for contradictions.

```python
items = [
    {"key": "stage", "value": "Series A", "confidence": 0.95},
    {"key": "stage", "value": "Series B", "confidence": 0.6},
]

contradictions = validator.validate_facts(items)
for c in contradictions:
    print(f"{c.contradiction_type}: {c.resolution_hint}")
```

**`summary() -> dict`**

Get contradiction stats.

```python
summary = validator.summary()
# {
#   'total': 2,
#   'warnings': 1,
#   'errors': 1,
#   'by_type': {'CONFLICTING_VALUES': 1, 'CARDINALITY_VIOLATION': 1}
# }
```

#### Contradiction Types

```python
class ContradictionType(Enum):
    CONFLICTING_VALUES = "conflicting_values"
    CARDINALITY_VIOLATION = "cardinality_violation"
    TEMPORAL_VIOLATION = "temporal_violation"
    MUTUAL_EXCLUSION = "mutual_exclusion"
```

---

## CoreferenceResolver Class

### `class CoreferenceResolver`

Links duplicate entity mentions.

```python
from motherflame.coreference import CoreferenceResolver, CoreferenceChain

resolver = CoreferenceResolver()
```

#### Methods

**`link_entities(mention1: str, mention2: str) -> tuple[bool, float]`**

Check if two mentions refer to the same entity.

```python
is_same, confidence = resolver.link_entities("Opel", "opelpleple")
# (True, 0.95) — very likely same person

is_same, confidence = resolver.link_entities("Opel", "Bob")
# (False, 0.1) — unlikely same person
```

**`add_chain(chain: CoreferenceChain) -> None`**

Register a coreference chain (multiple mentions of same entity).

```python
chain = CoreferenceChain(
    canonical_id="person:opel",
    canonical_name="Opel",
    mentions=["Opel", "opelpleple", "opel@trustfinance.com"],
    confidence=0.95,
    evidence=["exact", "email_domain", "abbrev"]
)
resolver.add_chain(chain)
```

**`resolve(mention: str) -> str`**

Get canonical ID for a mention.

```python
canonical_id = resolver.resolve("opelpleple")
# "person:opel"
```

**`build_from_facts(items: list) -> None`**

Auto-build chains from brain items.

```python
items = [
    {"key": "ceo", "value": "Opel"},
    {"key": "founder", "value": "opelpleple"},
]
resolver.build_from_facts(items)
# Now 1 chain created linking both mentions
```

**`export_chains() -> list[dict]`**

Serialize all chains for storage.

```python
chains = resolver.export_chains()
# [{"canonical_id": "person:opel", "mentions": [...], ...}]
```

**`stats() -> dict`**

Get summary.

```python
stats = resolver.stats()
# {'chains': 3, 'total_mentions': 8, 'avg_confidence': 0.93}
```

---

## CLI Commands

### `motherflame create <org_name> --remote <url>`

Create org brain.

```bash
motherflame create TrustFinance --remote git@github.com:opelpleple/team-brain.git
```

### `motherflame join <flame_key> --remote <url>`

Join org as teammate.

```bash
motherflame join mf_trustfinance_be583d48d4052b2e --remote <url>
```

### `motherflame absorb <path>`

Ingest local files into brain.

```bash
motherflame absorb ~/.claude/
```

### `motherflame push`

Upload brain to remote (encrypted).

```bash
motherflame push
```

### `motherflame pull`

Download latest brain from remote (decrypt & merge).

```bash
motherflame pull
```

### `motherflame status`

Show brain summary.

```bash
motherflame status
# Org Brain: TrustFinance · 9 items (3 from teammates)
# Brain hash: 7f0b9f438bbb6a1b
# Contradictions: 2 (stage, team_size) → auto-resolved
```

### `motherflame doctor`

Detailed diagnostics.

```bash
motherflame doctor
```

### `motherflame export --format graphml`

Export entity graph.

```bash
motherflame export --format graphml > org-structure.graphml
```

### `motherflame`

Start interactive agent.

```bash
motherflame
you › what are our legal constraints?
ai  › UK FCA regulated...
```

---

## Data Structures

### Brain State

```python
brain = {
    "org_name": "TrustFinance",
    "flame_key": "mf_trustfinance_be583d48d4052b2e",
    "items": [
        {
            "key": "stage",
            "value": "Series A",
            "source": "chat",
            "confidence": 0.95,
            "sensitivity": "confidential",
            "timestamp": "2026-06-28T14:30:00Z"
        },
        ...
    ],
    "claims": {...},
    "documents": {...},
    "graph": {...},
    "contradictions": [...],
    "coreference": {...}
}
```

### Contradiction Object

```python
Contradiction(
    contradiction_type=ContradictionType.CONFLICTING_VALUES,
    key="stage",
    values=["Series A", "Series B"],
    sources=["chat", "web"],
    confidences=[0.95, 0.6],
    resolution_hint="Pick Series A (confidence 0.95 > 0.6)",
    timestamp="2026-06-28T14:30:00Z"
)
```

### CoreferenceChain Object

```python
CoreferenceChain(
    canonical_id="person:opel",
    canonical_name="Opel",
    mentions=["Opel", "opelpleple", "opel@trustfinance.com"],
    confidence=0.95,
    evidence=["exact_match", "abbreviation", "email_domain"],
    timestamp="2026-06-28T14:30:00Z"
)
```

---

## Error Handling

### Common Exceptions

```python
from motherflame.errors import (
    FlameKeyError,           # Invalid/missing Flame Key
    CorruptedBrainError,     # Brain data corrupted
    SyncConflictError,       # Unresolvable sync conflict
    EncryptionError,         # Encryption/decryption failed
)
```

---

## Testing

```bash
# All tests
python3.11 -m pytest tests/ -v

# By gap
python3.11 -m pytest tests/test_graph_cef.py -v  # C, E, F
python3.11 -m pytest tests/test_authority.py -v  # B
python3.11 -m pytest tests/test_sensitivity.py -v # H

# Integration
python3.11 -m pytest tests/test_integration_cef.py -v
```

---

## Performance

- **Graph build:** O(n) where n = items count (typical <100ms for 1000 items)
- **Contradiction detection:** O(n²) worst-case, O(n) typical
- **Coreference:** O(m log m) where m = mentions count
- **Encryption:** O(k) where k = serialized brain size (~10-50KB)
- **Sync:** 500-1000 items synced in <1 second

---

## Support

- Issues: https://github.com/opelpleple/motherflame/issues
- Discussions: https://github.com/opelpleple/motherflame/discussions
- Docs: See [ARCHITECTURE.md](./ARCHITECTURE.md)
