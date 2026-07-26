from pathlib import Path

from petro_agent.pipeline import analyze_csv


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    result = analyze_csv(
        ROOT / "data/demo/polymer_simple2d_demo.csv",
        ROOT / "config/cases/polymer_simple2d.yaml",
        ROOT / "outputs",
    )
    print(f"完成: {result.dataset.case_id}; 校验规则 {len(result.findings)} 条")

