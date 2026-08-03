"""计算油藏生产时间序列的基础确定性指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def enrich_common_metrics(frame: pd.DataFrame, pore_volume_m3: float | None = None) -> pd.DataFrame:
    result = frame.copy()
    if {"oil_rate_m3_day", "water_rate_m3_day"} <= set(result.columns):
        total = result["oil_rate_m3_day"] + result["water_rate_m3_day"]
        result["water_cut_fraction"] = np.where(total > 0, result["water_rate_m3_day"] / total, np.nan)
    if "oil_rate_m3_day" in result and "time_days" in result and "cumulative_oil_m3" not in result:
        dt = result["time_days"].diff().fillna(0).clip(lower=0)
        result["cumulative_oil_m3"] = (result["oil_rate_m3_day"].clip(lower=0) * dt).cumsum()
    if pore_volume_m3 and "cumulative_injected_water_m3" in result:
        result["injected_pv"] = result["cumulative_injected_water_m3"] / pore_volume_m3
    return result


def summarize(frame: pd.DataFrame) -> dict:
    numeric = frame.select_dtypes(include="number")
    output: dict[str, object] = {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "missing_cells": int(frame.isna().sum().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
    }
    for column in numeric.columns:
        series = numeric[column].dropna()
        if not series.empty:
            output[column] = {
                "min": float(series.min()),
                "max": float(series.max()),
                "final": float(series.iloc[-1]),
            }
    return output
