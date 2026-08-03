"""执行 YAML 声明的确定性规则，并生成带证据的判断结果。"""

from __future__ import annotations

from typing import Any

import numpy as np

from petro_agent.core.models import CanonicalDataset, ValidationFinding
from petro_agent.knowledge.models import EngineeringRule, ResolvedField


class RuleEngine:
    def __init__(self) -> None:
        self.last_execution: dict[str, Any] = {
            "loaded": 0,
            "executed": 0,
            "skipped": [],
        }

    def evaluate(
        self,
        dataset: CanonicalDataset,
        rules: list[EngineeringRule],
        resolved_fields: list[ResolvedField],
        evidence_lookup,
    ) -> list[ValidationFinding]:
        concept_fields = {item.concept_id: item for item in resolved_fields}
        findings: list[ValidationFinding] = []
        skipped: list[dict[str, str]] = []
        for rule in rules:
            field = concept_fields.get(rule.target_concept)
            if rule.target_concept == "dataset":
                values: Any = dataset.frame
            elif field and field.field_name in dataset.frame:
                values = dataset.frame[field.field_name].dropna()
            else:
                skipped.append({
                    "rule_id": rule.rule_id,
                    "target_concept": rule.target_concept,
                    "reason": "target_concept_not_resolved",
                })
                continue
            passed, observed = self._apply(rule.operator, values, rule.expected)
            evidence = evidence_lookup(rule.rule_id) or {}
            findings.append(ValidationFinding(
                rule_id=rule.rule_id,
                severity=rule.severity,
                passed=passed,
                message=f"{rule.name_zh} / {rule.name_en}",
                observed=observed,
                concept_id=rule.target_concept,
                expected=rule.expected,
                actual_unit=field.actual_unit if field else None,
                canonical_unit=rule.unit or (field.canonical_unit if field else None),
                source_id=rule.source_id,
                source_name=evidence.get("name_zh"),
                clause=rule.clause,
                applicability=rule.applicability_zh,
            ))
        self.last_execution = {
            "loaded": len(rules),
            "executed": len(findings),
            "skipped": skipped,
        }
        return findings

    @staticmethod
    def _apply(operator: str, values: Any, expected: Any) -> tuple[bool, Any]:
        if operator == "not_empty":
            return not values.empty, len(values)
        if len(values) == 0:
            return True, None
        array = values.to_numpy()
        if operator == "between":
            lower, upper = expected["min"], expected["max"]
            return bool(((array >= lower) & (array <= upper)).all()), {
                "min": float(np.min(array)),
                "max": float(np.max(array)),
            }
        if operator == "greater_than_or_equal":
            return bool((array >= expected).all()), float(np.min(array))
        if operator == "monotonic_non_decreasing":
            tolerance = float((expected or {}).get("tolerance", 0))
            return bool(np.all(np.diff(array) >= -tolerance)), None
        raise ValueError(f"Unsupported knowledge rule operator: {operator}")
