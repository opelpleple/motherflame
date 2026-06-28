"""
Semantic contradiction detection — identify logical inconsistencies in facts.

Examples:
- "Company X founded 2020" vs "Company X founded 2021"
- "Person A is CEO of X" vs "Person A is CEO of Y" (can't be both)
- "Product X EOL in 2023" vs "Product X launched in 2024" (temporal violation)
"""

import json
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class ContradictionType(Enum):
    """Types of semantic contradictions."""
    CONFLICTING_VALUES = "conflicting_values"  # Same fact, different values
    TEMPORAL_VIOLATION = "temporal_violation"  # Timeline inconsistency
    CARDINALITY_VIOLATION = "cardinality_violation"  # One-to-many conflict
    LOGICAL_INCONSISTENCY = "logical_inconsistency"  # Inconsistent state
    MUTUAL_EXCLUSION = "mutual_exclusion"  # Can't both be true


@dataclass
class Contradiction:
    """Detected semantic conflict."""
    contradiction_type: ContradictionType
    key: str  # Fact key (e.g., "stage", "founded_year")
    values: List[Tuple[str, str, float]]  # [(value, source, confidence), ...]
    severity: str = "warning"  # info, warning, error
    explanation: str = ""
    resolution_hint: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["contradiction_type"] = self.contradiction_type.value
        data["values"] = [(v, s, c) for v, s, c in self.values]
        return data


class SemanticValidator:
    """Validate facts for semantic consistency."""

    # Cardinality rules: key → max concurrent values
    CARDINALITY_CONSTRAINTS = {
        "ceo": 1,
        "cto": 1,
        "cfo": 1,
        "founder": 1,
        "stage": 1,  # Can only be in one funding stage at once
    }

    # Temporal constraints: [key1, key2] → key1_year must be < key2_year
    TEMPORAL_CONSTRAINTS = [
        ("founded_year", "ipo_year"),
        ("founded_year", "acq_year"),
        ("founded_year", "series_a_year"),  # Founded before Series A
        ("series_a_year", "series_b_year"),
        ("series_b_year", "series_c_year"),
    ]

    # Mutual exclusion: only one of these can be true
    MUTUAL_EXCLUSIONS = [
        {"public_company", "private_company"},
        {"acquired", "independent"},
        {"active", "defunct"},
    ]

    def __init__(self):
        self.contradictions: List[Contradiction] = []

    def validate_facts(self, items: List[dict]) -> List[Contradiction]:
        """Scan canonical items for contradictions."""
        self.contradictions = []

        # Check cardinality violations
        self._check_cardinality(items)

        # Check temporal violations
        self._check_temporal(items)

        # Check conflicting values
        self._check_conflicting_values(items)

        # Check mutual exclusions
        self._check_mutual_exclusions(items)

        return self.contradictions

    def _check_cardinality(self, items: List[dict]) -> None:
        """Verify one-to-many constraints."""
        value_counts = {}

        for item in items:
            key = item.get("key", "")
            if key not in self.CARDINALITY_CONSTRAINTS:
                continue

            max_allowed = self.CARDINALITY_CONSTRAINTS[key]
            if key not in value_counts:
                value_counts[key] = []

            value_counts[key].append((
                item.get("value", ""),
                item.get("source", "unknown"),
                item.get("confidence", 0.5)
            ))

        for key, values in value_counts.items():
            if len(set(v[0] for v in values)) > 1:  # Multiple distinct values
                contradiction = Contradiction(
                    contradiction_type=ContradictionType.CARDINALITY_VIOLATION,
                    key=key,
                    values=values,
                    severity="error",
                    explanation=f"Cannot have multiple {key} values simultaneously",
                    resolution_hint=f"Choose highest confidence {key}: {max(values, key=lambda x: x[2])[0]}"
                )
                self.contradictions.append(contradiction)

    def _check_temporal(self, items: List[dict]) -> None:
        """Verify timeline consistency."""
        fact_dict = {item.get("key"): item for item in items}

        for earlier_key, later_key in self.TEMPORAL_CONSTRAINTS:
            if earlier_key not in fact_dict or later_key not in fact_dict:
                continue

            earlier_val = fact_dict[earlier_key].get("value", "")
            later_val = fact_dict[later_key].get("value", "")

            try:
                earlier_year = int(earlier_val)
                later_year = int(later_val)

                if earlier_year > later_year:
                    contradiction = Contradiction(
                        contradiction_type=ContradictionType.TEMPORAL_VIOLATION,
                        key=f"{earlier_key}_{later_key}",
                        values=[
                            (earlier_val, fact_dict[earlier_key].get("source", ""), 
                             fact_dict[earlier_key].get("confidence", 0.5)),
                            (later_val, fact_dict[later_key].get("source", ""), 
                             fact_dict[later_key].get("confidence", 0.5))
                        ],
                        severity="error",
                        explanation=f"{earlier_key} ({earlier_year}) must be before {later_key} ({later_year})",
                        resolution_hint=f"Verify or swap {earlier_key}/{later_key} values"
                    )
                    self.contradictions.append(contradiction)
            except (ValueError, TypeError):
                pass  # Not numeric, skip

    def _check_conflicting_values(self, items: List[dict]) -> None:
        """Detect same key with different values."""
        key_values = {}

        for item in items:
            key = item.get("key", "")
            value = item.get("value", "")

            if key not in key_values:
                key_values[key] = []
            key_values[key].append((
                value,
                item.get("source", "unknown"),
                item.get("confidence", 0.5)
            ))

        for key, values in key_values.items():
            unique_values = set(v[0] for v in values)
            if len(unique_values) > 1:  # Multiple distinct values for same fact
                contradiction = Contradiction(
                    contradiction_type=ContradictionType.CONFLICTING_VALUES,
                    key=key,
                    values=values,
                    severity="warning",
                    explanation=f"Fact '{key}' has {len(unique_values)} conflicting values",
                    resolution_hint=f"Recommended: {max(values, key=lambda x: x[2])[0]} (highest confidence)"
                )
                self.contradictions.append(contradiction)

    def _check_mutual_exclusions(self, items: List[dict]) -> None:
        """Verify mutually exclusive facts."""
        present_facts = {item.get("key", "") for item in items}

        for exclusion_set in self.MUTUAL_EXCLUSIONS:
            matching = [fact for fact in exclusion_set if fact in present_facts]
            if len(matching) > 1:
                contradiction = Contradiction(
                    contradiction_type=ContradictionType.MUTUAL_EXCLUSION,
                    key="_or_".join(matching),
                    values=[(f, "inferred", 1.0) for f in matching],
                    severity="error",
                    explanation=f"Cannot be both: {' and '.join(matching)}",
                    resolution_hint=f"Remove one of {matching}"
                )
                self.contradictions.append(contradiction)

    def resolve_contradiction(self, contradiction: Contradiction, chosen_value: str) -> None:
        """Mark contradiction as manually resolved."""
        contradiction.severity = "resolved"

    def summary(self) -> dict:
        """Statistics on contradictions."""
        by_type = {}
        by_severity = {}

        for c in self.contradictions:
            t = c.contradiction_type.value
            s = c.severity
            by_type[t] = by_type.get(t, 0) + 1
            by_severity[s] = by_severity.get(s, 0) + 1

        return {
            "total": len(self.contradictions),
            "by_type": by_type,
            "by_severity": by_severity,
            "errors": len([c for c in self.contradictions if c.severity == "error"]),
            "warnings": len([c for c in self.contradictions if c.severity == "warning"]),
        }
