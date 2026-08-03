"""把结构化分析结果渲染为可追溯的 Markdown 报告。"""

from __future__ import annotations

import json
from pathlib import Path

from petro_agent.core.models import AnalysisResult


def write_report(result: AnalysisResult, path: Path) -> Path:
    dataset = result.dataset
    failures = sum(not item.passed for item in result.findings)
    lines = [
        f"# {dataset.case_id} 分析报告",
        "",
        "## 1. 数据来源与边界",
        "",
        f"- 领域：`{dataset.domain}`",
        f"- 过程：`{dataset.process}`",
        f"- 来源类型：`{dataset.source.source_type}`",
        f"- 来源模型：`{dataset.source.model}`",
        f"- 上游仓库：{dataset.source.repository or '未记录'}",
        f"- 数据行数：{len(dataset.frame)}",
        "",
        "本报告由确定性工具生成。当前结论属于数据事实与规则计算，不把语言模型推断当作数值证据。",
        "",
        "## 2. 数据概览",
        "",
        "```json",
        json.dumps(result.summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 3. 数据与物理规则校验",
        "",
        "| 规则 | 中英文名称 | 级别 | 状态 | 观测值 | 期望值 | 来源 | 适用条件 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in result.findings:
        source = item.source_name or item.source_id or "内置领域校验"
        lines.append(
            f"| {item.rule_id} | {item.message} | {item.severity} | "
            f"{'通过' if item.passed else '未通过'} | "
            f"{item.observed if item.observed is not None else '-'} | "
            f"{item.expected if item.expected is not None else '-'} | "
            f"{source} | {item.applicability or '-'} |"
        )
    lines.extend([
        "",
        f"共执行 {len(result.findings)} 条规则，发现 {failures} 条未通过。",
        "",
        "## 4. 图表",
        "",
    ])
    if result.figures:
        for figure in result.figures:
            relative = Path("..") / "figures" / figure.name
            lines.append(f"![{figure.stem}]({relative.as_posix()})")
            lines.append("")
    else:
        lines.append("没有可绘制的标准时间序列字段。")
        lines.append("")
    lines.extend([
        "## 5. 解释限制与下一步",
        "",
        "- 若输入是人工整理 CSV，应核对字段映射和单位。",
        "- 若来自 OPM Flow，应记录模拟器版本、deck 修订号及输出提取命令。",
        "- 采收率、质量守恒和孔隙体积相关结论只有在必要元数据完整时才计算。",
        "- 聚合物驱与水驱的因果比较需要相同地质模型、边界条件和一致的对照方案。",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
