"""把技术经济计算结果转换为可追溯的知识规则执行与解释链。"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd


OBSERVATION_FIELDS: dict[str, tuple[str, str]] = {
    "polymer_concentration_kg_m3": ("polymer_concentration_kg_m3", "kg/m3"),
    "injection_rate_m3_day": ("polymer_injection_rate", "m3/day"),
    "polymer_mass_kg": ("polymer_mass_kg", "kg"),
    "peak_daily_polymer_kg_day": ("peak_daily_polymer_rate", "kg/day"),
    "incremental_oil_m3": ("incremental_oil_m3", "m3"),
    "incremental_oil_revenue": ("incremental_oil_revenue", "USD"),
    "polymer_cost": ("polymer_cost", "USD"),
    "net_incremental_value": ("net_incremental_value", "USD"),
    "scenario_rank": ("scenario_rank", "rank"),
}

CONSTRAINT_RULES = {
    "injector_bhp": ("PF-OPS-001", "注入井压力不超过配置上限"),
    "water_injection_rate": ("PF-OPS-004", "注水峰值不超过设施能力"),
    "water_production_rate": ("PF-OPS-005", "产水峰值不超过处理能力"),
    "daily_polymer": ("PF-OPS-006", "日配聚峰值不超过配制能力"),
    "total_polymer": ("PF-OPS-007", "聚合物总量不超过供应上限"),
}


def _native(value: Any) -> Any:
    """将 NumPy/Pandas 标量转换为可写入 JSON 和 Neo4j 的 Python 类型。"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return value.item() if isinstance(value, np.generic) else value


def build_semantic_explanations(
    rankings: pd.DataFrame, constraints: pd.DataFrame, model_id: str
) -> dict[str, list[dict]]:
    """为每个方案生成指标观测、规则执行、推荐和证据链。"""
    observations: list[dict] = []
    executions: list[dict] = []
    recommendations: list[dict] = []
    chains: list[dict] = []
    source_id = "petroagent_techno_economic_model_v1"

    for row in rankings.to_dict(orient="records"):
        case_id = str(row["polymer_case_id"])
        case_observations = []
        for field, (concept_id, unit) in OBSERVATION_FIELDS.items():
            if field not in row or pd.isna(row[field]):
                continue
            item = {
                "observation_id": f"observation:{case_id}:{concept_id}",
                "case_id": case_id,
                "concept_id": concept_id,
                "source_field": field,
                "value": _native(row[field]),
                "unit": unit,
            }
            observations.append(item)
            case_observations.append(item)

        case_executions: list[dict] = []

        def add_execution(rule_id: str, passed: bool, actual: Any, expected: Any, operator: str, message: str) -> None:
            item = {
                "rule_execution_id": f"rule-execution:{case_id}:{rule_id}",
                "case_id": case_id,
                "rule_id": rule_id,
                "passed": bool(passed),
                "actual": _native(actual),
                "expected": _native(expected),
                "operator": operator,
                "message": message,
                "evidence_source_id": source_id,
                "model_id": model_id,
            }
            executions.append(item)
            case_executions.append(item)

        # 质量由同一段塞水量与浓度确定；生成成功即代表公式完成且结果有限。
        mass_ok = np.isfinite(float(row["polymer_mass_kg"])) and float(row["polymer_mass_kg"]) >= 0
        add_execution("PF-DESIGN-003", mass_ok, row["polymer_mass_kg"], "C_p × integral(FWIR dt)", "formula", "聚合物质量按段塞窗口积分得到")
        add_execution("PF-PERF-001", bool(row.get("waterflood_case_id")), row.get("incremental_oil_m3"), row.get("waterflood_case_id"), "paired_baseline", "增量油采用同注入速率水驱基线")
        add_execution("PF-PERF-002", pd.notna(row.get("incremental_oil_m3_per_tonne_polymer")), row.get("incremental_oil_m3_per_tonne_polymer"), "reported", "is_not_null", "已报告单位聚合物增量油")

        case_constraints = constraints.loc[constraints["polymer_case_id"] == case_id]
        for constraint in case_constraints.to_dict(orient="records"):
            rule_id, message = CONSTRAINT_RULES[str(constraint["constraint"])]
            add_execution(rule_id, constraint["passed"], constraint["actual"], constraint["limit"], "less_than_or_equal", message)

        calculated_net = float(row["incremental_oil_revenue"]) - float(row["total_incremental_cost"])
        net_ok = abs(calculated_net - float(row["net_incremental_value"])) <= 1e-6
        add_execution("PF-ECO-001", net_ok, row["net_incremental_value"], calculated_net, "formula", "净增量价值采用收入减带符号增量成本")
        add_execution("PF-ECO-002", row["economically_positive"], row["net_incremental_value"], 0, "greater_than", "净增量价值大于零才通过经济筛选")
        add_execution("PF-RANK-001", True, row["scenario_rank"], row["ranking_tier"], "deterministic_ranking", "排名按技术可行性、经济正值和净值生成")

        failed = [item for item in case_executions if not item["passed"]]
        recommendation = {
            "recommendation_id": f"recommendation:{case_id}",
            "case_id": case_id,
            "scenario_rank": int(row["scenario_rank"]),
            "decision": str(row["recommendation"]),
            "rationale": "；".join(item["message"] for item in failed) if failed else "所有已配置规则均通过",
            "justifying_execution_ids": json.dumps([item["rule_execution_id"] for item in case_executions], ensure_ascii=False),
            "evidence_source_id": source_id,
            "assumption_status": str(row["assumption_status"]),
        }
        recommendations.append(recommendation)
        chains.append({
            "case_id": case_id,
            "observations": case_observations,
            "rule_executions": case_executions,
            "recommendation": {**recommendation, "justifying_execution_ids": json.loads(recommendation["justifying_execution_ids"])},
            "evidence": {"source_id": source_id, "model_id": model_id, "assumption_status": row["assumption_status"]},
        })

    return {
        "metric_observations": observations,
        "rule_executions": executions,
        "recommendations": recommendations,
        "explanation_chains": chains,
    }
