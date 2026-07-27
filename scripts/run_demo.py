from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.pipeline import analyze_csv


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def print_graph_relations(knowledge_root: Path) -> None:
    """以文本三元组输出聚合物驱知识图谱关系。"""
    concept_names: dict[str, str] = {}
    for filename, key in (
        ("entities.yaml", "entities"),
        ("parameters.yaml", "parameters"),
    ):
        data = _read_yaml(knowledge_root / "core" / filename)
        for item in data.get(key, []):
            concept_names[item["concept_id"]] = item.get(
                "name_zh", item["concept_id"]
            )

    relation_data = _read_yaml(knowledge_root / "core" / "relations.yaml")
    relation_names = {
        item["relation_id"]: item.get("name_zh", item["relation_id"])
        for item in relation_data.get("relations", [])
    }

    graph_data = _read_yaml(
        knowledge_root
        / "domains"
        / "chemical_eor"
        / "polymer_flooding.yaml"
    )
    triples = graph_data.get("triples", [])

    print()
    print(f"图谱关系佐证: 共 {len(triples)} 条")
    for index, triple in enumerate(triples, start=1):
        subject_id = triple["subject"]
        relation_id = triple["relation"]
        object_id = triple["object"]
        subject_name = concept_names.get(subject_id, subject_id)
        relation_name = relation_names.get(relation_id, relation_id)
        object_name = concept_names.get(object_id, object_id)
        print(
            f"{index:02d}. "
            f"{subject_name} [{subject_id}] "
            f"--{relation_name} [{relation_id}]--> "
            f"{object_name} [{object_id}]"
        )


if __name__ == "__main__":
    result = analyze_csv(
        ROOT / "data/demo/polymer_simple2d_demo.csv",
        ROOT / "config/cases/polymer_simple2d.yaml",
        ROOT / "outputs",
    )
    execution = result.dataset.metadata["rule_execution"]
    passed = sum(item.passed for item in result.findings)
    failed = len(result.findings) - passed
    print(f"完成: {result.dataset.case_id}")
    print(f"规则执行模式: {execution['mode']}")
    if execution["knowledge_version"]:
        print(f"知识库版本: Knowledge Foundation v{execution['knowledge_version']}")
        print(
            "知识规则: "
            f"加载 {execution['knowledge_loaded']} 条, "
            f"执行 {execution['knowledge_executed']} 条, "
            f"跳过 {len(execution['knowledge_skipped'])} 条"
        )
    print(f"校验结果: 通过 {passed} 条, 未通过 {failed} 条")
    print(f"报告: {ROOT / 'outputs/reports' / f'{result.dataset.case_id}.md'}")
    print_graph_relations(ROOT / "knowledge_graph")