"""生成聚合物质量、简单增量经济和工程约束数据集。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from petro_agent.economics import (
    build_semantic_explanations,
    calculate_incremental_economics,
    evaluate_constraints,
    integrate_polymer_slug,
    load_economic_assumptions,
    rank_scenarios,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "economics" / "polymer_economics.yaml"
DEFAULT_PAIRED = ROOT / "outputs" / "experiments" / "polymer_sensitivity_v1" / "analysis" / "waterflood_comparison" / "paired_case_metrics.csv"
DEFAULT_SERIES = ROOT / "outputs" / "experiments" / "polymer_sensitivity_v1" / "dataset" / "time_series.csv"
DEFAULT_OUTPUT = ROOT / "outputs" / "experiments" / "polymer_sensitivity_v1" / "analysis" / "techno_economics"


def _markdown_table(frame: pd.DataFrame) -> str:
    """不引入额外依赖，把小型结果表转换为 Markdown。"""
    headers = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for values in frame.itertuples(index=False, name=None):
        cells = [f"{value:.3f}" if isinstance(value, float) else str(value) for value in values]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run(config_path: Path, paired_path: Path, series_path: Path, output: Path) -> dict:
    """按 case_id 汇合增量终值与动态序列，并写出宽表、约束长表及报告。"""
    config = load_economic_assumptions(config_path)
    paired = pd.read_csv(paired_path)
    series = pd.read_csv(series_path)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    constraint_rows: list[dict] = []
    for _, pair in paired.iterrows():
        case_id = str(pair["polymer_case_id"])
        case_series = series.loc[series["case_id"] == case_id].copy()
        if case_series.empty:
            raise ValueError(f"缺少聚合物算例时间序列: {case_id}")
        mass = integrate_polymer_slug(
            case_series,
            float(pair["parameter_polymer_concentration"]),
            config.slug_start_day,
            config.slug_end_day,
        )
        economics = calculate_incremental_economics(pair, mass, config)
        constraints = evaluate_constraints(case_series, mass, config)
        failed = [item.constraint for item in constraints if not item.passed]
        rows.append({
            "polymer_case_id": case_id,
            "waterflood_case_id": pair["waterflood_case_id"],
            "injection_rate_m3_day": pair["parameter_injection_rate"],
            **mass,
            **economics,
            "constraint_violation_count": len(failed),
            "technically_feasible": not failed,
            "constraint_violations": ";".join(failed),
            "assumption_status": config.assumption_status,
            "currency": config.currency,
        })
        for item in constraints:
            constraint_rows.append({"polymer_case_id": case_id, **asdict(item)})

    result = pd.DataFrame(rows).sort_values(["injection_rate_m3_day", "polymer_concentration_kg_m3"])
    constraint_frame = pd.DataFrame(constraint_rows)
    rankings = rank_scenarios(result)
    result.to_csv(output / "case_economics.csv", index=False)
    constraint_frame.to_csv(output / "constraint_evaluations.csv", index=False)
    rankings.to_csv(output / "scenario_rankings.csv", index=False)
    semantic = build_semantic_explanations(rankings, constraint_frame, config.model_id)
    pd.DataFrame(semantic["metric_observations"]).to_csv(output / "metric_observations.csv", index=False)
    pd.DataFrame(semantic["rule_executions"]).to_csv(output / "rule_executions.csv", index=False)
    pd.DataFrame(semantic["recommendations"]).to_csv(output / "recommendations.csv", index=False)
    (output / "explanation_chains.json").write_text(
        json.dumps({"model_id": config.model_id, "cases": semantic["explanation_chains"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = {
        "model_id": config.model_id,
        "assumption_status": config.assumption_status,
        "case_count": len(result),
        "technically_feasible": int(result["technically_feasible"].sum()),
        "economically_positive": int(result["economically_positive"].sum()),
        "best_case_id": rankings.iloc[0]["polymer_case_id"],
        "ranking_policy": "技术可行且经济为正优先，其次按净增量价值和增量油降序",
        "config_file": str(config_path),
        "rule_execution_count": len(semantic["rule_executions"]),
        "metric_observation_count": len(semantic["metric_observations"]),
        "recommendation_count": len(semantic["recommendations"]),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    table = _markdown_table(result[["polymer_concentration_kg_m3", "injection_rate_m3_day", "polymer_mass_tonnes", "incremental_oil_m3", "net_incremental_value", "technically_feasible", "constraint_violations"]])
    report = f"""# 聚合物质量、增量经济与约束报告

> 假设状态：`{config.assumption_status}`。价格和设施上限是演示值，不能直接用于投资决策。

## 计算思路

1. 在 Deck 的第 {config.slug_start_day:g}–{config.slug_end_day:g} 天聚合物段内，对实际 `FWIR` 做边界插值和梯形积分，得到段塞注水量；再乘浓度得到聚合物质量。
2. 增量经济统一按“聚合物驱减同注入速率水驱”：增量油收入减聚合物、增量注水和增量产水处理成本；当前为未折现筛选模型。
3. 压力、注水、产水、日配聚量和总用量均按实际峰值/累计值与 YAML 上限比较，余量为“上限减实际”。

## 汇总

- 算例：{len(result)}；技术约束通过：{summary['technically_feasible']}；示例价格下经济为正：{summary['economically_positive']}。
- 净增量价值最优算例：`{summary['best_case_id']}`。

{table}

## 适用边界

尚未计入折现、税费、聚合物配制站 CAPEX、注入泵功耗、剪切降解、吸附损失和价格不确定性。下一步应以现场破裂压力、设施能力和商务报价替换示例 YAML。
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    ranking_table = _markdown_table(rankings[[
        "scenario_rank", "polymer_case_id", "polymer_concentration_kg_m3",
        "injection_rate_m3_day", "incremental_oil_m3", "net_incremental_value",
        "technically_feasible", "economically_positive", "recommendation",
    ]])
    ranking_report = f"""# 聚合物方案技术经济排名

> 假设状态：`{config.assumption_status}`。本排名是示例价格和设施上限下的确定性筛选，不是投资决策结论。

## 排名规则

1. 技术可行且经济为正的方案属于第一层；技术可行但净值不为正属于第二层；违反任一设施约束属于第三层。
2. 同层内依次按净增量价值、增量油降序排列。
3. 若仍相同，按聚合物浓度和注入速率升序排列，保证重复执行得到稳定名次。

## 排名结果

{ranking_table}

## 使用限制

排名依赖 `{config.model_id}` 的未验证示例价格与约束。正式推荐前必须补充折现现金流、CAPEX、能耗、税费和不确定性分析。
"""
    (output / "ranking_report.md").write_text(ranking_report, encoding="utf-8")

    # 把技术经济摘要登记到父级实验摘要，使 FastAPI/Vue 沿用现有实验详情接口。
    parent_summary_path = output.parent / "summary.json"
    if parent_summary_path.is_file():
        parent_summary = json.loads(parent_summary_path.read_text(encoding="utf-8"))
        parent_summary["techno_economics"] = {
            **summary,
            "cases": rankings.to_dict(orient="records"),
            "case_economics": "techno_economics/case_economics.csv",
            "constraints": "techno_economics/constraint_evaluations.csv",
            "rankings": "techno_economics/scenario_rankings.csv",
            "report": "techno_economics/report.md",
            "ranking_report": "techno_economics/ranking_report.md",
            "metric_observations": "techno_economics/metric_observations.csv",
            "rule_executions": "techno_economics/rule_executions.csv",
            "recommendations": "techno_economics/recommendations.csv",
            "explanation_chains": "techno_economics/explanation_chains.json",
        }
        parent_summary_path.write_text(
            json.dumps(parent_summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--paired", type=Path, default=DEFAULT_PAIRED)
    parser.add_argument("--series", type=Path, default=DEFAULT_SERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.paired, args.series, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
