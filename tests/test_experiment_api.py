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
        }),
        encoding="utf-8",
    )
    (analysis / "a.png").write_bytes(b"png")
    (experiment / "analysis" / "report.md").write_text("report", encoding="utf-8")


def test_experiment_summary_adds_download_urls(tmp_path: Path, monkeypatch) -> None:
    _write_experiment(tmp_path)
    monkeypatch.setattr(main, "EXPERIMENT_ROOT", tmp_path)

    listing = main.list_experiments()
    payload = main.get_experiment("sweep_a")

    assert listing[0]["analyzed"] is True
    assert listing[0]["analysis_case_id"] == "polymer_simple2d"
    assert payload["figures"][0]["url"].endswith("figures/a.png")
    assert payload["report_url"].endswith("report.md")


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
