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
