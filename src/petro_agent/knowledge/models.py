"""定义知识实体、关系、规则和来源证据的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EngineeringConcept:
    concept_id: str
    concept_type: str
    name_zh: str
    name_en: str
    aliases_zh: tuple[str, ...] = ()
    aliases_en: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    description_zh: str | None = None
    description_en: str | None = None


@dataclass(frozen=True)
class EngineeringRelation:
    relation_id: str
    name_zh: str
    name_en: str
    inverse_name_zh: str | None = None
    inverse_name_en: str | None = None
    description_zh: str | None = None
    description_en: str | None = None


@dataclass(frozen=True)
class EngineeringRule:
    rule_id: str
    name_zh: str
    name_en: str
    rule_type: str
    target_concept: str
    operator: str
    expected: Any = None
    unit: str | None = None
    severity: str = "error"
    conditions: dict[str, Any] = field(default_factory=dict)
    source_id: str | None = None
    clause: str | None = None
    applicability_zh: str | None = None
    applicability_en: str | None = None


@dataclass(frozen=True)
class ResolvedField:
    field_name: str
    concept_id: str
    name_zh: str
    name_en: str
    actual_unit: str | None
    canonical_unit: str | None
