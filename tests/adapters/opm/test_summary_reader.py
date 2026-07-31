import json
from pathlib import Path

import pandas as pd
import pytest

from petro_agent.adapters.opm.summary_reader import convert_esmry, describe_vector


def test_vector_description_preserves_object_and_unknown_vectors():
    well = describe_vector("WOPR:PROD1", "SM3/DAY")
    assert well.keyword == "WOPR"
    assert well.object_name == "PROD1"
    assert well.scope == "well"
    assert well.canonical_field == "well_oil_rate_m3_day"

    unknown = describe_vector("XUNKNOWN", "-")
    assert unknown.scope == "other"
    assert unknown.canonical_field is None


def test_convert_esmry_writes_standard_catalog_and_metadata(tmp_path: Path):
    source = tmp_path / "CASE.ESMRY"
    source.write_bytes(b"test boundary only")
    payload = {
        "vectors": {
            "TIME": [0.0, 10.0, 20.0],
            "FOPR": [2.0, 1.5, 1.0],
            "FWPR": [0.0, 0.5, 1.0],
            "WOPR:PROD1": [2.0, 1.5, 1.0],
            "XUNKNOWN": [7.0, 8.0, 9.0],
        },
        "units": {
            "TIME": "DAYS",
            "FOPR": "SM3/DAY",
            "FWPR": "SM3/DAY",
            "WOPR:PROD1": "SM3/DAY",
            "XUNKNOWN": "-",
        },
    }
    result = convert_esmry(
        source,
        tmp_path / "converted",
        case_id="case_a",
        payload_loader=lambda *_: payload,
    )
    frame = pd.read_csv(result.standard_csv)
    assert list(frame) == ["time_days", "oil_rate_m3_day", "water_rate_m3_day"]
    assert result.vector_count == 5
    assert result.mapped_vector_count == 3
    catalog = pd.read_csv(result.vector_catalog_csv)
    assert set(catalog["key"]) == set(payload["vectors"])
    metadata = json.loads(Path(result.metadata_json).read_text(encoding="utf-8"))
    assert metadata["source_vectors"]["oil_rate_m3_day"] == "FOPR"


def test_convert_rejects_mismatched_vector_lengths(tmp_path: Path):
    source = tmp_path / "CASE.ESMRY"
    source.write_bytes(b"test")
    with pytest.raises(ValueError, match="长度不一致"):
        convert_esmry(
            source,
            tmp_path / "converted",
            payload_loader=lambda *_: {
                "vectors": {"TIME": [0, 1], "FOPR": [1]},
                "units": {},
            },
        )
