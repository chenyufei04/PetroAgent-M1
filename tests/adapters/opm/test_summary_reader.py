"""验证 OPM Summary 字段识别、单位转换和标准 CSV 输出。"""

import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from petro_agent.adapters.opm import FlowExecutionConfig
from petro_agent.adapters.opm.summary_reader import (
    _run_native_bridge,
    convert_esmry,
    describe_vector,
)


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


def test_convert_esmry_reads_directly_in_native_mode(tmp_path: Path, monkeypatch):
    class FakeESmry:
        def __init__(self, source):
            assert source.endswith("CASE.ESMRY")

        def keys(self):
            return ["TIME", "FOPR"]

        def get(self, key):
            return {"TIME": [0, 1], "FOPR": [2, 1]}[key]

        def get_unit(self, key):
            return {"TIME": "DAYS", "FOPR": "SM3/DAY"}[key]

    opm = types.ModuleType("opm")
    opm_io = types.ModuleType("opm.io")
    opm_ecl = types.ModuleType("opm.io.ecl")
    opm_ecl.ESmry = FakeESmry
    monkeypatch.setitem(sys.modules, "opm", opm)
    monkeypatch.setitem(sys.modules, "opm.io", opm_io)
    monkeypatch.setitem(sys.modules, "opm.io.ecl", opm_ecl)
    source = tmp_path / "CASE.ESMRY"
    source.write_bytes(b"fake")

    result = convert_esmry(
        source,
        tmp_path / "converted",
        config=FlowExecutionConfig(execution_mode="native"),
    )

    assert pd.read_csv(result.standard_csv).to_dict("list") == {
        "time_days": [0.0, 1.0],
        "oil_rate_m3_day": [2.0, 1.0],
    }


def test_native_bridge_uses_system_python_outside_active_venv(tmp_path, monkeypatch):
    source = tmp_path / "CASE.ESMRY"
    source.write_bytes(b"fake")
    observed = {}

    def fake_run(command, **_):
        observed["command"] = command
        Path(command[-1]).write_text(
            json.dumps({"vectors": {"TIME": [0]}, "units": {}}),
            encoding="utf-8",
        )
        return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

    monkeypatch.setattr("petro_agent.adapters.opm.summary_reader.subprocess.run", fake_run)
    payload = _run_native_bridge(
        source,
        FlowExecutionConfig(execution_mode="native"),
        ImportError("opm unavailable in venv"),
    )

    assert observed["command"][0] == "/usr/bin/python3"
    assert payload["vectors"]["TIME"] == [0]
