from __future__ import annotations
from typing import Protocol
from petro_agent.core.models import CanonicalDataset
from petro_agent.knowledge.models import EngineeringConcept, EngineeringRule, ResolvedField


class KnowledgeService(Protocol):
    def resolve_concept(self, term: str) -> EngineeringConcept | None:
        ...

    def resolve_dataset(self, dataset: CanonicalDataset) -> list[ResolvedField]:
        ...

    def find_rules(
        self,
        concept_id: str | None = None,
        context: dict | None = None,
    ) -> list[EngineeringRule]:
        ...

    def trace_evidence(self, rule_id: str) -> dict | None:
        ...
