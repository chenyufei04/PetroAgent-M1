from pathlib import Path

import pandas as pd

from petro_agent.api.serializers import serialize_result
from petro_agent.core.models import (
    AnalysisResult,
    CanonicalDataset,
    SourceInfo,
    ValidationFinding,
)


def test_serialize_result_builds_web_contract(tmp_path: Path):
    dataset = CanonicalDataset(
        case_id="demo",
        domain="reservoir_engineering",
        process="polymer_flooding",
        frame=pd.DataFrame({"time_days": [0, 1]}),
        units={"time_days": "day"},
        source=SourceInfo("demo", "test"),
        metadata={"rule_execution": {"mode": "knowledge"}},
    )
    result = AnalysisResult(
        dataset=dataset,
        summary={"oil_rate": {"mean": 10}},
        findings=[
            ValidationFinding(
                rule_id="PF_TEST",
                severity="warning",
                passed=False,
                message="测试风险",
                observed=12,
                concept_id="oil_rate",
                source_id="SOURCE_TEST",
            )
        ],
        figures=[],
    )

    payload = serialize_result(result, tmp_path)

    assert payload["summary"]["total_rules"] == 1
    assert payload["summary"]["failed_rules"] == 1
    assert payload["summary"]["warnings"] == 1
    assert payload["concept_ids"] == ["oil_rate"]
    assert payload["results"][0]["source_id"] == "SOURCE_TEST"
    assert any(item["type"] == "json" for item in payload["output_files"])
