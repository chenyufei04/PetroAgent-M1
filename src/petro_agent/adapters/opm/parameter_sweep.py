from __future__ import annotations

import hashlib
import itertools
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd
import yaml

from .deck_runner import FlowExecutionConfig, FlowRunResult, run_flow
from .summary_reader import SummaryConversionResult, convert_esmry


_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")
_DEFAULT_DECK_SUFFIXES = {
    ".DATA", ".INC", ".SCH", ".GRDECL", ".PROPS", ".SCHEDULE", ".TXT"
}


@dataclass(frozen=True)
class SweepParameter:
    name: str
    token: str
    values: tuple[float | int | str, ...]
    unit: str = ""
    file_glob: str = "**/*"
    format_spec: str = "g"


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    parameters: dict[str, float | int | str]


@dataclass(frozen=True)
class BatchExperimentResult:
    experiment_id: str
    experiment_dir: str
    case_count: int
    succeeded: int
    failed: int
    prepared: int
    summary_csv: str
    series_csv: str | None
    manifest_json: str


def _safe_identifier(value: str) -> str:
    result = _SAFE_ID.sub("-", value.strip()).strip("-._")
    if not result:
        raise ValueError("标识不能为空或只包含特殊字符")
    return result


def load_experiment_config(config_file: str | Path) -> dict[str, Any]:
    source = Path(config_file).resolve()
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("实验配置必须是 YAML 对象")
    raw["_config_file"] = str(source)
    return raw


def parse_parameters(raw: Mapping[str, Any]) -> list[SweepParameter]:
    parameters: list[SweepParameter] = []
    for name, item in raw.items():
        if not isinstance(item, Mapping):
            raise ValueError(f"参数 {name} 必须是对象")
        values = item.get("values")
        token = str(item.get("token", "")).strip()
        if not isinstance(values, list) or not values:
            raise ValueError(f"参数 {name} 的 values 必须是非空列表")
        if not token:
            raise ValueError(f"参数 {name} 缺少 token")
        parameters.append(
            SweepParameter(
                name=str(name),
                token=token,
                values=tuple(values),
                unit=str(item.get("unit", "")),
                file_glob=str(item.get("file_glob", "**/*")),
                format_spec=str(item.get("format", "g")),
            )
        )
    if not parameters:
        raise ValueError("实验配置至少需要一个参数")
    tokens = [item.token for item in parameters]
    if len(tokens) != len(set(tokens)):
        raise ValueError("每个参数必须使用不同的 token")
    return parameters


def build_cases(
    experiment_id: str,
    parameters: Sequence[SweepParameter],
    *,
    design: str = "cartesian",
    max_cases: int = 1000,
) -> list[SweepCase]:
    if design not in {"cartesian", "zip"}:
        raise ValueError("design 只能是 cartesian 或 zip")
    if max_cases <= 0:
        raise ValueError("max_cases 必须大于 0")
    value_sets = [item.values for item in parameters]
    if design == "zip":
        lengths = {len(values) for values in value_sets}
        if len(lengths) != 1:
            raise ValueError("zip 设计要求所有参数的 values 数量相同")
        combinations = zip(*value_sets)
    else:
        combinations = itertools.product(*value_sets)
    cases: list[SweepCase] = []
    for index, values in enumerate(combinations, start=1):
        if index > max_cases:
            raise ValueError(f"组合数量超过 max_cases={max_cases}")
        payload = dict(zip((item.name for item in parameters), values))
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:8]
        cases.append(SweepCase(f"{_safe_identifier(experiment_id)}-{index:04d}-{digest}", payload))
    return cases


def _format_value(value: float | int | str, format_spec: str) -> str:
    if isinstance(value, bool):
        raise ValueError("Deck 参数值不能是布尔值")
    if isinstance(value, (int, float)):
        return format(value, format_spec)
    return str(value)


def prepare_derived_deck(
    base_deck: str | Path,
    target_dir: str | Path,
    case: SweepCase,
    parameters: Sequence[SweepParameter],
) -> Path:
    source = Path(base_deck).resolve()
    if not source.is_file() or source.suffix.upper() != ".DATA":
        raise ValueError(f"基础 Deck 不存在或不是 .DATA 文件：{source}")
    target = Path(target_dir).resolve()
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source.parent, target)
    replaced: dict[str, int] = {item.name: 0 for item in parameters}
    for parameter in parameters:
        replacement = _format_value(case.parameters[parameter.name], parameter.format_spec)
        for path in target.glob(parameter.file_glob):
            if not path.is_file() or path.suffix.upper() not in _DEFAULT_DECK_SUFFIXES:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            count = content.count(parameter.token)
            if count:
                path.write_text(content.replace(parameter.token, replacement), encoding="utf-8")
                replaced[parameter.name] += count
    missing = [name for name, count in replaced.items() if count == 0]
    if missing:
        shutil.rmtree(target)
        raise ValueError(f"基础 Deck 中未找到参数占位符：{', '.join(missing)}")
    derived = target / source.name
    provenance = {
        "case_id": case.case_id,
        "base_deck": str(source),
        "derived_deck": str(derived),
        "parameters": case.parameters,
        "replacements": replaced,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (target / "parameter_manifest.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return derived


def _find_esmry(output_dir: Path, deck_stem: str) -> Path:
    preferred = output_dir / f"{deck_stem}.ESMRY"
    if preferred.is_file():
        return preferred
    matches = sorted(output_dir.glob("*.ESMRY"))
    if len(matches) != 1:
        raise RuntimeError(f"无法唯一确定 ESMRY 文件，找到 {len(matches)} 个")
    return matches[0]


def _labels(frame: pd.DataFrame) -> dict[str, float | int | None]:
    def final(column: str) -> float | None:
        return float(frame[column].iloc[-1]) if column in frame and len(frame) else None

    def maximum(column: str) -> float | None:
        return float(frame[column].max()) if column in frame and len(frame) else None

    def average(column: str) -> float | None:
        return float(frame[column].mean()) if column in frame and len(frame) else None

    return {
        "time_steps": int(len(frame)),
        "simulation_days": final("time_days"),
        "final_cumulative_oil_m3": final("cumulative_oil_m3"),
        "final_cumulative_water_m3": final("cumulative_water_m3"),
        "final_cumulative_injected_water_m3": final("cumulative_injected_water_m3"),
        "final_water_cut_fraction": final("water_cut_fraction"),
        "peak_oil_rate_m3_day": maximum("oil_rate_m3_day"),
        "mean_oil_rate_m3_day": average("oil_rate_m3_day"),
    }


def run_batch_experiment(
    config_file: str | Path,
    *,
    prepare_only: bool = False,
    resume: bool = True,
    flow_config: FlowExecutionConfig | None = None,
    flow_runner: Callable[..., FlowRunResult] = run_flow,
    summary_converter: Callable[..., SummaryConversionResult] = convert_esmry,
) -> BatchExperimentResult:
    config = load_experiment_config(config_file)
    config_path = Path(config["_config_file"])
    project_root = config_path.parents[2] if len(config_path.parents) >= 3 else config_path.parent
    experiment_id = _safe_identifier(str(config.get("experiment_id", config_path.stem)))
    base_deck = Path(str(config.get("base_deck", "")))
    if not base_deck.is_absolute():
        base_deck = (project_root / base_deck).resolve()
    output_root = Path(str(config.get("output_root", "outputs/experiments")))
    if not output_root.is_absolute():
        output_root = (project_root / output_root).resolve()
    experiment_dir = output_root / experiment_id
    cases_dir = experiment_dir / "cases"
    derived_root = experiment_dir / "derived_decks"
    dataset_dir = experiment_dir / "dataset"
    for directory in (cases_dir, derived_root, dataset_dir):
        directory.mkdir(parents=True, exist_ok=True)

    parameters = parse_parameters(config.get("parameters", {}))
    cases = build_cases(
        experiment_id,
        parameters,
        design=str(config.get("design", "cartesian")),
        max_cases=int(config.get("max_cases", 1000)),
    )
    extra_args = tuple(str(value) for value in config.get("flow_args", []))
    rows: list[dict[str, Any]] = []
    series_frames: list[pd.DataFrame] = []
    case_manifests: list[dict[str, Any]] = []

    for case in cases:
        case_dir = cases_dir / case.case_id
        manifest_file = case_dir / "case_manifest.json"
        if resume and not prepare_only and manifest_file.is_file():
            cached = json.loads(manifest_file.read_text(encoding="utf-8"))
            if cached.get("status") == "succeeded":
                rows.append(cached["dataset_row"])
                standard_csv = Path(cached["conversion"]["standard_csv"])
                if standard_csv.is_file():
                    frame = pd.read_csv(standard_csv)
                    frame.insert(0, "case_id", case.case_id)
                    for name, value in case.parameters.items():
                        frame[f"parameter_{name}"] = value
                    series_frames.append(frame)
                case_manifests.append(cached)
                continue

        case_dir.mkdir(parents=True, exist_ok=True)
        row: dict[str, Any] = {"case_id": case.case_id, **{
            f"parameter_{name}": value for name, value in case.parameters.items()
        }}
        manifest: dict[str, Any] = {
            "case_id": case.case_id,
            "parameters": case.parameters,
            "status": "preparing",
        }
        try:
            derived = prepare_derived_deck(
                base_deck, derived_root / case.case_id, case, parameters
            )
            manifest["derived_deck"] = str(derived)
            if prepare_only:
                row["status"] = "prepared"
                manifest["status"] = "prepared"
            else:
                run_result = flow_runner(
                    derived,
                    case_dir / "flow",
                    config=flow_config,
                    extra_args=extra_args,
                )
                manifest["flow"] = asdict(run_result)
                if run_result.return_code != 0:
                    raise RuntimeError(f"Flow 退出码为 {run_result.return_code}")
                esmry = _find_esmry(case_dir / "flow", derived.stem)
                conversion = summary_converter(
                    esmry, case_dir / "converted", case_id=case.case_id,
                    config=flow_config,
                )
                manifest["conversion"] = asdict(conversion)
                frame = pd.read_csv(conversion.standard_csv)
                labels = _labels(frame)
                row.update(labels)
                row["status"] = "succeeded"
                row["deck_file"] = str(derived)
                row["summary_file"] = str(esmry)
                row["standard_csv"] = conversion.standard_csv
                manifest["labels"] = labels
                manifest["status"] = "succeeded"
                frame.insert(0, "case_id", case.case_id)
                for name, value in case.parameters.items():
                    frame[f"parameter_{name}"] = value
                series_frames.append(frame)
        except Exception as exc:  # one failed case must not abort the experiment
            row["status"] = "failed"
            row["error"] = str(exc)
            manifest["status"] = "failed"
            manifest["error"] = str(exc)
        manifest["dataset_row"] = row
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest_file.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows.append(row)
        case_manifests.append(manifest)

    summary_csv = dataset_dir / "cases.csv"
    pd.DataFrame(rows).to_csv(summary_csv, index=False)
    series_csv: Path | None = None
    if series_frames:
        series_csv = dataset_dir / "time_series.csv"
        pd.concat(series_frames, ignore_index=True).to_csv(series_csv, index=False)
    counts = pd.Series([row["status"] for row in rows]).value_counts().to_dict()
    manifest_json = experiment_dir / "experiment_manifest.json"
    manifest_json.write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "data_nature": "OPM数值模拟数据",
                "config_file": str(config_path),
                "base_deck": str(base_deck),
                "design": config.get("design", "cartesian"),
                "case_count": len(cases),
                "status_counts": counts,
                "parameter_units": {item.name: item.unit for item in parameters},
                "summary_csv": str(summary_csv),
                "series_csv": str(series_csv) if series_csv else None,
                "cases": [
                    str(cases_dir / case.case_id / "case_manifest.json") for case in cases
                ],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return BatchExperimentResult(
        experiment_id,
        str(experiment_dir),
        len(cases),
        int(counts.get("succeeded", 0)),
        int(counts.get("failed", 0)),
        int(counts.get("prepared", 0)),
        str(summary_csv),
        str(series_csv) if series_csv else None,
        str(manifest_json),
    )
