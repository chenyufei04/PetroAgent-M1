from __future__ import annotations

import numpy as np

from petro_agent.core.models import CanonicalDataset, ValidationFinding


def validate_common(dataset: CanonicalDataset) -> list[ValidationFinding]:
    frame = dataset.frame
    findings: list[ValidationFinding] = []
    findings.append(ValidationFinding(
        "DATA_NOT_EMPTY", "error", not frame.empty,
        "数据集包含记录" if not frame.empty else "数据集为空",
        len(frame),
    ))
    if "time_days" in frame:
        monotonic = bool(frame["time_days"].dropna().is_monotonic_increasing)
        findings.append(ValidationFinding(
            "TIME_MONOTONIC", "error", monotonic,
            "时间序列单调不减" if monotonic else "时间序列存在倒序",
        ))
    for column in ("oil_rate_m3_day", "water_rate_m3_day", "polymer_concentration_kg_m3"):
        if column in frame:
            valid = bool((frame[column].dropna() >= 0).all())
            findings.append(ValidationFinding(
                f"{column.upper()}_NONNEGATIVE", "error", valid,
                f"{column} 非负" if valid else f"{column} 存在负值",
                float(frame[column].min()) if len(frame[column].dropna()) else None,
            ))
    if "water_cut_fraction" in frame:
        series = frame["water_cut_fraction"].dropna()
        valid = bool(((series >= 0) & (series <= 1)).all())
        findings.append(ValidationFinding(
            "WATER_CUT_BOUNDS", "error", valid,
            "含水率位于 [0, 1]" if valid else "含水率超出 [0, 1]",
        ))
    if "recovery_factor_fraction" in frame:
        series = frame["recovery_factor_fraction"].dropna()
        bounded = bool(((series >= 0) & (series <= 1 + 1e-9)).all())
        monotonic = bool(np.all(np.diff(series.to_numpy()) >= -1e-8))
        findings.extend([
            ValidationFinding("RECOVERY_BOUNDS", "error", bounded, "采收率位于 [0, 1]" if bounded else "采收率越界"),
            ValidationFinding("RECOVERY_MONOTONIC", "warning", monotonic, "累计采收率单调不减" if monotonic else "累计采收率出现下降"),
        ])
    return findings

