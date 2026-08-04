"""验证 YAML 知识图谱的幂等 Neo4j 导入。"""

from pathlib import Path

from petro_agent.knowledge.neo4j.importer import Neo4jKnowledgeImporter


ROOT = Path(__file__).resolve().parents[2]


def test_build_plan_contains_domain_graph_and_rules():
    plan = Neo4jKnowledgeImporter(ROOT / "knowledge_graph").build_plan()

    assert len(plan.triples) == 17
    assert len(plan.rules) == 32
    assert plan.domain["domain_id"] == "chemical_eor"
    assert all(item["concept_id"] for item in plan.concepts)


def test_all_referenced_concepts_have_chinese_names():
    plan = Neo4jKnowledgeImporter(ROOT / "knowledge_graph").build_plan()
    concepts = {item["concept_id"]: item for item in plan.concepts}

    assert concepts["polymer_solution_viscosity"]["name_zh"] == "聚合物溶液黏度"
    assert all(item.get("name_zh") for item in plan.concepts)
    assert all(item["placeholder"] is False for item in plan.concepts)
    assert concepts["polymer_flooding"]["placeholder"] is False
    assert concepts["net_incremental_value"]["name_zh"] == "净增量价值"
