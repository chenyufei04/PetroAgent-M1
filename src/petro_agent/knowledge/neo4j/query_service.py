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

    def concept_subgraph(
        self,
        concept_ids: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, list[dict]]:
        """Return a UI-safe Concept subgraph without accepting arbitrary Cypher."""
        with self.client.session() as session:
            result = session.run(
                """
                MATCH (a:Concept)-[r]->(b:Concept)
                WHERE size($concept_ids) = 0
                   OR a.concept_id IN $concept_ids
                   OR b.concept_id IN $concept_ids
                RETURN a.concept_id AS source_id,
                       coalesce(a.name_zh, a.name_en, a.concept_id) AS source_name,
                       b.concept_id AS target_id,
                       coalesce(b.name_zh, b.name_en, b.concept_id) AS target_name,
                       type(r) AS relation_id,
                       coalesce(r.name_zh, r.name_en, type(r)) AS relation_name
                ORDER BY source_id, relation_name, target_id
                LIMIT $limit
                """,
                concept_ids=concept_ids or [],
                limit=limit,
            )
            rows = [dict(record) for record in result]
        nodes: dict[str, dict] = {}
        edges = []
        for index, row in enumerate(rows, start=1):
            nodes[row["source_id"]] = {
                "id": row["source_id"],
                "label": row["source_name"],
                "type": "Concept",
            }
            nodes[row["target_id"]] = {
                "id": row["target_id"],
                "label": row["target_name"],
                "type": "Concept",
            }
            edges.append({
                "id": f"edge-{index}",
                "source": row["source_id"],
                "target": row["target_id"],
                "label": row["relation_name"],
                "relation_id": row["relation_id"],
            })
        return {"nodes": list(nodes.values()), "edges": edges}

    def graph_view(self, view: str = "all", limit: int = 200) -> dict:
        """Return one of the predefined, read-only graph views for the UI."""
        patterns = {
            "all": "MATCH (a)-[r]->(b)",
            "concepts": "MATCH (a:Concept)-[r]->(b:Concept)",
            "rules": "MATCH (a:Rule)-[r]->(b:Concept)",
            "sources": "MATCH (a:Rule)-[r:SUPPORTED_BY]->(b:Source)",
            "stages": "MATCH (a:Rule)-[r:IN_STAGE]->(b:Stage)",
        }
        if view not in patterns:
            raise ValueError(f"不支持的图谱视图：{view}")

        query = f"""
            {patterns[view]}
            RETURN elementId(a) AS source_element_id,
                   labels(a) AS source_labels,
                   properties(a) AS source_properties,
                   elementId(b) AS target_element_id,
                   labels(b) AS target_labels,
                   properties(b) AS target_properties,
                   elementId(r) AS relationship_element_id,
                   type(r) AS relationship_type,
                   properties(r) AS relationship_properties
            LIMIT $limit
        """
        with self.client.session() as session:
            rows = [dict(record) for record in session.run(query, limit=limit)]
            isolated_rows = []
            if view == "all":
                isolated_rows = [
                    dict(record)
                    for record in session.run(
                        """
                        MATCH (n)
                        RETURN elementId(n) AS element_id,
                               labels(n) AS labels,
                               properties(n) AS properties
                        LIMIT $limit
                        """,
                        limit=limit,
                    )
                ]

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        for row in isolated_rows:
            node = self._ui_node(
                row["element_id"],
                row["labels"],
                row["properties"],
            )
            nodes[node["id"]] = node
        for row in rows:
            source = self._ui_node(
                row["source_element_id"],
                row["source_labels"],
                row["source_properties"],
            )
            target = self._ui_node(
                row["target_element_id"],
                row["target_labels"],
                row["target_properties"],
            )
            nodes[source["id"]] = source
            nodes[target["id"]] = target
            relation_props = row["relationship_properties"] or {}
            edges.append({
                "id": row["relationship_element_id"],
                "source": source["id"],
                "source_label": source["label"],
                "target": target["id"],
                "target_label": target["label"],
                "label": relation_props.get("name_zh")
                    or relation_props.get("name_en")
                    or row["relationship_type"],
                "relation_id": row["relationship_type"],
                "properties": relation_props,
            })
        return {"nodes": list(nodes.values()), "edges": edges}

    @staticmethod
    def _ui_node(element_id: str, labels: list[str], properties: dict) -> dict:
        properties = properties or {}
        stable_id = (
            properties.get("concept_id")
            or properties.get("rule_id")
            or properties.get("source_id")
            or properties.get("stage_id")
            or properties.get("parameter_id")
            or properties.get("id")
            or element_id
        )
        label = (
            properties.get("name_zh")
            or properties.get("name")
            or properties.get("title")
            or properties.get("name_en")
            or stable_id
        )
        return {
            "id": str(stable_id),
            "label": str(label),
            "type": labels[0] if labels else "Node",
            "labels": labels,
            "properties": properties,
        }
