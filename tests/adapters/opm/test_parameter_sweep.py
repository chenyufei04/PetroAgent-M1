import json
from pathlib import Path

import pandas as pd
import pytest

from petro_agent.adapters.opm import (
    FlowRunResult,
    SummaryConversionResult,
    SweepCase,
    SweepParameter,
    build_cases,
    prepare_derived_deck,
    run_batch_experiment,
)


def test_cartesian_and_zip_case_designs():
    parameters = [
        SweepParameter("concentration", "{{C}}", (0.5, 1.0)),
        SweepParameter("rate", "{{R}}", (100, 200)),
    ]
    assert len(build_cases("test", parameters)) == 4
    assert len(build_cases("test", parameters, design="zip")) == 2
    with pytest.raises(ValueError, match="max_cases"):
        build_cases("test", parameters, max_cases=3)


def test_prepare_deck_replaces_tokens_and_preserves_source(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    deck = source_dir / "MODEL.DATA"
    include = source_dir / "schedule.inc"
    deck.write_text("INCLUDE\n'schedule.inc' /\nC={{C}}\n", encoding="utf-8")
    include.write_text("R={{R}}\n", encoding="utf-8")
    parameters = [
        SweepParameter("concentration", "{{C}}", (1.5,)),
        SweepParameter("rate", "{{R}}", (200,)),
    ]
    derived = prepare_derived_deck(
        deck,
        tmp_path / "derived",
        SweepCase("case-1", {"concentration": 1.5, "rate": 200}),
        parameters,
    )
    assert "C=1.5" in derived.read_text(encoding="utf-8")
    assert "R=200" in (derived.parent / "schedule.inc").read_text(encoding="utf-8")
    assert "{{C}}" in deck.read_text(encoding="utf-8")
    assert json.loads((derived.parent / "parameter_manifest.json").read_text())[
        "parameters"
    ]["rate"] == 200


def test_batch_experiment_builds_case_and_series_datasets(tmp_path: Path):
    project = tmp_path / "project"
    config_dir = project / "config" / "experiments"
    deck_dir = project / "data" / "case"
    config_dir.mkdir(parents=True)
    deck_dir.mkdir(parents=True)
    (deck_dir / "MODEL.DATA").write_text("VALUE={{VALUE}}\n", encoding="utf-8")
    config = config_dir / "sweep.yaml"
    config.write_text(
        """
experiment_id: smoke
base_deck: data/case/MODEL.DATA
output_root: outputs/experiments
parameters:
  value:
    token: "{{VALUE}}"
    values: [1, 2]
""",
        encoding="utf-8",
    )

    def fake_flow(deck_file, output_dir, **_):
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{Path(deck_file).stem}.ESMRY").write_bytes(b"fake")
        manifest = output / "run_manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        return FlowRunResult([], 0, "", "", str(manifest))

    def fake_convert(summary_file, output_dir, *, case_id, **_):
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        csv_file = output / f"{case_id}.csv"
        pd.DataFrame(
            {
                "time_days": [0, 10],
                "oil_rate_m3_day": [5, 4],
                "cumulative_oil_m3": [0, 45],
                "water_cut_fraction": [0.1, 0.2],
            }
        ).to_csv(csv_file, index=False)
        catalog = output / "vectors.csv"
        metadata = output / "metadata.json"
        catalog.write_text("key\nTIME\n", encoding="utf-8")
        metadata.write_text("{}", encoding="utf-8")
        return SummaryConversionResult(
            str(summary_file), str(csv_file), str(catalog), str(metadata), 2, 4, 4
        )

    result = run_batch_experiment(
        config, flow_runner=fake_flow, summary_converter=fake_convert
    )
    assert result.case_count == 2
    assert result.succeeded == 2
    cases = pd.read_csv(result.summary_csv)
    assert set(cases["status"]) == {"succeeded"}
    assert set(cases["final_cumulative_oil_m3"]) == {45.0}
    series = pd.read_csv(result.series_csv)
    assert len(series) == 4
    assert "parameter_value" in series
