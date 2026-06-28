"""
Tests for entity graph (C), semantic contradictions (E), coreference (F).
"""

import pytest
import sys
sys.path.insert(0, "/Users/peterbu/motherflame-cli")

from motherflame.graph import Entity, Relationship, EntityGraph, build_org_hierarchy
from motherflame.semantic_validator import SemanticValidator, ContradictionType, Contradiction
from motherflame.coreference import CoreferenceResolver, CoreferenceChain


# ════════════════════════════════════════════════════════════════════════════════
# TESTS: Entity Graph (Gap C)
# ════════════════════════════════════════════════════════════════════════════════

def test_entity_graph_add_entities():
    """Test adding entities to graph."""
    graph = EntityGraph()
    
    org = Entity(id="org:trustfinance", type="org", name="TrustFinance")
    person = Entity(id="person:opel", type="person", name="Opel", aliases=["opelpleple"])
    
    graph.add_entity(org)
    graph.add_entity(person)
    
    assert len(graph.entities) == 2
    assert graph.find_entity("TrustFinance") == org
    assert graph.find_entity("Opel") == person
    assert graph.find_entity("opelpleple") == person  # Via alias


def test_entity_graph_relationships():
    """Test relationships between entities."""
    graph = EntityGraph()
    
    org = Entity(id="org:trustfinance", type="org", name="TrustFinance")
    person = Entity(id="person:opel", type="person", name="Opel")
    
    graph.add_entity(org)
    graph.add_entity(person)
    
    rel = Relationship(
        source_id="person:opel",
        target_id="org:trustfinance",
        rel_type="is_ceo_of",
        confidence=0.95,
        evidence=["chat:Opel is CEO"]
    )
    graph.add_relationship(rel)
    
    assert len(graph.relationships) == 1
    leadership = graph.get_leadership("org:trustfinance")
    assert "CEO" in leadership


def test_entity_graph_from_brain():
    """Test building graph from canonical brain."""
    brain = {
        "items": [
            {"key": "name", "value": "TrustFinance", "confidence": 1.0},
            {"key": "ceo", "value": "Opel", "confidence": 0.95},
            {"key": "cto", "value": "Bombay", "confidence": 0.9},
            {"key": "jurisdiction", "value": "UK FCA", "confidence": 1.0},
        ]
    }
    
    graph = EntityGraph()
    graph.build_from_brain(brain)
    
    assert len(graph.entities) > 0
    assert len(graph.relationships) > 0
    
    # Verify org was created
    orgs = [e for e in graph.entities.values() if e.type == "org"]
    assert len(orgs) > 0
    
    # Verify people were created
    people = [e for e in graph.entities.values() if e.type == "person"]
    assert len(people) > 0


def test_org_hierarchy():
    """Test org hierarchy extraction."""
    brain = {
        "items": [
            {"key": "name", "value": "TrustFinance", "confidence": 1.0},
            {"key": "ceo", "value": "Opel", "confidence": 0.95},
            {"key": "cto", "value": "Bombay", "confidence": 0.9},
        ]
    }
    
    graph = EntityGraph()
    graph.build_from_brain(brain)
    hierarchy = build_org_hierarchy(graph)
    
    assert "TrustFinance" in hierarchy
    assert "CEO" in hierarchy["TrustFinance"]["leadership"]


# ════════════════════════════════════════════════════════════════════════════════
# TESTS: Semantic Contradictions (Gap E)
# ════════════════════════════════════════════════════════════════════════════════

def test_contradiction_conflicting_values():
    """Test detection of conflicting values for same fact."""
    items = [
        {"key": "stage", "value": "Series A", "source": "chat", "confidence": 0.9},
        {"key": "stage", "value": "Series B", "source": "confidential", "confidence": 0.95},
    ]
    
    validator = SemanticValidator()
    contradictions = validator.validate_facts(items)
    
    assert len(contradictions) > 0
    assert any(c.contradiction_type == ContradictionType.CONFLICTING_VALUES for c in contradictions)


def test_contradiction_cardinality_violation():
    """Test one-to-one constraint violation."""
    items = [
        {"key": "ceo", "value": "Opel", "source": "chat", "confidence": 0.9},
        {"key": "ceo", "value": "Other Person", "source": "chat", "confidence": 0.8},
    ]
    
    validator = SemanticValidator()
    contradictions = validator.validate_facts(items)
    
    assert len(contradictions) > 0
    assert any(c.contradiction_type == ContradictionType.CARDINALITY_VIOLATION for c in contradictions)


def test_contradiction_temporal_violation():
    """Test timeline consistency."""
    items = [
        {"key": "founded_year", "value": "2022", "source": "chat", "confidence": 0.9},
        {"key": "series_a_year", "value": "2020", "source": "chat", "confidence": 0.9},  # Before founding!
    ]
    
    validator = SemanticValidator()
    contradictions = validator.validate_facts(items)
    
    assert len(contradictions) > 0
    assert any(c.contradiction_type == ContradictionType.TEMPORAL_VIOLATION for c in contradictions)


def test_contradiction_mutual_exclusion():
    """Test mutually exclusive facts."""
    items = [
        {"key": "public_company", "value": "true", "source": "chat", "confidence": 1.0},
        {"key": "private_company", "value": "true", "source": "chat", "confidence": 1.0},
    ]
    
    validator = SemanticValidator()
    contradictions = validator.validate_facts(items)
    
    assert len(contradictions) > 0
    assert any(c.contradiction_type == ContradictionType.MUTUAL_EXCLUSION for c in contradictions)


def test_contradiction_resolution_hint():
    """Test that resolution hints are provided."""
    items = [
        {"key": "stage", "value": "Series A", "source": "chat", "confidence": 0.7},
        {"key": "stage", "value": "Series B", "source": "confidential", "confidence": 0.95},
    ]
    
    validator = SemanticValidator()
    contradictions = validator.validate_facts(items)
    
    assert len(contradictions) > 0
    contradiction = contradictions[0]
    assert contradiction.resolution_hint != ""
    assert "Series B" in contradiction.resolution_hint  # Higher confidence


def test_semantic_validator_summary():
    """Test contradiction summary statistics."""
    items = [
        {"key": "stage", "value": "Series A", "source": "chat", "confidence": 0.9},
        {"key": "stage", "value": "Series B", "source": "chat", "confidence": 0.8},
        {"key": "ceo", "value": "Opel", "source": "chat", "confidence": 0.9},
        {"key": "ceo", "value": "Other", "source": "chat", "confidence": 0.8},
    ]
    
    validator = SemanticValidator()
    contradictions = validator.validate_facts(items)
    summary = validator.summary()
    
    # Both stage and ceo are cardinality violations + conflicting values
    assert summary["total"] >= 2  # At least 2 contradictions
    assert summary["errors"] >= 1  # At least 1 cardinality error


# ════════════════════════════════════════════════════════════════════════════════
# TESTS: Entity Coreference (Gap F)
# ════════════════════════════════════════════════════════════════════════════════

def test_coreference_exact_match():
    """Test exact name matching."""
    resolver = CoreferenceResolver()
    
    is_same, confidence = resolver.link_entities("Opel", "opel")
    assert is_same
    assert confidence == 1.0


def test_coreference_fuzzy_match():
    """Test fuzzy string matching."""
    resolver = CoreferenceResolver(similarity_threshold=0.85)
    
    # Similar names should match
    is_same, confidence = resolver.link_entities("Peter Bu", "peterbu")
    assert is_same or confidence > 0.8


def test_coreference_email_domain():
    """Test email domain matching."""
    resolver = CoreferenceResolver()
    
    is_same, confidence = resolver.link_entities(
        "opel@trustfinance.com",
        "opel.pleple@trustfinance.com"
    )
    assert confidence >= 0.7  # Same domain


def test_coreference_abbreviation():
    """Test abbreviation linking."""
    resolver = CoreferenceResolver()
    
    is_same, confidence = resolver.link_entities("opel", "opelpleple")
    assert is_same
    assert confidence >= 0.85


def test_coreference_chain_creation():
    """Test creating and registering coreference chains."""
    resolver = CoreferenceResolver()
    
    chain = CoreferenceChain(
        canonical_id="person:opel",
        canonical_name="Opel",
        mentions=["Opel", "opel", "opelpleple", "CEO"],
        confidence=0.95,
        evidence=["primary", "alias", "email:opel@..."]
    )
    resolver.add_chain(chain)
    
    assert resolver.resolve("opel") == "person:opel"
    assert resolver.resolve("opelpleple") == "person:opel"
    assert resolver.resolve("CEO") == "person:opel"


def test_coreference_build_from_facts():
    """Test auto-detecting coreference from facts."""
    items = [
        {"key": "ceo", "value": "Opel", "confidence": 0.95},
        {"key": "founder", "value": "opelpleple", "confidence": 0.95},
        {"key": "cto", "value": "Bombay", "confidence": 0.9},
    ]
    
    resolver = CoreferenceResolver()
    resolver.build_from_facts(items)
    
    chains = resolver.export_chains()
    assert len(chains) > 0
    
    # Should have detected Opel/opelpleple as same
    opel_chains = [c for c in chains if "opel" in c["canonical_name"].lower()]
    assert len(opel_chains) > 0


def test_coreference_chain_merge():
    """Test merging two coreference chains."""
    resolver = CoreferenceResolver()
    
    chain1 = CoreferenceChain(
        canonical_id="person:opel_v1",
        canonical_name="Opel",
        mentions=["Opel"],
        confidence=0.8,
        evidence=["source1"]
    )
    chain2 = CoreferenceChain(
        canonical_id="person:opel_v2",
        canonical_name="opelpleple",
        mentions=["opelpleple"],
        confidence=0.9,
        evidence=["source2"]
    )
    
    resolver.add_chain(chain1)
    resolver.add_chain(chain2)
    assert len(resolver.chains) == 2
    
    resolver.merge_chains("person:opel_v1", "person:opel_v2", evidence="matched:email_domain")
    assert len(resolver.chains) == 1
    
    merged = list(resolver.chains.values())[0]
    assert "Opel" in merged.mentions
    assert "opelpleple" in merged.mentions


def test_coreference_stats():
    """Test coreference statistics."""
    resolver = CoreferenceResolver()
    
    chain = CoreferenceChain(
        canonical_id="person:opel",
        canonical_name="Opel",
        mentions=["Opel", "opel", "opelpleple", "CEO"],
        confidence=0.95
    )
    resolver.add_chain(chain)
    
    stats = resolver.stats()
    assert stats["chains"] == 1
    assert stats["total_mentions"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
