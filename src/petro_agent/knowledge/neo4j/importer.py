"""Idempotent YAML-to-Neo4j importer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .client import Neo4jClient


_SAFE_RELATION = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class ImportPlan:
    concepts: list[dict]
    triples: list[dict]
    rules: list[dict]
    sources: list[dict]
    domain: dict

    def summary(self) -> dict[str, int]:
        return {
            "concepts": len(self.concepts),
            "triples": len(self.triples),
            "rules": len(self.rules),
            "sources": len(self.sources),
        }


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class Neo4jKnowledgeImporter:
    def __init__(self, knowledge_root: Path):
        self.knowledge_root = knowledge_root

    def build_plan(self) -> ImportPlan:
        core = self.knowledge_root / "core"
        domain_path = (
            self.knowledge_root
            / "domains"
            / "chemical_eor"
            / "polymer_flooding.yaml"
        )
        entities = _read_yaml(core / "entities.yaml").get("entities", [])
        parameters = _read_yaml(core / "parameters.yaml").get("parameters", [])
        domain_data = _read_yaml(domain_path)
        domain_concepts = domain_data.get("concepts", [])
        triples = domain_data.get("triples", [])
        rules = domain_data.get("rule_catalog", {}).get("rules", [])
        source_data = _read_yaml(
            self.knowledge_root / "provenance" / "sources.yaml"
        )
        sources = source_data.get("sources", [])

        concepts: dict[str, dict] = {}
        for item in [*entities, *parameters, *domain_concepts]:
            concept = dict(item)
            concept["placeholder"] = False
            concepts[concept["concept_id"]] = concept

        referenced_ids = {
            value
            for triple in triples
            for value in (triple["subject"], triple["object"])
        }
        referenced_ids.update(
            input_id
            for rule in rules
            for input_id in rule.get("inputs", [])
        )
        for concept_id in referenced_ids:
            concepts.setdefault(
                concept_id,
                {
                    "concept_id": concept_id,
                    "concept_type": "unclassified",
                    "name_en": concept_id.replace("_", " ").title(),
                    "placeholder": True,
                },
            )

        relation_ids = {
            item["relation_id"]
            for item in _read_yaml(core / "relations.yaml").get("relations", [])
        }
        for triple in triples:
            relation = triple["relation"]
            if relation not in relation_ids:
                raise ValueError(f"未定义的关系类型: {relation}")
            if not _SAFE_RELATION.fullmatch(relation):
                raise ValueError(f"不安全的关系类型: {relation}")

        domain = dict(domain_data.get("domain_graph", {}))
        return ImportPlan(
            concepts=list(concepts.values()),
            triples=triples,
            rules=rules,
            sources=sources,
            domain=domain,
        )

    def import_all(self, client: "Neo4jClient") -> dict[str, int]:
        plan = self.build_plan()
        relation_names = self._relation_names()
        with client.session() as session:
            self._create_constraints(session)
            self._write_concepts(session, plan.concepts)
            self._write_domain(session, plan)
            self._write_rules(session, plan, relation_names)
            self._write_triples(session, plan.triples, relation_names)
        return plan.summary()

    def _relation_names(self) -> dict[str, dict[str, str]]:
        rows = _read_yaml(
            self.knowledge_root / "core" / "relations.yaml"
        ).get("relations", [])
        return {
            row["relation_id"]: {
                "name_zh": row["name_zh"],
                "name_en": row["name_en"],
            }
            for row in rows
        }

    @staticmethod
    def _create_constraints(session) -> None:
        for label, key in (
            ("Concept", "concept_id"),
            ("Domain", "domain_id"),
            ("Rule", "rule_id"),
            ("Stage", "stage_id"),
            ("Source", "source_id"),
        ):
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
            ).consume()

    @staticmethod
    def _write_concepts(session, concepts: list[dict]) -> None:
        session.run(
            """
            UNWIND $rows AS row
            MERGE (n:Concept {concept_id: row.concept_id})
            SET n += row
            """,
            rows=concepts,
        ).consume()

    @staticmethod
    def _write_domain(session, plan: ImportPlan) -> None:
        domain = plan.domain
        session.run(
            """
            MERGE (d:Domain {domain_id: $domain.domain_id})
            SET d += $domain
            """,
            domain=domain,
        ).consume()

    @staticmethod
    def _write_rules(
        session, plan: ImportPlan, relation_names: dict[str, dict[str, str]]
    ) -> None:
        source_ids = {source["source_id"] for source in plan.sources}
        used_source_ids = {
            rule["source_id"]
            for rule in plan.rules
            if rule.get("source_id")
        }
        missing_sources = sorted(used_source_ids - source_ids)
        if missing_sources:
            raise ValueError(
                f"规则引用了未登记的来源: {', '.join(missing_sources)}"
            )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Source {source_id: row.source_id})
            SET s += row
            """,
            rows=plan.sources,
        ).consume()
        session.run(
            """
            UNWIND $rows AS row
            MERGE (r:Rule {rule_id: row.rule_id})
            SET r += row.properties
            MERGE (stage:Stage {stage_id: row.stage})
            SET stage.name_zh = row.stage_name_zh,
                stage.name_en = row.stage_name_en
            MERGE (r)-[inStage:IN_STAGE]->(stage)
            SET inStage += $in_stage_names
            WITH r, row
            MATCH (d:Domain {domain_id: $domain_id})
            MERGE (d)-[hasRule:HAS_RULE]->(r)
            SET hasRule += $has_rule_names
            WITH r, row
            MATCH (s:Source {source_id: row.source_id})
            MERGE (r)-[supportedBy:SUPPORTED_BY]->(s)
            SET supportedBy += $supported_by_names
            """,
            rows=[
                {
                    "rule_id": rule["rule_id"],
                    "stage": rule["stage"],
                    "stage_name_zh": {
                        "screening": "候选筛选",
                        "laboratory": "配伍与实验",
                        "design": "方案设计",
                        "simulation": "数值模拟",
                        "operation": "注入运行",
                        "surveillance": "动态评价",
                    }[rule["stage"]],
                    "stage_name_en": rule["stage"].replace("_", " ").title(),
                    "source_id": rule["source_id"],
                    "properties": {
                        key: value
                        for key, value in rule.items()
                        if key not in {"inputs"}
                    },
                }
                for rule in plan.rules
            ],
            domain_id=plan.domain["domain_id"],
            in_stage_names=relation_names["IN_STAGE"],
            has_rule_names=relation_names["HAS_RULE"],
            supported_by_names=relation_names["SUPPORTED_BY"],
        ).consume()
        session.run(
            """
            UNWIND $rows AS row
            MATCH (r:Rule {rule_id: row.rule_id})
            UNWIND row.inputs AS input_id
            MATCH (c:Concept {concept_id: input_id})
            MERGE (r)-[usesInput:USES_INPUT]->(c)
            SET usesInput += $uses_input_names
            """,
            rows=[
                {"rule_id": rule["rule_id"], "inputs": rule.get("inputs", [])}
                for rule in plan.rules
            ],
            uses_input_names=relation_names["USES_INPUT"],
        ).consume()

    @staticmethod
    def _write_triples(
        session,
        triples: list[dict],
        relation_names: dict[str, dict[str, str]],
    ) -> None:
        by_relation: dict[str, list[dict]] = {}
        for triple in triples:
            by_relation.setdefault(triple["relation"], []).append(triple)
        for relation, rows in by_relation.items():
            session.run(
                f"""
                UNWIND $rows AS row
                MATCH (source:Concept {{concept_id: row.subject}})
                MATCH (target:Concept {{concept_id: row.object}})
                MERGE (source)-[r:{relation}]->(target)
                SET r.source = 'knowledge_graph YAML',
                    r.name_zh = $relation_names.name_zh,
                    r.name_en = $relation_names.name_en
                """,
                rows=rows,
                relation_names=relation_names[relation],
            ).consume()
