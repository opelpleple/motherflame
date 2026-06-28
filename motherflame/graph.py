"""
Entity graph layer — relationship mapping & organizational structure.

Build a directed graph of entities (people, orgs, roles, products) and their relationships.
Enables: org hierarchy visualization, people-org links, dependency tracking.
"""

import json
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict


@dataclass
class Entity:
    """Represents a node in the knowledge graph."""
    id: str  # Unique identifier (e.g., "person:opel", "org:trustfinance")
    type: str  # person, org, product, role, team
    name: str  # Display name
    aliases: List[str] = field(default_factory=list)  # Alternative names
    attributes: Dict[str, str] = field(default_factory=dict)  # Fact metadata
    confidence: float = 0.8  # Derived from facts

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Relationship:
    """Edge in the knowledge graph."""
    source_id: str  # From entity
    target_id: str  # To entity
    rel_type: str  # "is_ceo_of", "works_at", "owns", "is_same_as"
    confidence: float = 0.8
    source: str = "inferred"  # Where the relationship came from
    evidence: List[str] = field(default_factory=list)  # Supporting facts

    def to_dict(self) -> dict:
        return asdict(self)


class EntityGraph:
    """Maintains entity graph from canonical facts."""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self.entity_index: Dict[str, Set[str]] = defaultdict(set)  # name/alias → [entity_ids]

    def add_entity(self, entity: Entity) -> None:
        """Add or update entity node."""
        self.entities[entity.id] = entity
        self._index_entity(entity)

    def _index_entity(self, entity: Entity) -> None:
        """Index entity by name & aliases for quick lookup."""
        self.entity_index[entity.name.lower()].add(entity.id)
        for alias in entity.aliases:
            self.entity_index[alias.lower()].add(entity.id)

    def add_relationship(self, rel: Relationship) -> None:
        """Add edge between entities."""
        if rel.source_id not in self.entities or rel.target_id not in self.entities:
            return  # Both entities must exist
        self.relationships.append(rel)

    def find_entity(self, name: str) -> Optional[Entity]:
        """Find entity by name or alias (fuzzy)."""
        name_lower = name.lower()
        candidates = self.entity_index.get(name_lower, set())
        if candidates:
            return self.entities.get(list(candidates)[0])
        
        # Fuzzy fallback: prefix match
        for entity_id, entity in self.entities.items():
            if entity.type in ["person", "org"]:
                if entity.name.lower().startswith(name_lower[:3]):
                    return entity
        return None

    def get_org_members(self, org_id: str) -> List[Entity]:
        """List all people working at org."""
        members = []
        for rel in self.relationships:
            if rel.target_id == org_id and rel.rel_type in ["works_at", "is_member_of"]:
                members.append(self.entities[rel.source_id])
        return members

    def get_person_orgs(self, person_id: str) -> List[Entity]:
        """List all orgs person is affiliated with."""
        orgs = []
        for rel in self.relationships:
            if rel.source_id == person_id and rel.rel_type in ["works_at", "is_member_of"]:
                orgs.append(self.entities[rel.target_id])
        return orgs

    def get_leadership(self, org_id: str) -> Dict[str, Entity]:
        """Get leadership team (CEO, CTO, CFO, etc.) for org."""
        leadership = {}
        for rel in self.relationships:
            if rel.target_id == org_id and rel.rel_type.startswith("is_"):
                role = rel.rel_type.replace("is_", "").replace("_of", "").upper()
                leadership[role] = self.entities[rel.source_id]
        return leadership

    def build_from_brain(self, brain: dict) -> None:
        """Populate graph from canonical facts."""
        items = brain.get("items", [])
        
        # Phase 1: Extract entities from facts
        org_entities = {}
        person_entities = {}

        for item in items:
            key = item.get("key", "")
            value = item.get("value", "")

            # Detect org/person facts
            if key == "name":
                org_id = f"org:{value.lower().replace(' ', '_')}"
                org_entities[org_id] = Entity(
                    id=org_id,
                    type="org",
                    name=value,
                    confidence=item.get("confidence", 0.8)
                )

            elif key in ["ceo", "cto", "cfo", "founder"]:
                person_id = f"person:{value.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                if person_id not in person_entities:
                    person_entities[person_id] = Entity(
                        id=person_id,
                        type="person",
                        name=value,
                        confidence=item.get("confidence", 0.8)
                    )
                # Store role attribute
                person_entities[person_id].attributes[key] = "true"

            elif key == "jurisdiction":
                # Mark org jurisdiction
                if org_entities:
                    first_org = list(org_entities.values())[0]
                    first_org.attributes["jurisdiction"] = value

        # Phase 2: Add all entities
        for entity in org_entities.values():
            self.add_entity(entity)
        for entity in person_entities.values():
            self.add_entity(entity)

        # Phase 3: Create relationships
        first_org_id = list(org_entities.keys())[0] if org_entities else None

        for rel_type in ["ceo", "cto", "cfo", "founder"]:
            for item in items:
                if item.get("key") == rel_type and first_org_id:
                    person_name = item.get("value", "")
                    person_id = f"person:{person_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                    
                    rel = Relationship(
                        source_id=person_id,
                        target_id=first_org_id,
                        rel_type=f"is_{rel_type}_of",
                        confidence=item.get("confidence", 0.8),
                        source="canonical",
                        evidence=[f"{rel_type}:{person_name}"]
                    )
                    self.add_relationship(rel)

    def to_dict(self) -> dict:
        """Export graph as JSON-serializable dict."""
        return {
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relationships": [r.to_dict() for r in self.relationships]
        }

    def export_graphml(self) -> str:
        """Export as GraphML (compatible with Gephi, yEd)."""
        graphml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        graphml += '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        graphml += '  <graph edgedefault="directed">\n'

        # Nodes
        for entity_id, entity in self.entities.items():
            graphml += f'    <node id="{entity_id}" label="{entity.name}"><data key="type">{entity.type}</data></node>\n'

        # Edges
        for rel in self.relationships:
            graphml += f'    <edge source="{rel.source_id}" target="{rel.target_id}" label="{rel.rel_type}"/>\n'

        graphml += '  </graph>\n</graphml>\n'
        return graphml

    def export_json(self) -> str:
        """Export as JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def stats(self) -> dict:
        """Graph statistics."""
        entity_types = defaultdict(int)
        rel_types = defaultdict(int)

        for entity in self.entities.values():
            entity_types[entity.type] += 1

        for rel in self.relationships:
            rel_types[rel.rel_type] += 1

        return {
            "entities_count": len(self.entities),
            "entity_types": dict(entity_types),
            "relationships_count": len(self.relationships),
            "relationship_types": dict(rel_types)
        }


def build_org_hierarchy(graph: EntityGraph) -> dict:
    """Extract org structure tree."""
    hierarchy = {}
    for org_id, org in graph.entities.items():
        if org.type != "org":
            continue
        hierarchy[org.name] = {
            "id": org_id,
            "leadership": {
                role: person.name
                for role, person in graph.get_leadership(org_id).items()
            },
            "members": [
                person.name
                for person in graph.get_org_members(org_id)
            ]
        }
    return hierarchy
