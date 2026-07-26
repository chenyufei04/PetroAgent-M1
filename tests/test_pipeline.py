from pathlib import Path

from petro_agent.pipeline import analyze_csv


ROOT = Path(__file__).resolve().parents[1]


def test_demo_pipeline(tmp_path):
    result = analyze_csv(
        ROOT / "data/demo/polymer_simple2d_demo.csv",
        ROOT / "config/cases/polymer_simple2d.yaml",
        tmp_path,
    )
    assert result.dataset.case_id == "polymer_simple2d_demo"
    assert (tmp_path / "reports/polymer_simple2d_demo.md").exists()
    assert (tmp_path / "runs/polymer_simple2d_demo_canonical.csv").exists()
    assert all(item.passed for item in result.findings if item.severity == "error")

