from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.knowledge.yaml_service import YamlKnowledgeService


def main() -> None:
    service = YamlKnowledgeService(ROOT / "knowledge_graph")
    required = ("含水率", "Water Cut", "polymer_concentration")
    missing = [term for term in required if service.resolve_concept(term) is None]
    if missing:
        raise SystemExit(f"知识校验失败，无法解析：{', '.join(missing)}")

    domain_path = (
        ROOT / "knowledge_graph/domains/chemical_eor/polymer_flooding.yaml"
    )
    domain = yaml.safe_load(domain_path.read_text(encoding="utf-8"))
    domain_rules = domain.get("rule_catalog", {}).get("rules", [])
    rule_ids = [item["rule_id"] for item in domain_rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise SystemExit("知识校验失败：聚合物驱领域规则 ID 重复")

    source_ids = {
        item["source_id"]
        for item in yaml.safe_load(
            (ROOT / "knowledge_graph/provenance/sources.yaml").read_text(
                encoding="utf-8"
            )
        ).get("sources", [])
    }
    unknown_sources = sorted({
        item.get("source_id")
        for item in domain_rules
        if item.get("source_id") not in source_ids
    })
    if unknown_sources:
        raise SystemExit(
            "知识校验失败，领域规则引用未知来源："
            + ", ".join(unknown_sources)
        )

    print(
        "知识基础层校验通过 / Knowledge foundation validation passed\n"
        f"知识库版本 / Version: {service.version}\n"
        f"聚合物驱领域规则 / Polymer-flood domain rules: {len(domain_rules)}"
    )


if __name__ == "__main__":
    main()
