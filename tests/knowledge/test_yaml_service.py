"""验证 YAML 知识目录加载、索引和引用解析。"""

from pathlib import Path

import pandas as pd

from petro_agent.core.models import CanonicalDataset, SourceInfo
from petro_agent.knowledge.rule_engine import RuleEngine
from petro_agent.knowledge.yaml_service import YamlKnowledgeService


ROOT = Path(__file__).resolve().parents[2]


def test_resolves_bilingual_concept_names():
    service = YamlKnowledgeService(ROOT / "knowledge_graph")
    assert service.resolve_concept("含水率").concept_id == "water_cut"
    assert service.resolve_concept("Water Cut").concept_id == "water_cut"


def test_knowledge_rule_flags_invalid_water_cut():
    service = YamlKnowledgeService(ROOT / "knowledge_graph")
    dataset = CanonicalDataset(
        "test",
        "reservoir_engineering",
        "water_flooding",
        pd.DataFrame({"water_cut_fraction": [0.2, 1.2]}),
        {"water_cut_fraction": "fraction"},
        SourceInfo("test", "test"),
    )
    resolved = service.resolve_dataset(dataset)
    rules = service.find_rules(
        concept_id="water_cut",
        context={"representation": "decimal_fraction"},
    )
    findings = RuleEngine().evaluate(dataset, rules, resolved, service.trace_evidence)
    assert len(findings) == 1
    assert not findings[0].passed
    assert findings[0].source_id == "petroleum_engineering_core"


def test_rule_engine_records_unresolved_targets_as_skipped():
    service = YamlKnowledgeService(ROOT / "knowledge_graph")
    dataset = CanonicalDataset(
        "test",
        "reservoir_engineering",
        "water_flooding",
        pd.DataFrame({"time_days": [0, 1]}),
        {"time_days": "day"},
        SourceInfo("test", "test"),
    )
    engine = RuleEngine()
    findings = engine.evaluate(
        dataset,
        service.find_rules(context={"representation": "decimal_fraction"}),
        service.resolve_dataset(dataset),
        service.trace_evidence,
    )
    assert len(findings) == 2
    assert engine.last_execution["loaded"] == 7
    assert engine.last_execution["executed"] == 2
    assert len(engine.last_execution["skipped"]) == 5
