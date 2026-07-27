from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from petro_agent.core.models import CanonicalDataset
from petro_agent.knowledge.models import (
    EngineeringConcept,
    EngineeringRule,
    ResolvedField,
)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class YamlKnowledgeService:
    """Read the version-controlled knowledge source without requiring Neo4j."""

    def __init__(self, knowledge_root: Path):
        self.knowledge_root = knowledge_root
        self.manifest = _read_yaml(knowledge_root / "manifest.yaml").get(
            "knowledge_base", {}
        )
        self.version = str(self.manifest.get("version", "unknown"))
        self._concepts = self._load_concepts()
        self._field_mappings = self._load_field_mappings()
        self._rules = self._load_rules()
        self._sources = {
            item["source_id"]: item
            for item in _read_yaml(knowledge_root / "provenance/sources.yaml").get("sources", [])
        }

    def _load_concepts(self) -> dict[str, EngineeringConcept]:
        records: list[dict[str, Any]] = []
        for filename, key in (
            ("entities.yaml", "entities"),
            ("parameters.yaml", "parameters"),
        ):
            records.extend(_read_yaml(self.knowledge_root / "core" / filename).get(key, []))
        concepts: dict[str, EngineeringConcept] = {}
        for item in records:
            concept = EngineeringConcept(
                concept_id=item["concept_id"],
                concept_type=item["concept_type"],
                name_zh=item["name_zh"],
                name_en=item["name_en"],
                aliases_zh=tuple(item.get("aliases_zh", [])),
                aliases_en=tuple(item.get("aliases_en", [])),
                domains=tuple(item.get("domains", [])),
                description_zh=item.get("description_zh"),
                description_en=item.get("description_en"),
            )
            concepts[concept.concept_id] = concept
        return concepts

    def _load_field_mappings(self) -> dict[str, dict[str, Any]]:
        return _read_yaml(
            self.knowledge_root / "mappings/canonical_fields.yaml"
        ).get("mappings", {})

    def _load_rules(self) -> list[EngineeringRule]:
        return [
            EngineeringRule(
                rule_id=item["rule_id"],
                name_zh=item["name_zh"],
                name_en=item["name_en"],
                rule_type=item["rule_type"],
                target_concept=item["target_concept"],
                operator=item["operator"],
                expected=item.get("expected"),
                unit=item.get("unit"),
                severity=item.get("severity", "error"),
                conditions=item.get("conditions", {}),
                source_id=item.get("source_id"),
                clause=item.get("clause"),
                applicability_zh=item.get("applicability_zh"),
                applicability_en=item.get("applicability_en"),
            )
            for item in _read_yaml(self.knowledge_root / "core/rules.yaml").get("rules", [])
        ]

    def resolve_concept(self, term: str) -> EngineeringConcept | None:
        normalized = term.strip().casefold()
        for concept in self._concepts.values():
            names = (
                concept.concept_id,
                concept.name_zh,
                concept.name_en,
                *concept.aliases_zh,
                *concept.aliases_en,
            )
            if normalized in {name.casefold() for name in names}:
                return concept
        mapping = self._field_mappings.get(term)
        return self._concepts.get(mapping["concept_id"]) if mapping else None

    def resolve_dataset(self, dataset: CanonicalDataset) -> list[ResolvedField]:
        resolved: list[ResolvedField] = []
        for field_name in dataset.frame.columns:
            mapping = self._field_mappings.get(field_name)
            if not mapping:
                continue
            concept = self._concepts.get(mapping["concept_id"])
            if not concept:
                continue
            resolved.append(ResolvedField(
                field_name=field_name,
                concept_id=concept.concept_id,
                name_zh=concept.name_zh,
                name_en=concept.name_en,
                actual_unit=dataset.units.get(field_name),
                canonical_unit=mapping.get("canonical_unit"),
            ))
        return resolved

    def find_rules(
        self,
        concept_id: str | None = None,
        context: dict | None = None,
    ) -> list[EngineeringRule]:
        context = context or {}
        rules = self._rules
        if concept_id:
            rules = [rule for rule in rules if rule.target_concept == concept_id]
        return [rule for rule in rules if self._conditions_match(rule.conditions, context)]

    @staticmethod
    def _conditions_match(conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        return all(context.get(key) == value for key, value in conditions.items())

    def trace_evidence(self, rule_id: str) -> dict | None:
        rule = next((item for item in self._rules if item.rule_id == rule_id), None)
        if not rule:
            return None
        return self._sources.get(rule.source_id)
