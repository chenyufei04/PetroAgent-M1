"""Read-only graph queries used by scripts and the agent layer."""

from __future__ import annotations

from .client import Neo4jClient


class Neo4jQueryService:
    def __init__(self, client: Neo4jClient):
        self.client = client

    def graph_counts(self) -> dict[str, int]:
        with self.client.session() as session:
            record = session.run(
                """
                MATCH (n)
                OPTIONAL MATCH ()-[r]->()
                RETURN count(DISTINCT n) AS nodes,
                       count(DISTINCT r) AS relationships
                """
            ).single(strict=True)
            return dict(record)

    def domain_triples(self, limit: int = 200) -> list[dict]:
        with self.client.session() as session:
            result = session.run(
                """
                MATCH (a:Concept)-[r]->(b:Concept)
                RETURN a.concept_id AS subject_id,
                       coalesce(a.name_zh, a.name_en, a.concept_id) AS subject,
                       type(r) AS relation_id,
                       coalesce(r.name_zh, r.name_en, type(r)) AS relation,
                       b.concept_id AS object_id,
                       coalesce(b.name_zh, b.name_en, b.concept_id) AS object
                ORDER BY subject_id, relation, object_id
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(record) for record in result]

    def rules_for_stage(self, stage: str | None = None) -> list[dict]:
        with self.client.session() as session:
            result = session.run(
                """
                MATCH (r:Rule)-[:IN_STAGE]->(s:Stage)
                WHERE $stage IS NULL OR s.stage_id = $stage
                OPTIONAL MATCH (r)-[:SUPPORTED_BY]->(source:Source)
                RETURN r.rule_id AS rule_id,
                       r.name_zh AS name,
                       s.stage_id AS stage,
                       source.source_id AS source_id
                ORDER BY stage, rule_id
                """,
                stage=stage,
            )
            return [dict(record) for record in result]
