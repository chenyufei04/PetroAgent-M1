"""为脚本、智能体、API 和 Web 界面提供只读图查询。"""

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
        """返回前端允许使用的预定义只读图视图。"""
        patterns = {
            "all": "MATCH (a)-[r]->(b)",
            "concepts": "MATCH (a:Concept)-[r]->(b:Concept)",
            "rules": "MATCH (a:Rule)-[r]->(b:Concept)",
            "sources": "MATCH (a:Rule)-[r:SUPPORTED_BY]->(b:Source)",
            "stages": "MATCH (a:Rule)-[r:IN_STAGE]->(b:Stage)",
            "experiments": "MATCH (a)-[r]->(b) WHERE a:AnalysisCase OR a:Experiment OR a:SimulationCase OR a:Comparison",
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

    def experiment_rankings(self, experiment_id: str) -> list[dict]:
        """优先返回技术经济排名，并保留水驱基准供 API 和智能体解释。"""
        with self.client.session() as session:
            rows = session.run(
                """
                MATCH (e:Experiment {experiment_id: $experiment_id})-[:HAS_CASE]->(c:SimulationCase)
                MATCH (c)-[:HAS_PARAMETER_SET]->(p:ParameterSet)
                MATCH (c)-[:HAS_RESULT]->(m:MetricResult)
                OPTIONAL MATCH (c)-[:HAS_COMPARISON]->(cmp:Comparison)-[:USES_BASELINE]->(baseline:SimulationCase)
                OPTIONAL MATCH (c)-[:HAS_ECONOMIC_EVALUATION]->(x:EconomicEvaluation)
                RETURN c.case_id AS case_id,
                       p.polymer_concentration AS polymer_concentration,
                       p.injection_rate AS injection_rate,
                       m.final_cumulative_oil_m3 AS final_cumulative_oil_m3,
                       cmp.incremental_cumulative_oil_m3 AS incremental_cumulative_oil_m3,
                       cmp.incremental_oil_percent AS incremental_oil_percent,
                       baseline.case_id AS baseline_case_id
                       ,x.scenario_rank AS scenario_rank,
                       x.net_incremental_value AS net_incremental_value,
                       x.technically_feasible AS technically_feasible,
                       x.economically_positive AS economically_positive,
                       x.recommendation AS recommendation
                ORDER BY coalesce(x.scenario_rank, 999999), incremental_cumulative_oil_m3 DESC, case_id
                """,
                experiment_id=experiment_id,
            )
            return [dict(record) for record in rows]

    def scenario_explanation(self, case_id: str) -> dict | None:
        """沿指标概念、规则执行、推荐和来源关系返回单方案解释链。"""
        with self.client.session() as session:
            record = session.run(
                """
                MATCH (c:SimulationCase {case_id: $case_id})
                OPTIONAL MATCH (c)-[:HAS_OBSERVATION]->(o:MetricObservation)-[:OBSERVES]->(concept:Concept)
                WITH c, collect(DISTINCT {observation_id: o.observation_id, concept_id: concept.concept_id,
                     concept_name: coalesce(concept.name_zh, concept.name_en), value: o.value, unit: o.unit}) AS observations
                OPTIONAL MATCH (c)-[:EXECUTED_RULE]->(x:RuleExecution)-[:EXECUTES]->(rule:Rule)
                OPTIONAL MATCH (x)-[:SUPPORTED_BY]->(rule_source:Source)
                WITH c, observations, collect(DISTINCT {rule_execution_id: x.rule_execution_id,
                     rule_id: rule.rule_id, rule_name: coalesce(rule.name_zh, rule.name_en), passed: x.passed,
                     actual: x.actual, expected: x.expected, operator: x.operator, message: x.message,
                     evidence_source_id: rule_source.source_id, evidence_name: coalesce(rule_source.name_zh, rule_source.name_en)}) AS rule_executions
                OPTIONAL MATCH (c)-[:PRODUCES_RECOMMENDATION]->(r:Recommendation)-[:SUPPORTED_BY]->(source:Source)
                RETURN c.case_id AS case_id, observations, rule_executions,
                       head(collect(DISTINCT {recommendation_id: r.recommendation_id, decision: r.decision,
                            scenario_rank: r.scenario_rank, rationale: r.rationale,
                            assumption_status: r.assumption_status})) AS recommendation,
                       head(collect(DISTINCT {source_id: source.source_id,
                            source_name: coalesce(source.name_zh, source.name_en),
                            authority_level: source.authority_level})) AS evidence
                """,
                case_id=case_id,
            ).single()
            if record is None:
                return None
            payload = dict(record)
            payload["observations"] = [item for item in payload["observations"] if item.get("observation_id")]
            payload["rule_executions"] = [item for item in payload["rule_executions"] if item.get("rule_execution_id")]
            return payload

    @staticmethod
    def _ui_node(element_id: str, labels: list[str], properties: dict) -> dict:
        properties = properties or {}
        primary_keys = {
            "AnalysisCase": "analysis_case_id", "Experiment": "experiment_id",
            "SimulationCase": "case_id", "Comparison": "comparison_id",
            "Deck": "deck_id", "ParameterSet": "parameter_set_id",
            "SimulatorRun": "run_id", "MetricResult": "metric_result_id",
            "EconomicEvaluation": "economic_evaluation_id",
            "MetricObservation": "observation_id", "RuleExecution": "rule_execution_id",
            "Recommendation": "recommendation_id",
            "Dataset": "dataset_id", "Report": "report_id",
        }
        # 实例节点常同时携带父级外键，优先按 Neo4j 标签选择自身主键。
        stable_id = next(
            (properties[key] for label, key in primary_keys.items() if label in labels and properties.get(key)),
            None,
        ) or (
            properties.get("concept_id")
            or properties.get("analysis_case_id")
            or properties.get("comparison_id")
            or properties.get("deck_id")
            or properties.get("parameter_set_id")
            or properties.get("run_id")
            or properties.get("metric_result_id")
            or properties.get("dataset_id")
            or properties.get("report_id")
            or properties.get("case_id")
            or properties.get("experiment_id")
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
