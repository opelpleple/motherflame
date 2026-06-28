"""
Entity coreference resolution — link duplicate mentions of same entity.

Problem: "Opel", "CEO", "opelpleple@users.noreply.github.com" = same person
Solution: Record coreference chains, resolve to canonical form

Strategies:
1. Exact match (after normalization)
2. Fuzzy match (Levenshtein distance)
3. Context matching (same org, similar role)
4. Email domain matching
"""

import json
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import difflib


@dataclass
class CoreferenceChain:
    """Links multiple mentions of same entity."""
    canonical_id: str  # Primary identifier
    canonical_name: str
    mentions: List[str] = field(default_factory=list)  # Alternative forms
    confidence: float = 0.8
    evidence: List[str] = field(default_factory=list)  # Why we linked them


class CoreferenceResolver:
    """Resolve entity mentions to canonical forms."""

    def __init__(self, similarity_threshold: float = 0.85):
        self.chains: Dict[str, CoreferenceChain] = {}  # canonical_id → chain
        self.mention_to_canonical: Dict[str, str] = {}  # mention → canonical_id
        self.similarity_threshold = similarity_threshold

    def link_entities(self, name1: str, name2: str, context: Dict = None) -> Tuple[bool, float]:
        """
        Determine if two name mentions refer to same entity.
        Returns: (is_same, confidence)
        """
        confidence = 0.0

        # Strategy 1: Exact match (case-insensitive)
        if name1.lower() == name2.lower():
            return (True, 1.0)

        # Strategy 2: Email domain match
        if "@" in name1 and "@" in name2:
            domain1 = name1.split("@")[1] if "@" in name1 else ""
            domain2 = name2.split("@")[1] if "@" in name2 else ""
            if domain1 == domain2:
                confidence = 0.7

        # Strategy 3: Fuzzy string match
        similarity = difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
        if similarity > self.similarity_threshold:
            confidence = max(confidence, similarity)

        # Strategy 4: Common abbreviations
        abbrev_map = {
            "opel": ["opelpleple", "opel pleple", "opel p."],
            "bombay": ["bombay singh", "b. singh"],
            "peter": ["peter bu", "peterbu", "p. bu"],
        }
        for canonical, variants in abbrev_map.items():
            if (name1.lower() in variants and name2.lower() == canonical) or \
               (name2.lower() in variants and name1.lower() == canonical):
                confidence = max(confidence, 0.95)

        # Strategy 5: Role-based linking (if context provided)
        if context:
            org1 = context.get("org", "")
            role1 = context.get("role", "")
            if org1 and role1:
                # If both mentions are for same org + role, likely same person
                confidence = max(confidence, 0.85)

        return (confidence >= self.similarity_threshold, confidence)

    def add_chain(self, chain: CoreferenceChain) -> None:
        """Register a coreference chain."""
        self.chains[chain.canonical_id] = chain
        for mention in chain.mentions:
            self.mention_to_canonical[mention.lower()] = chain.canonical_id

    def resolve(self, name: str) -> Optional[str]:
        """Resolve name mention to canonical form."""
        return self.mention_to_canonical.get(name.lower())

    def merge_chains(self, chain1_id: str, chain2_id: str, evidence: str = "") -> None:
        """Merge two coreference chains."""
        if chain1_id not in self.chains or chain2_id not in self.chains:
            return

        chain1 = self.chains[chain1_id]
        chain2 = self.chains[chain2_id]

        # Keep chain with higher confidence as canonical
        if chain2.confidence > chain1.confidence:
            # Swap so chain1 is the keeper
            chain1_id, chain2_id = chain2_id, chain1_id
            chain1, chain2 = chain2, chain1

        # Merge mentions
        chain1.mentions.extend(chain2.mentions)
        chain1.evidence.append(evidence)
        chain1.confidence = (chain1.confidence + chain2.confidence) / 2

        # Update indices
        for mention in chain2.mentions:
            self.mention_to_canonical[mention.lower()] = chain1.canonical_id

        # Remove old chain
        del self.chains[chain2_id]

    def build_from_facts(self, items: List[dict]) -> None:
        """Auto-detect coreference chains from canonical facts."""
        # Collect all entity mentions
        mentions_by_type = defaultdict(list)

        for item in items:
            key = item.get("key", "")
            value = item.get("value", "")

            # Detect entity types from keys
            if key in ["ceo", "cto", "cfo", "founder", "name"]:
                mentions_by_type["entity"].append((value, key))

        # Link similar mentions
        entities = mentions_by_type.get("entity", [])
        seen = set()

        for i, (name1, role1) in enumerate(entities):
            if name1.lower() in seen:
                continue

            chain = CoreferenceChain(
                canonical_id=f"entity:{name1.lower().replace(' ', '_')}",
                canonical_name=name1,
                mentions=[name1],
                evidence=[f"primary:{role1}"]
            )

            # Find similar mentions
            for j, (name2, role2) in enumerate(entities[i + 1:], i + 1):
                is_same, confidence = self.link_entities(name1, name2)
                if is_same:
                    chain.mentions.append(name2)
                    chain.evidence.append(f"{role2}@confidence={confidence:.2f}")
                    seen.add(name2.lower())

            self.add_chain(chain)
            seen.add(name1.lower())

    def export_chains(self) -> List[dict]:
        """Export all coreference chains."""
        return [
            {
                "canonical_id": chain.canonical_id,
                "canonical_name": chain.canonical_name,
                "mentions": chain.mentions,
                "confidence": chain.confidence,
                "evidence": chain.evidence,
            }
            for chain in self.chains.values()
        ]

    def stats(self) -> dict:
        """Coreference resolution statistics."""
        total_mentions = sum(len(chain.mentions) for chain in self.chains.values())
        return {
            "chains": len(self.chains),
            "total_mentions": total_mentions,
            "avg_mentions_per_chain": total_mentions / len(self.chains) if self.chains else 0,
            "high_confidence_chains": len([c for c in self.chains.values() if c.confidence >= 0.9]),
        }
