"""验证质量积分、增量经济符号和工程约束边界。"""

from pathlib import Path

import pandas as pd

from petro_agent.economics import (
    calculate_incremental_economics,
    evaluate_constraints,
    integrate_polymer_slug,
    load_economic_assumptions,
    rank_scenarios,
)


CONFIG = Path("config/economics/polymer_economics.yaml")


def test_polymer_mass_uses_only_slug_window_and_interpolated_boundaries():
    frame = pd.DataFrame({"time_days": [0, 500, 2000, 3000], "water_injection_rate_m3_day": [100, 100, 100, 100]})
    result = integrate_polymer_slug(frame, 1.5, 460, 2110)
    assert result["polymer_slug_injected_water_m3"] == 165000
    assert result["polymer_mass_kg"] == 247500
    assert result["peak_daily_polymer_kg_day"] == 150


def test_incremental_economics_preserves_signed_water_savings():
    config = load_economic_assumptions(CONFIG)
    result = calculate_incremental_economics(
        {"incremental_cumulative_oil_m3": 100, "incremental_cumulative_injected_water_m3": 0, "incremental_cumulative_water_m3": -10},
        {"polymer_mass_kg": 1000},
        config,
    )
    assert result["incremental_produced_water_cost"] == -5
    assert result["net_incremental_value"] == result["incremental_oil_revenue"] - 2495


def test_constraints_include_pressure_and_facility_limits():
    config = load_economic_assumptions(CONFIG)
    series = pd.DataFrame({
        "inje01_well_bhp_bar": [370, 381],
        "water_injection_rate_m3_day": [100, 200],
        "water_rate_m3_day": [20, 90],
    })
    results = evaluate_constraints(series, {"peak_daily_polymer_kg_day": 300, "polymer_mass_kg": 495000}, config)
    by_name = {item.constraint: item for item in results}
    assert not by_name["injector_bhp"].passed
    assert by_name["water_injection_rate"].passed
    assert by_name["daily_polymer"].passed


def test_rank_scenarios_prioritizes_feasibility_then_net_value():
    frame = pd.DataFrame([
        {"polymer_case_id": "infeasible", "technically_feasible": False, "economically_positive": True, "net_incremental_value": 1000, "incremental_oil_m3": 20, "polymer_concentration_kg_m3": 1.0, "injection_rate_m3_day": 100},
        {"polymer_case_id": "feasible_low", "technically_feasible": True, "economically_positive": False, "net_incremental_value": -20, "incremental_oil_m3": 10, "polymer_concentration_kg_m3": 1.0, "injection_rate_m3_day": 100},
        {"polymer_case_id": "feasible_high", "technically_feasible": True, "economically_positive": False, "net_incremental_value": -10, "incremental_oil_m3": 5, "polymer_concentration_kg_m3": 0.5, "injection_rate_m3_day": 100},
    ])
    ranked = rank_scenarios(frame)
    assert ranked["polymer_case_id"].tolist() == ["feasible_high", "feasible_low", "infeasible"]
    assert ranked["scenario_rank"].tolist() == [1, 2, 3]
