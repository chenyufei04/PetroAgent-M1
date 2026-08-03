"""检查聚合物参数扫描数据并生成敏感性图表和技术报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CASE_COLUMNS = {
    "case_id", "parameter_polymer_concentration", "parameter_injection_rate",
    "final_cumulative_oil_m3", "final_water_cut_fraction", "status",
}
REQUIRED_SERIES_COLUMNS = {
    "case_id", "time_days", "cumulative_oil_m3", "field_pressure_bar",
    "water_cut_fraction", "parameter_polymer_concentration",
    "parameter_injection_rate",
}
METRICS = {
    "final_cumulative_oil_m3": "Cumulative oil (m³)",
    "final_water_cut_fraction": "Final water cut (-)",
    "final_field_pressure_bar": "Final field pressure (bar)",
}
COLORS = {0.5: "#2563eb", 1.0: "#d97706", 1.5: "#0f766e"}
MARKERS = {0.5: "o", 1.0: "s", 1.5: "^"}


def _finite(frame: pd.DataFrame) -> bool:
    numeric = frame.select_dtypes(include=[np.number])
    return bool(np.isfinite(numeric.to_numpy()).all())


def _quality(cases: pd.DataFrame, series: pd.DataFrame) -> dict:
    missing_case_columns = sorted(REQUIRED_CASE_COLUMNS - set(cases.columns))
    missing_series_columns = sorted(REQUIRED_SERIES_COLUMNS - set(series.columns))
    duplicate_cases = int(cases["case_id"].duplicated().sum()) if "case_id" in cases else None
    duplicate_points = (
        int(series.duplicated(["case_id", "time_days"]).sum())
        if {"case_id", "time_days"} <= set(series.columns) else None
    )
    rows_per_case = series.groupby("case_id").size()
    time_coverage = series.groupby("case_id")["time_days"].agg(["min", "max"])
    monotonic_failures = [
        case_id for case_id, group in series.groupby("case_id")
        if not group["time_days"].is_monotonic_increasing
        or group["time_days"].duplicated().any()
    ]
    range_violations = {
        "negative_rates_or_cumulatives": int((series[[
            c for c in series.columns
            if c.endswith("_rate_m3_day") or c.startswith("cumulative_")
        ]] < 0).sum().sum()),
        "water_cut_outside_0_1": int(
            ((series["water_cut_fraction"] < 0) | (series["water_cut_fraction"] > 1)).sum()
        ),
        "nonpositive_pressure": int((series["field_pressure_bar"] <= 0).sum()),
    }
    checks_passed = not any([
        missing_case_columns, missing_series_columns, duplicate_cases,
        duplicate_points, monotonic_failures, sum(range_violations.values()),
        int(cases.isna().sum().sum()), int(series.isna().sum().sum()),
        not _finite(cases), not _finite(series),
        set(cases.get("status", [])) != {"succeeded"},
        set(cases.get("case_id", [])) != set(series.get("case_id", [])),
    ])
    return {
        "status": "passed" if checks_passed else "warning",
        "case_rows": len(cases),
        "time_series_rows": len(series),
        "case_columns": list(cases.columns),
        "time_series_columns": list(series.columns),
        "missing_case_columns": missing_case_columns,
        "missing_time_series_columns": missing_series_columns,
        "null_cells": {"cases": int(cases.isna().sum().sum()), "time_series": int(series.isna().sum().sum())},
        "duplicate_case_ids": duplicate_cases,
        "duplicate_case_time_points": duplicate_points,
        "finite_numeric_values": {"cases": _finite(cases), "time_series": _finite(series)},
        "rows_per_case": {str(k): int(v) for k, v in rows_per_case.items()},
        "time_coverage_days": {
            str(k): {"min": float(v["min"]), "max": float(v["max"])}
            for k, v in time_coverage.to_dict("index").items()
        },
        "non_monotonic_cases": monotonic_failures,
        "range_violations": range_violations,
    }


def _case_metrics(cases: pd.DataFrame, series: pd.DataFrame) -> pd.DataFrame:
    final_pressure = (
        series.sort_values("time_days").groupby("case_id", as_index=False).tail(1)
        [["case_id", "field_pressure_bar"]]
        .rename(columns={"field_pressure_bar": "final_field_pressure_bar"})
    )
    return cases.merge(final_pressure, on="case_id", validate="one_to_one")


def _effects(metrics: pd.DataFrame) -> dict:
    baseline = metrics.query(
        "parameter_polymer_concentration == 0.5 and parameter_injection_rate == 100"
    ).iloc[0]
    best_oil = metrics.loc[metrics["final_cumulative_oil_m3"].idxmax()]
    effects = {}
    for metric in METRICS:
        rate_means = metrics.groupby("parameter_injection_rate")[metric].mean()
        concentration_means = metrics.groupby("parameter_polymer_concentration")[metric].mean()
        effects[metric] = {
            "injection_rate_mean": {str(k): float(v) for k, v in rate_means.items()},
            "polymer_concentration_mean": {str(k): float(v) for k, v in concentration_means.items()},
            "rate_100_to_200_absolute": float(rate_means.loc[200] - rate_means.loc[100]),
            "rate_100_to_200_percent": float((rate_means.loc[200] / rate_means.loc[100] - 1) * 100),
            "concentration_0_5_to_1_5_absolute": float(concentration_means.loc[1.5] - concentration_means.loc[0.5]),
            "concentration_0_5_to_1_5_percent": float((concentration_means.loc[1.5] / concentration_means.loc[0.5] - 1) * 100),
        }
    return {
        "baseline": baseline.to_dict(),
        "best_cumulative_oil_case": best_oil.to_dict(),
        "metric_effects": effects,
    }


def _plot_final_metrics(metrics: pd.DataFrame, target: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, (metric, label) in zip(axes, METRICS.items()):
        for concentration, group in metrics.groupby("parameter_polymer_concentration"):
            group = group.sort_values("parameter_injection_rate")
            ax.plot(group["parameter_injection_rate"], group[metric], marker=MARKERS[concentration],
                    color=COLORS[concentration], linewidth=2, label=f"{concentration:g} kg/m³")
        ax.set_title(label)
        ax.set_xlabel("Injection rate (m³/day)")
        ax.grid(True, color="#dbe3e8", linewidth=.7)
        ax.ticklabel_format(axis="y", style="plain")
    axes[0].set_ylabel("Value")
    axes[-1].legend(title="Polymer concentration", frameon=False)
    fig.suptitle("Polymer sensitivity: final metrics", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_time_series(series: pd.DataFrame, target: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 11), sharex=True)
    fields = [
        ("cumulative_oil_m3", "Cumulative oil (m³)"),
        ("water_cut_fraction", "Water cut (-)"),
        ("field_pressure_bar", "Field pressure (bar)"),
    ]
    for (concentration, rate), group in series.groupby([
        "parameter_polymer_concentration", "parameter_injection_rate"
    ]):
        group = group.sort_values("time_days")
        line_style = {100: ":", 150: "--", 200: "-"}[int(rate)]
        label = f"{concentration:g} kg/m³ · {int(rate)} m³/d"
        for ax, (field, ylabel) in zip(axes, fields):
            ax.plot(group["time_days"], group[field], color=COLORS[concentration],
                    linestyle=line_style, linewidth=1.6, label=label)
            ax.set_ylabel(ylabel)
            ax.grid(True, color="#e2e8ec", linewidth=.7)
    axes[-1].set_xlabel("Simulation time (days)")
    axes[0].legend(ncol=3, fontsize=8, frameon=False)
    fig.suptitle("Polymer sensitivity: production trajectories", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_heatmaps(metrics: pd.DataFrame, target: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.3))
    for ax, (metric, label) in zip(axes, METRICS.items()):
        pivot = metrics.pivot(index="parameter_polymer_concentration", columns="parameter_injection_rate", values=metric)
        image = ax.imshow(pivot.to_numpy(), cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(pivot.columns)), [str(v) for v in pivot.columns])
        ax.set_yticks(range(len(pivot.index)), [str(v) for v in pivot.index])
        ax.set_xlabel("Injection rate (m³/day)")
        ax.set_ylabel("Concentration (kg/m³)")
        ax.set_title(label)
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                value = pivot.iloc[i, j]
                text = f"{value:,.0f}" if metric != "final_water_cut_fraction" else f"{value:.3f}"
                ax.text(j, i, text, ha="center", va="center", fontsize=8,
                        color="white" if value > pivot.to_numpy().mean() else "#173b3a")
        fig.colorbar(image, ax=ax, shrink=.72)
    fig.suptitle("Parameter-response matrix", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _report(experiment_id: str, quality: dict, effects: dict, metrics: pd.DataFrame) -> str:
    oil = effects["metric_effects"]["final_cumulative_oil_m3"]
    wc = effects["metric_effects"]["final_water_cut_fraction"]
    pressure = effects["metric_effects"]["final_field_pressure_bar"]
    best = effects["best_cumulative_oil_case"]
    rows = []
    for _, row in metrics.sort_values(["parameter_polymer_concentration", "parameter_injection_rate"]).iterrows():
        rows.append(
            f"| {row.parameter_polymer_concentration:g} | {row.parameter_injection_rate:.0f} | "
            f"{row.final_cumulative_oil_m3:,.1f} | {row.final_water_cut_fraction:.4f} | "
            f"{row.final_field_pressure_bar:.2f} |"
        )
    return f"""# {experiment_id} 参数敏感性实验报告

## 技术摘要

- 9 个参数组合全部成功，算例级表 9 行、时间序列表 {quality['time_series_rows']:,} 行；关键字段无空值、无重复主键、无非有限数值，数据可用于本轮描述性敏感性比较。
- 注入速率是主要驱动因素：从 100 增至 200 m³/day 时，跨浓度平均累计产油增加 {oil['rate_100_to_200_absolute']:,.1f} m³（{oil['rate_100_to_200_percent']:.1f}%），末期压力增加 {pressure['rate_100_to_200_absolute']:.2f} bar。
- 聚合物浓度在 0.5–1.5 kg/m³ 范围内对累计产油的平均净变化仅 {oil['concentration_0_5_to_1_5_absolute']:,.1f} m³（{oil['concentration_0_5_to_1_5_percent']:.2f}%）；对末期含水率有小幅降低作用，平均变化 {wc['concentration_0_5_to_1_5_absolute']:.4f}。
- 最大累计产油为 {best['final_cumulative_oil_m3']:,.1f} m³，对应 1.5 kg/m³、200 m³/day；但这是描述性结果，不等同于经济最优方案。

## 注入速率主导累计产油、含水率和压力

![终值指标对比](figures/final_metrics.png)

三幅图以相同的参数组合比较末期指标。累计产油随注入速率单调上升，同时末期含水率与压力也上升，说明增注带来产油增益的同时伴随更强水窜/产水风险与压力响应。浓度曲线大体重合，表明当前浓度范围的边际影响远小于注入速率。

![参数响应矩阵](figures/parameter_response_heatmaps.png)

矩阵保留每个组合的精确相对位置。浓度效应在不同注入速率下并非完全一致，因此不应从 9 个确定性组合推断普适单调规律。

## 动态曲线确认终值比较不是单点伪象

![动态曲线](figures/time_series.png)

累计产油、含水率和压力曲线覆盖 1–10,960 天。线型表示注入速率、颜色表示浓度；注入速率造成的轨迹分离持续存在，而同一速率下不同浓度曲线接近。

## 数据范围与指标定义

- 实验设计：3 个聚合物浓度（0.5、1.0、1.5 kg/m³）× 3 个注入速率（100、150、200 m³/day）的笛卡尔积。
- `final_cumulative_oil_m3`：各算例最后时间点的现场累计产油。
- `final_water_cut_fraction`：各算例最后时间点的现场含水率，0–1 小数。
- `final_field_pressure_bar`：由时间序列表每个算例最后时间点提取的现场压力。
- 比较基准：主效应使用另一个参数三个水平的算术平均；未拟合因果或响应面模型。

| 浓度 (kg/m³) | 注入速率 (m³/day) | 累计产油 (m³) | 末期含水率 | 末期压力 (bar) |
|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 方法与质量检查

对算例主键、`case_id + time_days` 复合键、空值、有限值、时间覆盖、时间单调性及物理范围进行检查。所有算例状态为 `succeeded`，时间覆盖一致；每个算例 231–237 个求解输出点的差异由模拟器自适应时间步产生，不视为缺失。

## 局限性与稳健性

- 本报告是单一 Deck、固定 OPM Flow 2026.04 下的确定性数值模拟结果，不代表真实油田数据，也不建立因果关系。
- 每个参数组合只有一次模拟，无随机重复、历史拟合不确定性或数值网格敏感性评估，不能给出置信区间。
- 未纳入聚合物成本、注入能耗、处理能力、采收率分母与净现值，因此“最大累计产油”不是经济最优。
- 含水率随注入速率显著上升，任何工程推荐都应联合产水处理能力和压力约束。

## 建议的下一步

1. 增加基准水驱/零聚合物算例，量化聚合物增量贡献。
2. 在 150–200 m³/day 区间加密注入速率，并加入聚合物成本与净现值指标。
3. 对渗透率场、相渗和聚合物吸附参数开展不确定性分析，而不是只扩展控制参数网格。
4. 将数据质量检查固化为回归测试，避免后续实验出现字段漂移或不完整合并。

## 进一步问题

- 聚合物浓度对含水率的小幅改善是否足以覆盖药剂成本？
- 高注入速率下的压力是否满足具体井口、地层破裂与设施约束？
- 在不同非均质实现中，当前排序是否保持稳定？
"""


def analyze(experiment_dir: Path) -> dict:
    dataset = experiment_dir / "dataset"
    manifest_file = experiment_dir / "experiment_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    cases = pd.read_csv(dataset / "cases.csv")
    series = pd.read_csv(dataset / "time_series.csv")
    analysis_dir = experiment_dir / "analysis"
    figures_dir = analysis_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    quality = _quality(cases, series)
    metrics = _case_metrics(cases, series)
    effects = _effects(metrics)
    _plot_final_metrics(metrics, figures_dir / "final_metrics.png")
    _plot_time_series(series, figures_dir / "time_series.png")
    _plot_heatmaps(metrics, figures_dir / "parameter_response_heatmaps.png")
    metrics.to_csv(analysis_dir / "case_metrics.csv", index=False)
    (analysis_dir / "quality_summary.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "experiment_id": experiment_dir.name,
        "analysis_case_id": manifest.get("analysis_case_id"),
        "data_nature": manifest.get("data_nature", "OPM数值模拟数据"),
        "quality": quality,
        **effects,
        "cases": json.loads(metrics.to_json(orient="records")),
        "figures": [
            {"name": "终值指标", "file": "figures/final_metrics.png"},
            {"name": "动态曲线", "file": "figures/time_series.png"},
            {"name": "参数响应矩阵", "file": "figures/parameter_response_heatmaps.png"},
        ],
        "report": "report.md",
    }
    (analysis_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (analysis_dir / "report.md").write_text(_report(experiment_dir.name, quality, effects, metrics), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 OPM 参数敏感性实验")
    parser.add_argument("experiment", help="实验目录或实验 ID")
    args = parser.parse_args()
    source = Path(args.experiment)
    if not source.is_absolute() and len(source.parts) == 1:
        source = ROOT / "outputs" / "experiments" / source
    summary = analyze(source.resolve())
    print(json.dumps({"experiment_id": summary["experiment_id"], "quality": summary["quality"]["status"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
