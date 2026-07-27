from __future__ import annotations
from pathlib import Path
from petro_agent.knowledge.yaml_service import YamlKnowledgeService


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    service = YamlKnowledgeService(ROOT / "knowledge_graph")
    required = ("含水率", "Water Cut", "polymer_concentration")
    missing = [term for term in required if service.resolve_concept(term) is None]
    if missing:
        raise SystemExit(f"知识校验失败，无法解析：{', '.join(missing)}")
    print("知识基础层校验通过 / Knowledge foundation validation passed")


if __name__ == "__main__":
    main()
