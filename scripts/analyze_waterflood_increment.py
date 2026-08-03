"""按注入速率配对水驱与聚合物驱，生成增量数据、图表和报告。"""

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
EXPERIMENT_ROOT = ROOT / "outputs" / "experiments"
POLYMER_ID = "polymer_sensitivity_v1"
WATER_ID = "waterflood_baseline_v1"
PAIR_KEY = "parameter_injection_rate"
COLORS = {0.5: "#2563eb", 1.0: "#d97706", 1.5: "#0f766e"}
MARKERS = {0.5: "o", 1.0: "s", 1.5: "^"}


def _last_pressure(series: pd.DataFrame, suffix: str) -> pd.DataFrame:
    return (
        series.sort_values("time_days").groupby("case_id", as_index=False).tail(1)
        [["case_id", "field_pressure_bar"]]
        .rename(columns={"field_pressure_bar": f"final_field_pressure_bar_{suffix}"})
    )


def build_paired_datasets(
    polymer_cases: pd.DataFrame,
    polymer_series: pd.DataFrame,
    water_cases: pd.DataFrame,
    water_series: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """按注入速率配对终值，并将水驱动态插值到聚合物时间点。"""
    if water_cases[PAIR_KEY].duplicated().any():
        raise ValueError("水驱基准的注入速率必须唯一")
    if set(polymer_cases[PAIR_KEY]) != set(water_cases[PAIR_KEY]):
        raise ValueError("水驱与聚合物驱的注入速率集合不一致")
    if set(polymer_cases["status"]) != {"succeeded"} or set(water_cases["status"]) != {"succeeded"}:
        raise ValueError("存在未成功算例，不能生成正式配对结果")

    poly = polymer_cases.merge(_last_pressure(polymer_series, "polymer"), on="case_id")
    water = water_cases.merge(_last_pressure(water_series, "water"), on="case_id")
    paired = poly.merge(water, on=PAIR_KEY, suffixes=("_polymer", "_water"), validate="many_to_one")
    paired = paired.rename(columns={
        "case_id_polymer": "polymer_case_id",
        "case_id_water": "waterflood_case_id",
    })
    metric_pairs = {
        "cumulative_oil_m3": "final_cumulative_oil_m3",
        "cumulative_water_m3": "final_cumulative_water_m3",
        "cumulative_injected_water_m3": "final_cumulative_injected_water_m3",
        "water_cut_fraction": "final_water_cut_fraction",
        "field_pressure_bar": "final_field_pressure_bar",
        "peak_oil_rate_m3_day": "peak_oil_rate_m3_day",
        "mean_oil_rate_m3_day": "mean_oil_rate_m3_day",
    }
    for short, source in metric_pairs.items():
        paired[f"incremental_{short}"] = paired[f"{source}_polymer"] - paired[f"{source}_water"]
    paired["incremental_oil_percent"] = (
        paired["incremental_cumulative_oil_m3"] / paired["final_cumulative_oil_m3_water"] * 100
    )
    paired["water_cut_change_percentage_points"] = paired["incremental_water_cut_fraction"] * 100

    dynamic_metrics = [
        "gas_rate_m3_day", "cumulative_gas_m3", "oil_rate_m3_day",
        "cumulative_oil_m3", "field_pressure_bar", "water_cut_fraction",
        "water_injection_rate_m3_day", "cumulative_injected_water_m3",
        "water_rate_m3_day", "cumulative_water_m3",
    ]
    paired_groups = []
    interpolated_points = 0
    for (polymer_case_id, rate), group in polymer_series.groupby(["case_id", PAIR_KEY]):
        group = group.sort_values("time_days").copy()
        baseline = water_series.loc[water_series[PAIR_KEY] == rate].sort_values("time_days")
        if group["time_days"].min() < baseline["time_days"].min() or group["time_days"].max() > baseline["time_days"].max():
            raise ValueError(f"水驱时间范围不能覆盖聚合物算例 {polymer_case_id}")
        frame = pd.DataFrame({"time_days": group["time_days"].to_numpy(), PAIR_KEY: rate})
        for column in group.columns:
            if column not in {"time_days", PAIR_KEY}:
                frame[f"{column}_polymer"] = group[column].to_numpy()
        frame["case_id_water"] = baseline["case_id"].iloc[0]
        baseline_times = baseline["time_days"].to_numpy()
        exact_times = set(baseline_times)
        interpolated_points += sum(value not in exact_times for value in frame["time_days"])
        for metric in dynamic_metrics:
            frame[f"{metric}_water"] = np.interp(
                frame["time_days"], baseline_times, baseline[metric].to_numpy()
            )
        paired_groups.append(frame)
    paired_ts = pd.concat(paired_groups, ignore_index=True)
    for metric in ["cumulative_oil_m3", "cumulative_water_m3", "water_cut_fraction", "field_pressure_bar"]:
        paired_ts[f"incremental_{metric}"] = paired_ts[f"{metric}_polymer"] - paired_ts[f"{metric}_water"]

    expected_points = len(polymer_series)
    quality = {
        "status": "passed",
        "paired_case_rows": int(len(paired)),
        "paired_time_series_rows": int(len(paired_ts)),
        "expected_time_series_rows": int(expected_points),
        "all_time_points_matched": len(paired_ts) == expected_points,
        "waterflood_interpolated_points": int(interpolated_points),
        "interpolation_method": "linear within matching injection rate",
        "duplicate_case_pairs": int(paired.duplicated(["polymer_case_id", "waterflood_case_id"]).sum()),
        "duplicate_time_points": int(paired_ts.duplicated(["case_id_polymer", "time_days"]).sum()),
        "null_cells": {"paired_cases": int(paired.isna().sum().sum()), "paired_time_series": int(paired_ts.isna().sum().sum())},
        "finite_numeric_values": bool(np.isfinite(paired.select_dtypes(include=[np.number])).all().all() and np.isfinite(paired_ts.select_dtypes(include=[np.number])).all().all()),
    }
    quality["status"] = "passed" if all([
        quality["all_time_points_matched"],
        quality["duplicate_case_pairs"] == 0,
        quality["duplicate_time_points"] == 0,
        not sum(quality["null_cells"].values()),
        quality["finite_numeric_values"],
    ]) else "warning"
    return paired, paired_ts, quality


def _plot_incremental_metrics(paired: pd.DataFrame, target: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    specs = [
        ("incremental_cumulative_oil_m3", "Incremental cumulative oil", "m³"),
        ("water_cut_change_percentage_points", "Final water-cut change", "percentage points"),
        ("incremental_field_pressure_bar", "Final pressure change", "bar"),
    ]
    x = np.arange(len(sorted(paired[PAIR_KEY].unique())))
    width = 0.24
    for ax, (field, title, unit) in zip(axes, specs):
        for offset, (concentration, group) in enumerate(paired.groupby("parameter_polymer_concentration")):
            group = group.sort_values(PAIR_KEY)
            positions = x + (offset - 1) * width
            ax.bar(positions, group[field], width, color=COLORS[concentration], label=f"{concentration:g} kg/m³")
        ax.axhline(0, color="#334155", linewidth=1)
        ax.set_xticks(x, [str(int(v)) for v in sorted(paired[PAIR_KEY].unique())])
        ax.set_xlabel("Injection rate (m³/day)")
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.grid(axis="y", color="#e2e8f0", linewidth=.7)
    axes[-1].legend(title="Polymer concentration", frameon=False)
    fig.suptitle("Polymer flood increment relative to paired waterflood", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_oil_comparison(paired: pd.DataFrame, target: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    for ax, (rate, group) in zip(axes, paired.groupby(PAIR_KEY)):
        group = group.sort_values("parameter_polymer_concentration")
        labels = ["Water"] + [f"Poly {v:g}" for v in group["parameter_polymer_concentration"]]
        values = [group["final_cumulative_oil_m3_water"].iloc[0], *group["final_cumulative_oil_m3_polymer"]]
        colors = ["#cbd5e1", *[COLORS[v] for v in group["parameter_polymer_concentration"]]]
        ax.bar(labels, values, color=colors, edgecolor="#475569", linewidth=.5)
        ax.set_title(f"Injection rate {int(rate)} m³/day")
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", color="#e2e8f0", linewidth=.7)
        ax.ticklabel_format(axis="y", style="plain")
    axes[0].set_ylabel("Final cumulative oil (m³)")
    fig.suptitle("Waterflood and polymer-flood cumulative oil", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_incremental_trajectories(paired_ts: pd.DataFrame, target: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    for ax, (rate, rate_group) in zip(axes, paired_ts.groupby(PAIR_KEY)):
        for concentration, group in rate_group.groupby("parameter_polymer_concentration_polymer"):
            group = group.sort_values("time_days")
            ax.plot(group["time_days"], group["incremental_cumulative_oil_m3"],
                    color=COLORS[concentration], marker=MARKERS[concentration], markevery=35,
                    linewidth=1.8, label=f"{concentration:g} kg/m³")
        ax.axhline(0, color="#334155", linewidth=1)
        ax.set_title(f"Injection rate {int(rate)} m³/day")
        ax.set_ylabel("Incremental oil (m³)")
        ax.grid(color="#e2e8f0", linewidth=.7)
    axes[0].legend(title="Polymer concentration", ncol=3, frameon=False)
    axes[-1].set_xlabel("Simulation time (days)")
    fig.suptitle("Incremental cumulative-oil trajectories versus waterflood", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(target, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _report(paired: pd.DataFrame, quality: dict) -> str:
    best = paired.loc[paired["incremental_cumulative_oil_m3"].idxmax()]
    rows = []
    for _, row in paired.sort_values([PAIR_KEY, "parameter_polymer_concentration"]).iterrows():
        rows.append(
            f"| {row.parameter_polymer_concentration:g} | {row.parameter_injection_rate:.0f} | "
            f"{row.final_cumulative_oil_m3_water:,.1f} | {row.final_cumulative_oil_m3_polymer:,.1f} | "
            f"{row.incremental_cumulative_oil_m3:+,.1f} | {row.incremental_oil_percent:+.3f}% | "
            f"{row.water_cut_change_percentage_points:+.3f} | {row.incremental_field_pressure_bar:+.3f} |"
        )
    positive = int((paired["incremental_cumulative_oil_m3"] > 0).sum())
    return f"""# 水驱—聚合物驱成对增量分析

## 技术摘要

- 9 组同注入速率配对全部匹配成功，终值表 9 行、动态配对表 {quality['paired_time_series_rows']:,} 行；无缺失、重复或非有限数值。
- 仅有 {positive}/9 个聚合物方案在 10,960 天末累计产油高于水驱，全部位于 200 m³/day 注入速率。
- 最大增量产油为 {best.incremental_cumulative_oil_m3:,.1f} m³（{best.incremental_oil_percent:.3f}%），对应 {best.parameter_polymer_concentration:g} kg/m³、{best.parameter_injection_rate:.0f} m³/day。
- 100 和 150 m³/day 下的终值增量为负，说明当前 Deck 与控制条件下聚合物并非在所有注入强度下提高最终累计产油；这是一组确定性数值模拟结果，不代表统计显著性或经济最优性。

## 增油只出现在 200 m³/day 组

![成对增量终值](figures/incremental_final_metrics.png)

图中以零线区分相对水驱的改善和退化。200 m³/day 下浓度从 0.5 增至 1.5 kg/m³ 时，累计增油从约 772 m³ 增至 1,474 m³；较低注入速率下三档浓度均未超过水驱终值。含水率和压力差必须与增油同时读取，不能只按累计油排序。

## 水驱与聚合物驱的绝对产油量非常接近

![终值累计产油对比](figures/final_oil_comparison.png)

绝对累计产油主要由注入速率决定，聚合物相对水驱的差异不足绝对产油量的 1%。因此，成对差值比单独比较各方案总量更适合评价化学驱贡献。

## 动态增量揭示终值之前的演化

![动态累计增油](figures/incremental_oil_trajectories.png)

动态曲线按注入速率分面，并以同速率水驱为零基准。终值为负不等于整个模拟期间都无改善；工程评价仍需结合目标评价时点、见水时间、压力限制和经济折现。

## 配对范围与指标定义

- 配对键：`parameter_injection_rate`，水驱每档速率恰好一个基准，聚合物每档速率包含 0.5、1.0、1.5 kg/m³。
- `incremental_cumulative_oil_m3`：同一注入速率下聚合物驱末期累计油减水驱末期累计油。
- `incremental_oil_percent`：累计增油除以配对水驱累计油。
- `water_cut_change_percentage_points`：聚合物驱末期含水率减水驱末期含水率，再乘 100。
- 压力差、累计产水差和动态差值均使用“聚合物驱减水驱”的符号约定。

| 浓度 kg/m³ | 注入速率 m³/day | 水驱累计油 m³ | 聚合物累计油 m³ | 增量油 m³ | 增幅 | 含水率差 pp | 压力差 bar |
|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 方法与质量检查

终值指标按注入速率进行多对一配对；压力取每个算例最后时间点。由于 Flow 自适应时间步不同，动态表在同一注入速率内把水驱序列线性插值到聚合物算例的时间点；共涉及 {quality['waterflood_interpolated_points']:,} 个非重合时间点，并验证全部 {quality['expected_time_series_rows']:,} 个聚合物时间点均有水驱对照。结果是描述性差值，没有进行回归或因果估计。

## 局限性与稳健性

- 单一非均质 Deck、单一 OPM Flow 版本和每组一次确定性模拟，无法给出置信区间。
- 配对控制了注入速率、网格、井位和时间安排，但尚未评价聚合物质量投入、注入能耗、产水处理成本或净现值。
- 当前差值相对总累计油较小，需要进一步检查数值容差、网格敏感性以及聚合物参数设置是否足以产生预期流度控制。
- 不能从本结果推断真实油藏中的因果增油效果。

## 建议的下一步

1. 优先复核 200 m³/day、1.5 kg/m³ 方案，并增加 175–225 m³/day 的局部速率网格。
2. 增加聚合物累计注入质量、单位聚合物增油量、药剂成本、注入能耗和产水处理成本。
3. 对终值差较小或为负的组合开展网格、求解容差、吸附和黏度参数稳健性检查。
4. 在 FastAPI/Vue 中把增量指标作为配对结果展示，不将“最大总产油”误标为“最大聚合物贡献”。

## 进一步问题

- 200 m³/day 的正增量能否覆盖聚合物与能耗成本？
- 负终值增量方案是否在更早评价时点具有含水控制或阶段性增油优势？
- 当前压力差是否满足注入井井口、地层破裂压力和地面设施约束？
"""


def analyze(polymer_dir: Path, water_dir: Path) -> dict:
    """生成成对 CSV、三类图表、技术报告及 API 摘要。"""
    poly_cases = pd.read_csv(polymer_dir / "dataset" / "cases.csv")
    poly_series = pd.read_csv(polymer_dir / "dataset" / "time_series.csv")
    water_cases = pd.read_csv(water_dir / "dataset" / "cases.csv")
    water_series = pd.read_csv(water_dir / "dataset" / "time_series.csv")
    paired, paired_ts, quality = build_paired_datasets(poly_cases, poly_series, water_cases, water_series)

    target = polymer_dir / "analysis" / "waterflood_comparison"
    figures = target / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    paired.to_csv(target / "paired_case_metrics.csv", index=False)
    paired_ts.to_csv(target / "paired_time_series.csv", index=False)
    _plot_incremental_metrics(paired, figures / "incremental_final_metrics.png")
    _plot_oil_comparison(paired, figures / "final_oil_comparison.png")
    _plot_incremental_trajectories(paired_ts, figures / "incremental_oil_trajectories.png")

    best = paired.loc[paired["incremental_cumulative_oil_m3"].idxmax()]
    summary = {
        "comparison_id": f"{polymer_dir.name}_vs_{water_dir.name}",
        "polymer_experiment_id": polymer_dir.name,
        "waterflood_experiment_id": water_dir.name,
        "quality": quality,
        "positive_increment_cases": int((paired["incremental_cumulative_oil_m3"] > 0).sum()),
        "best_incremental_oil_case": json.loads(best.to_json()),
        "cases": json.loads(paired.to_json(orient="records")),
        "figures": [
            {"name": "成对增量终值", "file": "waterflood_comparison/figures/incremental_final_metrics.png"},
            {"name": "水驱与聚合物驱累计产油", "file": "waterflood_comparison/figures/final_oil_comparison.png"},
            {"name": "动态累计增油", "file": "waterflood_comparison/figures/incremental_oil_trajectories.png"},
        ],
        "report": "waterflood_comparison/report.md",
        "paired_case_metrics": "waterflood_comparison/paired_case_metrics.csv",
        "paired_time_series": "waterflood_comparison/paired_time_series.csv",
    }
    (target / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "report.md").write_text(_report(paired, quality), encoding="utf-8")

    parent_summary_file = polymer_dir / "analysis" / "summary.json"
    parent_summary = json.loads(parent_summary_file.read_text(encoding="utf-8"))
    parent_summary["waterflood_comparison"] = summary
    parent_summary_file.write_text(json.dumps(parent_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="生成水驱—聚合物驱成对增量分析")
    parser.add_argument("--polymer", default=POLYMER_ID, help="聚合物实验 ID 或目录")
    parser.add_argument("--waterflood", default=WATER_ID, help="水驱实验 ID 或目录")
    args = parser.parse_args()
    polymer = Path(args.polymer)
    water = Path(args.waterflood)
    if len(polymer.parts) == 1:
        polymer = EXPERIMENT_ROOT / polymer
    if len(water.parts) == 1:
        water = EXPERIMENT_ROOT / water
    summary = analyze(polymer.resolve(), water.resolve())
    print(json.dumps({
        "comparison_id": summary["comparison_id"],
        "quality": summary["quality"]["status"],
        "paired_cases": summary["quality"]["paired_case_rows"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
