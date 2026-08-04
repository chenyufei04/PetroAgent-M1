"""聚合物质量衡算、增量经济性和设施约束的可复用算法。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml


@dataclass(frozen=True)
class EconomicAssumptions:
    """保存带明确单位的经济与工程假设，避免在公式中隐藏常数。"""

    model_id: str
    assumption_status: str
    currency: str
    barrels_per_m3: float
    slug_start_day: float
    slug_end_day: float
    oil_price_per_bbl: float
    polymer_price_per_kg: float
    injection_water_cost_per_m3: float
    produced_water_cost_per_m3: float
    injector_bhp_field: str
    max_injector_bhp_bar: float
    max_water_injection_rate_m3_day: float
    max_water_production_rate_m3_day: float
    max_daily_polymer_kg: float
    max_total_polymer_kg: float


# 多领域适配说明：本模块的段塞、药剂质量和配聚约束属于聚合物驱专用算法。
# 接入气驱、热采、人工举升、压裂或钻井时应新建领域模块，并复用结果契约而非改写这些公式。


@dataclass(frozen=True)
class ConstraintEvaluation:
    """一条可审计的约束判断；margin 大于等于零表示满足约束。"""

    constraint: str
    actual: float
    limit: float
    unit: str
    margin: float
    passed: bool


def load_economic_assumptions(path: str | Path) -> EconomicAssumptions:
    """读取并校验经济 YAML；所有价格和上限均要求非负。"""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    prices = payload["prices"]
    slug = payload["polymer_slug"]
    constraints = payload["constraints"]
    values = EconomicAssumptions(
        model_id=str(payload["model_id"]),
        assumption_status=str(payload["assumption_status"]),
        currency=str(payload["currency"]),
        barrels_per_m3=float(payload["conversion"]["barrels_per_m3"]),
        slug_start_day=float(slug["start_day"]),
        slug_end_day=float(slug["end_day"]),
        oil_price_per_bbl=float(prices["oil_per_bbl"]),
        polymer_price_per_kg=float(prices["polymer_per_kg"]),
        injection_water_cost_per_m3=float(prices["injection_water_per_m3"]),
        produced_water_cost_per_m3=float(prices["produced_water_per_m3"]),
        injector_bhp_field=str(constraints["injector_bhp_field"]),
        max_injector_bhp_bar=float(constraints["max_injector_bhp_bar"]),
        max_water_injection_rate_m3_day=float(constraints["max_water_injection_rate_m3_day"]),
        max_water_production_rate_m3_day=float(constraints["max_water_production_rate_m3_day"]),
        max_daily_polymer_kg=float(constraints["max_daily_polymer_kg"]),
        max_total_polymer_kg=float(constraints["max_total_polymer_kg"]),
    )
    numeric = [value for key, value in vars(values).items() if isinstance(value, float)]
    if any(value < 0 or not np.isfinite(value) for value in numeric):
        raise ValueError("经济参数和工程上限必须是非负有限数")
    if values.slug_end_day <= values.slug_start_day:
        raise ValueError("聚合物段结束时间必须晚于开始时间")
    return values


def _series_with_boundaries(
    frame: pd.DataFrame, value_field: str, start_day: float, end_day: float
) -> tuple[np.ndarray, np.ndarray]:
    """在线性插值后裁剪时间窗，使梯形积分严格落在段塞起止边界。"""
    ordered = frame[["time_days", value_field]].dropna().sort_values("time_days")
    if ordered["time_days"].duplicated().any():
        raise ValueError("质量衡算时间序列存在重复时间点")
    times = ordered["time_days"].to_numpy(dtype=float)
    values = ordered[value_field].to_numpy(dtype=float)
    if len(times) < 2 or start_day < times[0] or end_day > times[-1]:
        raise ValueError("质量衡算时间序列不能覆盖完整聚合物段塞")
    inside = (times > start_day) & (times < end_day)
    clipped_times = np.concatenate(([start_day], times[inside], [end_day]))
    clipped_values = np.interp(clipped_times, times, values)
    return clipped_times, clipped_values


def integrate_polymer_slug(
    frame: pd.DataFrame,
    concentration_kg_m3: float,
    start_day: float,
    end_day: float,
    rate_field: str = "water_injection_rate_m3_day",
) -> dict[str, float]:
    """按实际注入率积分段塞水量，再乘浓度得到聚合物质量。"""
    if concentration_kg_m3 < 0:
        raise ValueError("聚合物浓度不能为负")
    times, rates = _series_with_boundaries(frame, rate_field, start_day, end_day)
    # OPM 的水注入率单位为 m3/day，时间单位为 day，梯形积分结果自然为 m3。
    injected_water_m3 = float(np.trapezoid(rates, times))
    polymer_mass_kg = injected_water_m3 * concentration_kg_m3
    return {
        "polymer_slug_start_day": start_day,
        "polymer_slug_end_day": end_day,
        "polymer_slug_duration_days": end_day - start_day,
        "polymer_slug_injected_water_m3": injected_water_m3,
        "polymer_concentration_kg_m3": concentration_kg_m3,
        "polymer_mass_kg": polymer_mass_kg,
        "polymer_mass_tonnes": polymer_mass_kg / 1000.0,
        "peak_daily_polymer_kg_day": float(np.max(rates) * concentration_kg_m3),
    }


def calculate_incremental_economics(
    paired_row: Mapping[str, Any], mass: Mapping[str, float], config: EconomicAssumptions
) -> dict[str, float | bool | None]:
    """采用“聚合物驱减同速率水驱”的符号约定计算未折现增量价值。"""
    delta_oil_m3 = float(paired_row["incremental_cumulative_oil_m3"])
    delta_injected_m3 = float(paired_row["incremental_cumulative_injected_water_m3"])
    delta_water_m3 = float(paired_row["incremental_cumulative_water_m3"])
    delta_oil_bbl = delta_oil_m3 * config.barrels_per_m3
    revenue = delta_oil_bbl * config.oil_price_per_bbl
    polymer_cost = mass["polymer_mass_kg"] * config.polymer_price_per_kg
    injection_cost = delta_injected_m3 * config.injection_water_cost_per_m3
    water_cost = delta_water_m3 * config.produced_water_cost_per_m3
    # 增量产水为负代表处理费节省，因此按带符号成本直接从收入中扣除。
    total_cost = polymer_cost + injection_cost + water_cost
    net_value = revenue - total_cost
    mass_kg = mass["polymer_mass_kg"]
    break_even_polymer = (
        (revenue - injection_cost - water_cost) / mass_kg if mass_kg > 0 else None
    )
    break_even_oil = total_cost / delta_oil_bbl if delta_oil_bbl > 0 else None
    return {
        "incremental_oil_m3": delta_oil_m3,
        "incremental_oil_bbl": delta_oil_bbl,
        "incremental_oil_revenue": revenue,
        "polymer_cost": polymer_cost,
        "incremental_injection_water_cost": injection_cost,
        "incremental_produced_water_cost": water_cost,
        "total_incremental_cost": total_cost,
        "net_incremental_value": net_value,
        "economically_positive": net_value > 0,
        "break_even_polymer_price_per_kg": break_even_polymer,
        "break_even_oil_price_per_bbl": break_even_oil,
        "incremental_oil_m3_per_tonne_polymer": (
            delta_oil_m3 / (mass_kg / 1000.0) if mass_kg > 0 else None
        ),
    }


def evaluate_constraints(
    series: pd.DataFrame, mass: Mapping[str, float], config: EconomicAssumptions
) -> list[ConstraintEvaluation]:
    """同时检查压力、注采设施能力和聚合物配注能力。"""
    required = {
        config.injector_bhp_field,
        "water_injection_rate_m3_day",
        "water_rate_m3_day",
    }
    missing = sorted(required.difference(series.columns))
    if missing:
        raise ValueError(f"约束计算缺少标准字段: {', '.join(missing)}")
    specs = [
        ("injector_bhp", float(series[config.injector_bhp_field].max()), config.max_injector_bhp_bar, "bar"),
        ("water_injection_rate", float(series["water_injection_rate_m3_day"].max()), config.max_water_injection_rate_m3_day, "m3/day"),
        ("water_production_rate", float(series["water_rate_m3_day"].max()), config.max_water_production_rate_m3_day, "m3/day"),
        ("daily_polymer", mass["peak_daily_polymer_kg_day"], config.max_daily_polymer_kg, "kg/day"),
        ("total_polymer", mass["polymer_mass_kg"], config.max_total_polymer_kg, "kg"),
    ]
    results = []
    for name, actual, limit, unit in specs:
        # 所有设施约束均采用“实际值 <= 上限”，因此余量统一定义为上限减实际值。
        margin = limit - actual
        results.append(ConstraintEvaluation(name, actual, limit, unit, margin, margin >= -1e-9))
    return results


def rank_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    """按技术可行性、经济正值和净增量价值生成确定性方案排名。"""
    required = {
        "polymer_case_id", "technically_feasible", "economically_positive",
        "net_incremental_value", "incremental_oil_m3",
        "polymer_concentration_kg_m3", "injection_rate_m3_day",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"方案排名缺少字段: {', '.join(missing)}")
    ranked = frame.copy()
    # 第一层优先保留技术可行且经济为正的方案；不可行方案无论净值多高都排在最后。
    ranked["ranking_tier"] = np.select(
        [
            ranked["technically_feasible"] & ranked["economically_positive"],
            ranked["technically_feasible"],
        ],
        [1, 2],
        default=3,
    )
    ranked["recommendation"] = np.select(
        [ranked["ranking_tier"] == 1, ranked["ranking_tier"] == 2],
        ["优先候选", "技术可行但经济未通过"],
        default="约束不通过",
    )
    # 同层内先比较净增量价值，再比较增量油；参数值作为稳定的最终排序键。
    ranked = ranked.sort_values(
        [
            "ranking_tier", "net_incremental_value", "incremental_oil_m3",
            "polymer_concentration_kg_m3", "injection_rate_m3_day",
        ],
        ascending=[True, False, False, True, True],
        kind="stable",
    ).reset_index(drop=True)
    ranked.insert(0, "scenario_rank", np.arange(1, len(ranked) + 1))
    return ranked
