"""
Integration test: C+E+F working together on real brain data.

Scenario: 
- Load a TrustFinance brain with multiple conflicting facts
- Apply graph building, semantic validation, & coreference
- Verify all systems detect/resolve issues correctly
"""

import pytest
import sys
import json
sys.path.insert(0, "/Users/peterbu/motherflame-cli")

from motherflame import core


def test_cef_integration_trustfinance():
    """Test C, E, F working together on TrustFinance data."""
    
    # Create a realistic brain with conflicts & duplicates
    brain = {
        "org_name": "TrustFinance",
        "items": [
            # Company info
            {"key": "name", "value": "TrustFinance", "source": "chat", "confidence": 1.0, "sensitivity": "public"},
            
            # Leadership (potential coreference: Opel mentioned 3 ways)
            {"key": "ceo", "value": "Opel", "source": "chat", "confidence": 0.95, "sensitivity": "public"},
            {"key": "founder", "value": "opelpleple", "source": "confidential", "confidence": 0.98, "sensitivity": "confidential"},
            {"key": "cto", "value": "Bombay", "source": "chat", "confidence": 0.9, "sensitivity": "public"},
            
            # Funding stage (conflicts!)
            {"key": "stage", "value": "Series A", "source": "chat", "confidence": 0.9, "sensitivity": "confidential"},
            {"key": "stage", "value": "Series B", "source": "chat", "confidence": 0.6, "sensitivity": "internal"},  # Lower confidence = rumor
            
            # Headcount (conflict)
            {"key": "team_size", "value": "34", "source": "chat", "confidence": 0.85, "sensitivity": "internal"},
            {"key": "team_size", "value": "35", "source": "chat", "confidence": 0.7, "sensitivity": "internal"},
            
            # Legal/compliance
            {"key": "jurisdiction", "value": "UK FCA regulated", "source": "confidential", "confidence": 1.0, "sensitivity": "confidential"},
            {"key": "compliance", "value": "ISO 27001", "source": "document", "confidence": 0.95, "sensitivity": "public"},
            
            # Timeline (temporal consistency check)
            {"key": "founded_year", "value": "2021", "source": "chat", "confidence": 0.9, "sensitivity": "public"},
            {"key": "series_a_year", "value": "2023", "source": "chat", "confidence": 0.9, "sensitivity": "internal"},
        ],
        "claims": {},
        "last_updated": "2026-06-28"
    }
    
    # Step 1: Apply entity graph (Gap C)
    brain = core.enhance_brain_with_graph(brain)
    assert "graph" in brain
    assert brain["graph"]["entities"] > 0
    assert brain["graph"]["relationships"] > 0
    print(f"✓ Graph: {brain['graph']['entities']} entities, {brain['graph']['relationships']} relationships")
    
    # Step 2: Apply semantic validation (Gap E)
    brain = core.validate_semantic_consistency(brain)
    assert "contradictions" in brain
    assert "contradiction_summary" in brain
    
    summary = brain["contradiction_summary"]
    print(f"✓ Semantic validation: {summary['total']} contradictions detected")
    print(f"  - Errors: {summary['errors']}, Warnings: {summary['warnings']}")
    
    # Verify stage conflict was detected
    stage_contradictions = [c for c in brain["contradictions"] if c["key"] == "stage"]
    assert len(stage_contradictions) > 0, "Should detect stage conflict"
    print(f"  - Stage conflict detected: {len(stage_contradictions[0]['values'])} different values")
    
    # Step 3: Apply coreference resolution (Gap F)
    brain = core.resolve_coreference(brain)
    assert "coreference" in brain
    assert "chains" in brain["coreference"]
    assert "stats" in brain["coreference"]
    
    chains = brain["coreference"]["chains"]
    stats = brain["coreference"]["stats"]
    print(f"✓ Coreference: {stats['chains']} chains, {stats['total_mentions']} total mentions")
    
    # Verify Opel/opelpleple were linked
    opel_chains = [c for c in chains if "opel" in c["canonical_name"].lower() or any("opel" in m.lower() for m in c["mentions"])]
    assert len(opel_chains) > 0, "Should link Opel/opelpleple"
    
    merged_chain = opel_chains[0]
    assert "Opel" in merged_chain["mentions"], "Should have Opel"
    # Note: opelpleple might be canonical or mention depending on match
    print(f"  - CEO coreference chain: {merged_chain['mentions']}")
    
    # Step 4: Verify temporal consistency
    temporal_violations = [c for c in brain["contradictions"] if c["contradiction_type"] == "temporal_violation"]
    assert len(temporal_violations) == 0, "Temporal order should be valid (2021 < 2023)"
    print(f"✓ Temporal consistency: Valid (2021 < 2023)")
    
    # Step 5: Summary stats
    print(f"\n✓ Integration test complete:")
    print(f"  Org: {brain['org_name']}")
    print(f"  Items: {len(brain['items'])}")
    print(f"  Graph entities: {brain['graph']['entities']}")
    print(f"  Contradictions flagged: {summary['total']}")
    print(f"  Coreference chains: {stats['chains']}")


def test_cef_clean_brain():
    """Test C, E, F on a clean brain (no conflicts)."""
    
    brain = {
        "org_name": "CleanCorp",
        "items": [
            {"key": "name", "value": "CleanCorp", "source": "chat", "confidence": 1.0, "sensitivity": "public"},
            {"key": "ceo", "value": "Alice", "source": "chat", "confidence": 0.95, "sensitivity": "public"},
            {"key": "stage", "value": "Seed", "source": "chat", "confidence": 0.9, "sensitivity": "internal"},
        ],
        "claims": {},
        "last_updated": "2026-06-28"
    }
    
    brain = core.enhance_brain_with_graph(brain)
    brain = core.validate_semantic_consistency(brain)
    brain = core.resolve_coreference(brain)
    
    # Should have zero contradictions
    assert brain["contradiction_summary"]["total"] == 0
    print(f"✓ Clean brain has {brain['contradiction_summary']['total']} contradictions")
    
    # Should still have graph & coreference
    assert brain["graph"]["entities"] > 0
    assert brain["coreference"]["stats"]["chains"] > 0
    print(f"✓ Clean brain still has entities & coreference chains")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
