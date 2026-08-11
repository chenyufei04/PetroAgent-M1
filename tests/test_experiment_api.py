"""验证实验列表、详情、配对结果及安全文件下载接口。"""

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from petro_agent.api import main


def _write_experiment(root: Path) -> None:
    experiment = root / "sweep_a"
    analysis = experiment / "analysis" / "figures"
    analysis.mkdir(parents=True)
    (experiment / "experiment_manifest.json").write_text(
        json.dumps({
            "analysis_case_id": "polymer_simple2d",
            "comparison_role": "scenario",
            "paired_experiment_id": "waterflood_baseline_v1",
            "data_nature": "OPM数值模拟数据",
            "case_count": 2,
            "status_counts": {"succeeded": 2},
        }),
        encoding="utf-8",
    )
    (experiment / "analysis" / "summary.json").write_text(
        json.dumps({
            "experiment_id": "sweep_a",
            "analysis_case_id": "polymer_simple2d",
            "data_nature": "OPM数值模拟数据",
            "figures": [{"name": "figure", "file": "figures/a.png"}],
            "report": "report.md",
            "waterflood_comparison": {
                "figures": [{"name": "increment", "file": "waterflood_comparison/figures/increment.png"}],
                "report": "waterflood_comparison/report.md",
                "paired_case_metrics": "waterflood_comparison/paired_case_metrics.csv",
                "paired_time_series": "waterflood_comparison/paired_time_series.csv",
            },
            "techno_economics": {
                "best_case_id": "case-1",
                "cases": [{"scenario_rank": 1, "polymer_case_id": "case-1"}],
                "case_economics": "techno_economics/case_economics.csv",
                "constraints": "techno_economics/constraint_evaluations.csv",
                "rankings": "techno_economics/scenario_rankings.csv",
                "report": "techno_economics/report.md",
                "ranking_report": "techno_economics/ranking_report.md",
                "explanation_chains": "techno_economics/explanation_chains.json",
            },
        }),
        encoding="utf-8",
    )
    (analysis / "a.png").write_bytes(b"png")
    comparison = experiment / "analysis" / "waterflood_comparison"
    (comparison / "figures").mkdir(parents=True)
    (comparison / "figures" / "increment.png").write_bytes(b"png")
    (comparison / "report.md").write_text("comparison", encoding="utf-8")
    (comparison / "paired_case_metrics.csv").write_text("a\n1\n", encoding="utf-8")
    (comparison / "paired_time_series.csv").write_text("a\n1\n", encoding="utf-8")
    (experiment / "analysis" / "report.md").write_text("report", encoding="utf-8")
    economics = experiment / "analysis" / "techno_economics"
    economics.mkdir()
    for name in ("case_economics.csv", "constraint_evaluations.csv", "scenario_rankings.csv"):
        (economics / name).write_text("a\n1\n", encoding="utf-8")
    (economics / "report.md").write_text("economics", encoding="utf-8")
    (economics / "ranking_report.md").write_text("ranking", encoding="utf-8")
    (economics / "summary.json").write_text(
        json.dumps({"case_count": 1, "best_case_id": "case-1"}), encoding="utf-8"
    )
    (economics / "explanation_chains.json").write_text(
        json.dumps({"model_id": "model-1", "cases": [{"case_id": "case-1", "observations": [], "rule_executions": [], "recommendation": {"decision": "候选"}}]}),
        encoding="utf-8",
    )


def test_experiment_summary_adds_download_urls(tmp_path: Path, monkeypatch) -> None:
    _write_experiment(tmp_path)
    monkeypatch.setattr(main, "EXPERIMENT_ROOT", tmp_path)

    listing = main.list_experiments()
    payload = main.get_experiment("sweep_a")

    assert listing[0]["analyzed"] is True
    assert listing[0]["analysis_case_id"] == "polymer_simple2d"
    assert listing[0]["paired_experiment_id"] == "waterflood_baseline_v1"
    assert payload["figures"][0]["url"].endswith("figures/a.png")
    assert payload["report_url"].endswith("report.md")
    comparison = payload["waterflood_comparison"]
    assert comparison["figures"][0]["url"].endswith("increment.png")
    assert comparison["paired_case_metrics_url"].endswith("paired_case_metrics.csv")
    economics = payload["techno_economics"]
    assert economics["rankings_url"].endswith("scenario_rankings.csv")
    assert economics["ranking_report_url"].endswith("ranking_report.md")
    assert economics["rankings_api_url"].endswith("techno-economic-rankings")

    ranking_payload = main.get_techno_economic_rankings("sweep_a")
    assert ranking_payload["case_count"] == 1
    assert ranking_payload["rows"] == [{"a": 1}]
    explanation = main.get_scenario_explanation("sweep_a", "case-1")
    assert explanation["model_id"] == "model-1"
    assert explanation["recommendation"]["decision"] == "候选"


def test_case_list_exposes_related_experiment(tmp_path: Path, monkeypatch) -> None:
    _write_experiment(tmp_path)
    monkeypatch.setattr(main, "EXPERIMENT_ROOT", tmp_path)

    cases = main.list_cases()
    polymer = next(item for item in cases if item["case_id"] == "polymer_simple2d")

    assert polymer["experiments"] == ["sweep_a"]


def test_experiment_file_rejects_parent_traversal(tmp_path: Path, monkeypatch) -> None:
    _write_experiment(tmp_path)
    monkeypatch.setattr(main, "EXPERIMENT_ROOT", tmp_path)

    with pytest.raises(HTTPException) as exc:
        main.get_experiment_file("sweep_a", "../experiment_manifest.json")

    assert exc.value.status_code == 404


def test_scenario_context_joins_metrics_rules_recommendation_and_graph(tmp_path: Path, monkeypatch) -> None:
    """方案工作台契约应保持领域无关，并用同一个 case_id 串起全部证据。"""
    _write_experiment(tmp_path)
    monkeypatch.setattr(main, "EXPERIMENT_ROOT", tmp_path)
    economics = tmp_path / "sweep_a" / "analysis" / "techno_economics"
    (economics / "scenario_rankings.csv").write_text(
        "scenario_rank,case_id,net_value,recommendation\n1,case-1,12.5,候选\n",
        encoding="utf-8",
    )
    (economics / "explanation_chains.json").write_text(
        json.dumps({
            "model_id": "model-1",
            "cases": [{
                "case_id": "case-1",
                "observations": [{
                    "observation_id": "o-1", "concept_id": "injection_rate",
                    "source_field": "injection_rate", "value": 100, "unit": "m3/day",
                }],
                "rule_executions": [{
                    "rule_execution_id": "r-1", "rule_id": "RULE-1", "passed": False,
                    "message": "超过约束",
                }],
                "recommendation": {
                    "recommendation_id": "rec-1", "decision": "需调整",
                    "justifying_execution_ids": ["r-1"],
                },
                "evidence": {"source_id": "source-1"},
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = main.get_scenario_context("sweep_a", "case-1")

    assert payload["contract_version"] == "scenario-context/v1"
    assert payload["scenario"]["net_value"] == 12.5
    assert payload["rankings"] == [{"scenario_rank": 1, "case_id": "case-1", "net_value": 12.5, "recommendation": "候选"}]
    assert payload["ranking_metadata"] == {"case_count": 1}
    assert payload["parameters"][0]["concept_id"] == "injection_rate"
    assert payload["rule_summary"] == {"total": 1, "passed": 0, "failed": 1}
    assert {node["type"] for node in payload["graph"]["nodes"]} == {
        "SimulationCase", "MetricObservation", "RuleExecution", "Recommendation", "Source",
    }
