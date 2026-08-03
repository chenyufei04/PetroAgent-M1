"""编排数据适配、指标计算、规则执行和报告生成全过程。"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from petro_agent.adapters.csv_adapter import CsvAdapter
from petro_agent.core.config import load_yaml
from petro_agent.core.metrics import summarize
from petro_agent.core.models import AnalysisResult
from petro_agent.domain_packs.common_reservoir.pack import CommonReservoirPack
from petro_agent.domain_packs.polymer_flooding.pack import PolymerFloodingPack
from petro_agent.knowledge.rule_engine import RuleEngine
from petro_agent.knowledge.yaml_service import YamlKnowledgeService
from petro_agent.reporting.markdown import write_report
from petro_agent.reporting.plots import create_figures


PACKS = {
    "common_reservoir": CommonReservoirPack,
    "polymer_flooding": PolymerFloodingPack,
}

MIGRATED_LEGACY_RULES = {
    "DATA_NOT_EMPTY",
    "TIME_MONOTONIC",
    "OIL_RATE_M3_DAY_NONNEGATIVE",
    "WATER_RATE_M3_DAY_NONNEGATIVE",
    "POLYMER_CONCENTRATION_KG_M3_NONNEGATIVE",
    "WATER_CUT_BOUNDS",
    "RECOVERY_BOUNDS",
    "RECOVERY_MONOTONIC",
    "POLYMER_CONCENTRATION_NONNEGATIVE",
}


def analyze_csv(
    source: Path,
    config_path: Path,
    output_root: Path,
    case_id_override: str | None = None,
) -> AnalysisResult:
    config = load_yaml(config_path)
    if case_id_override:
        config["case_id"] = case_id_override
    dataset = CsvAdapter().load(source, config)
    knowledge_config = config.get("knowledge", {})
    knowledge_enabled = knowledge_config.get("enabled", True)
    execution_mode = knowledge_config.get(
        "execution_mode",
        "knowledge" if knowledge_enabled else "legacy",
    )
    if execution_mode not in {"knowledge", "legacy", "hybrid"}:
        raise ValueError(
            "knowledge.execution_mode must be one of: knowledge, legacy, hybrid"
        )

    legacy_findings = []
    for name in config.get("domain_packs", ["common_reservoir"]):
        pack = PACKS[name]()
        dataset = pack.enrich(dataset)
        if execution_mode in {"legacy", "hybrid"}:
            legacy_findings.extend(pack.validate(dataset))

    findings = list(legacy_findings)
    knowledge_root = config_path.resolve().parents[2] / "knowledge_graph"
    execution = {
        "mode": execution_mode,
        "knowledge_version": None,
        "legacy_executed": len(legacy_findings),
        "knowledge_loaded": 0,
        "knowledge_executed": 0,
        "knowledge_skipped": [],
    }
    if execution_mode in {"knowledge", "hybrid"}:
        if not knowledge_enabled:
            raise ValueError(
                "knowledge.enabled must be true when execution_mode uses knowledge rules"
            )
        if not knowledge_root.exists():
            raise FileNotFoundError(f"Knowledge root not found: {knowledge_root}")
        knowledge_service = YamlKnowledgeService(knowledge_root)
        resolved_fields = knowledge_service.resolve_dataset(dataset)
        dataset.metadata["resolved_concepts"] = [
            {
                "field": item.field_name,
                "concept_id": item.concept_id,
                "name_zh": item.name_zh,
                "name_en": item.name_en,
            }
            for item in resolved_fields
        ]
        context = {
            "domain": dataset.domain,
            "process": dataset.process,
            **config.get("knowledge", {}).get("context", {}),
        }
        rules = knowledge_service.find_rules(context=context)
        engine = RuleEngine()
        knowledge_findings = engine.evaluate(
            dataset,
            rules,
            resolved_fields,
            knowledge_service.trace_evidence,
        )
        if execution_mode == "hybrid":
            findings = [
                item for item in findings
                if item.rule_id not in MIGRATED_LEGACY_RULES
            ]
        findings.extend(knowledge_findings)
        execution.update({
            "knowledge_version": knowledge_service.version,
            "knowledge_loaded": engine.last_execution["loaded"],
            "knowledge_executed": engine.last_execution["executed"],
            "knowledge_skipped": engine.last_execution["skipped"],
        })
    dataset.metadata["rule_execution"] = execution
    figures = create_figures(dataset, output_root / "figures")
    result = AnalysisResult(dataset, summarize(dataset.frame), findings, figures)
    write_report(result, output_root / "reports" / f"{dataset.case_id}.md")
    dataset.write_csv(output_root / "runs" / f"{dataset.case_id}_canonical.csv")
    result_path = output_root / "runs" / f"{dataset.case_id}_result.json"
    result_path.write_text(
        json.dumps(
            {
                "case": dataset.to_metadata(),
                "summary": result.summary,
                "findings": [asdict(item) for item in result.findings],
                "figures": [item.name for item in result.figures],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return result
