"""验证技术经济结果能够形成指标、规则执行和推荐解释链。"""

import pandas as pd

from petro_agent.economics import build_semantic_explanations


def test_build_semantic_explanations_links_rules_concepts_and_evidence():
    rankings = pd.DataFrame([{
        "polymer_case_id": "case-1", "waterflood_case_id": "water-1",
        "polymer_concentration_kg_m3": 0.5, "injection_rate_m3_day": 200,
        "polymer_mass_kg": 1000, "peak_daily_polymer_kg_day": 100,
        "incremental_oil_m3": 10, "incremental_oil_m3_per_tonne_polymer": 10,
        "incremental_oil_revenue": 5000, "polymer_cost": 2500,
        "total_incremental_cost": 3000, "net_incremental_value": 2000,
        "scenario_rank": 1, "ranking_tier": 1, "recommendation": "优先候选",
        "economically_positive": True, "technically_feasible": True,
        "assumption_status": "illustrative_unvalidated",
    }])
    constraints = pd.DataFrame([
        {"polymer_case_id": "case-1", "constraint": name, "actual": 1, "limit": 2, "passed": True}
        for name in ("injector_bhp", "water_injection_rate", "water_production_rate", "daily_polymer", "total_polymer")
    ])

    result = build_semantic_explanations(rankings, constraints, "model-v1")

    assert len(result["metric_observations"]) == 9
    assert {item["rule_id"] for item in result["rule_executions"]} >= {"PF-DESIGN-003", "PF-ECO-002", "PF-RANK-001"}
    units = {item["rule_id"]: item["unit"] for item in result["rule_executions"]}
    assert units["PF-OPS-001"] == "bar"
    assert units["PF-OPS-004"] == "m3/day"
    assert units["PF-ECO-002"] == "USD"
    chain = result["explanation_chains"][0]
    assert chain["recommendation"]["decision"] == "优先候选"
    assert chain["evidence"]["source_id"] == "petroagent_techno_economic_model_v1"
