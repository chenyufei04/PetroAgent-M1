from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd

from .deck_runner import FlowExecutionConfig, windows_path_to_wsl


@dataclass(frozen=True)
class SummaryVector:
    key: str
    keyword: str
    object_name: str | None
    scope: str
    unit: str
    canonical_field: str | None


@dataclass(frozen=True)
class SummaryConversionResult:
    summary_file: str
    standard_csv: str
    vector_catalog_csv: str
    metadata_json: str
    row_count: int
    vector_count: int
    mapped_vector_count: int


FIELD_MAPPINGS: dict[str, tuple[str, str]] = {
    "TIME": ("time_days", "day"),
    "FOPR": ("oil_rate_m3_day", "m3/day"),
    "FWPR": ("water_rate_m3_day", "m3/day"),
    "FGPR": ("gas_rate_m3_day", "m3/day"),
    "FOPT": ("cumulative_oil_m3", "m3"),
    "FWPT": ("cumulative_water_m3", "m3"),
    "FGPT": ("cumulative_gas_m3", "m3"),
    "FWIR": ("water_injection_rate_m3_day", "m3/day"),
    "FWIT": ("cumulative_injected_water_m3", "m3"),
    "FWCT": ("water_cut_fraction", "fraction"),
    "FPR": ("field_pressure_bar", "bar"),
}

WELL_MAPPINGS: dict[str, tuple[str, str]] = {
    "WOPR": ("well_oil_rate_m3_day", "m3/day"),
    "WWPR": ("well_water_rate_m3_day", "m3/day"),
    "WGPR": ("well_gas_rate_m3_day", "m3/day"),
    "WWIR": ("well_water_injection_rate_m3_day", "m3/day"),
    "WBHP": ("well_bhp_bar", "bar"),
    "WWCT": ("well_water_cut_fraction", "fraction"),
}


def _split_key(key: str) -> tuple[str, str | None]:
    parts = key.split(":", 1)
    return parts[0].upper(), parts[1] if len(parts) == 2 else None


def describe_vector(key: str, unit: str) -> SummaryVector:
    keyword, object_name = _split_key(key)
    if keyword in FIELD_MAPPINGS:
        canonical = FIELD_MAPPINGS[keyword][0]
        scope = "field"
    elif keyword in WELL_MAPPINGS:
        canonical = WELL_MAPPINGS[keyword][0]
        scope = "well"
    else:
        canonical = None
        scope = (
            "well" if keyword.startswith("W")
            else "group" if keyword.startswith("G")
            else "region" if keyword.startswith("R")
            else "field" if keyword.startswith("F")
            else "other"
        )
    return SummaryVector(key, keyword, object_name, scope, unit, canonical)


def _bridge_source() -> str:
    """Return a self-contained script executed by OPM's Linux Python."""
    return r'''
import json
import sys

from opm.io.ecl import ESmry

source, target = sys.argv[1], sys.argv[2]
summary = ESmry(source)

def value_or_call(obj, names, *args):
    for name in names:
        if not hasattr(obj, name):
            continue
        value = getattr(obj, name)
        try:
            return value(*args) if callable(value) else value
        except (TypeError, KeyError, RuntimeError):
            continue
    raise AttributeError("No supported ESmry API member: " + ", ".join(names))

keys = list(value_or_call(summary, ("keys", "keywordList", "summaryKeys")))
vectors = {}
units = {}
for key in keys:
    key = str(key)
    values = value_or_call(summary, ("get", "get_vector", "__getitem__"), key)
    vectors[key] = [float(item) for item in values]
    try:
        units[key] = str(value_or_call(summary, ("get_unit", "unit", "getUnit"), key))
    except AttributeError:
        units[key] = ""

with open(target, "w", encoding="utf-8") as handle:
    json.dump({"vectors": vectors, "units": units}, handle, ensure_ascii=False)
'''


def _run_wsl_bridge(
    summary_file: Path,
    config: FlowExecutionConfig,
) -> dict[str, Any]:
    if config.execution_mode != "wsl":
        raise ValueError("ESMRY 读取当前要求 OPM_EXECUTION_MODE=wsl")
    with tempfile.TemporaryDirectory(prefix="petro-agent-esmry-") as temp_dir:
        bridge = Path(temp_dir) / "read_esmry.py"
        payload = Path(temp_dir) / "summary.json"
        bridge.write_text(_bridge_source(), encoding="utf-8")
        command = [
            "wsl.exe",
            "-d",
            config.wsl_distribution,
            "--",
            "python3",
            windows_path_to_wsl(bridge),
            windows_path_to_wsl(summary_file),
            windows_path_to_wsl(payload),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=config.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(
                "OPM ESMRY 读取失败。请确认 WSL 的 python3 可以导入 "
                f"opm.io.ecl.ESmry。详情：{detail}"
            )
        return json.loads(payload.read_text(encoding="utf-8"))


def _validate_payload(payload: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, str]]:
    vectors = payload.get("vectors")
    units = payload.get("units", {})
    if not isinstance(vectors, dict) or not vectors:
        raise ValueError("ESMRY 未返回任何 Summary 向量")
    lengths = {len(values) for values in vectors.values()}
    if len(lengths) != 1:
        raise ValueError(f"Summary 向量长度不一致：{sorted(lengths)}")
    return vectors, {str(key): str(value) for key, value in units.items()}


def convert_esmry(
    summary_file: str | Path,
    output_dir: str | Path,
    *,
    case_id: str | None = None,
    config: FlowExecutionConfig | None = None,
    payload_loader: Callable[[Path, FlowExecutionConfig], dict[str, Any]] | None = None,
) -> SummaryConversionResult:
    source = Path(summary_file).resolve()
    if not source.is_file() or source.suffix.upper() != ".ESMRY":
        raise ValueError(f"ESMRY 文件不存在或扩展名错误：{source}")
    cfg = config or FlowExecutionConfig.from_environment()
    payload = (payload_loader or _run_wsl_bridge)(source, cfg)
    vectors, units = _validate_payload(payload)
    descriptions = [describe_vector(key, units.get(key, "")) for key in vectors]

    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    resolved_case_id = case_id or source.stem.lower()
    frame = pd.DataFrame()
    canonical_units: dict[str, str] = {}
    source_vectors: dict[str, str] = {}
    for item in descriptions:
        if item.scope != "field" or not item.canonical_field:
            continue
        frame[item.canonical_field] = vectors[item.key]
        canonical_units[item.canonical_field] = FIELD_MAPPINGS[item.keyword][1]
        source_vectors[item.canonical_field] = item.key
    if "time_days" not in frame:
        raise ValueError("ESMRY 中缺少 TIME 向量，无法生成标准时间序列")

    standard_csv = target / f"{resolved_case_id}_summary_standard.csv"
    catalog_csv = target / f"{resolved_case_id}_summary_vectors.csv"
    metadata_json = target / f"{resolved_case_id}_summary_metadata.json"
    frame.to_csv(standard_csv, index=False)
    pd.DataFrame([asdict(item) for item in descriptions]).to_csv(catalog_csv, index=False)
    metadata_json.write_text(
        json.dumps(
            {
                "case_id": resolved_case_id,
                "source_type": "opm_flow_esmry",
                "summary_file": str(source),
                "row_count": len(frame),
                "vector_count": len(descriptions),
                "mapped_vector_count": len(source_vectors),
                "source_vectors": source_vectors,
                "source_units": units,
                "canonical_units": canonical_units,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return SummaryConversionResult(
        str(source),
        str(standard_csv),
        str(catalog_csv),
        str(metadata_json),
        len(frame),
        len(descriptions),
        len(source_vectors),
    )

