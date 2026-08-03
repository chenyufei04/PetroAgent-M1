"""将领域分析结果序列化为前端稳定使用的 JSON 结构。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from petro_agent.core.models import AnalysisResult


def serialize_result(result: AnalysisResult, output_root: Path) -> dict:
    findings = [asdict(item) for item in result.findings]
    failed = sum(not item["passed"] for item in findings)
    warnings = sum(
        not item["passed"] and item["severity"].lower() == "warning"
        for item in findings
    )
    case_id = result.dataset.case_id
    concept_ids = sorted({
        item["concept_id"] for item in findings if item.get("concept_id")
    })
    files = [
        {
            "name": f"{case_id}.md",
            "type": "markdown",
            "display_category": "document",
            "download_url": f"/api/outputs/reports/{case_id}.md",
            "preview_url": f"/api/outputs/preview/reports/{case_id}.md",
        },
        {
            "name": f"{case_id}_canonical.csv",
            "type": "csv",
            "display_category": "table",
            "download_url": f"/api/outputs/runs/{case_id}_canonical.csv",
            "preview_url": f"/api/outputs/preview/runs/{case_id}_canonical.csv",
        },
        {
            "name": f"{case_id}_result.json",
            "type": "json",
            "display_category": "document",
            "download_url": f"/api/outputs/runs/{case_id}_result.json",
            "preview_url": f"/api/outputs/preview/runs/{case_id}_result.json",
        },
    ]
    for figure in result.figures:
        files.append({
            "name": figure.name,
            "type": "image",
            "display_category": "chart",
            "download_url": f"/api/outputs/figures/{figure.name}",
            "preview_url": f"/api/outputs/figures/{figure.name}",
        })
    return {
        "case": result.dataset.to_metadata(),
        "summary": {
            "total_rules": len(findings),
            "passed_rules": len(findings) - failed,
            "failed_rules": failed,
            "warnings": warnings,
            "data_rows": len(result.dataset.frame),
        },
        "metrics": result.summary,
        "results": findings,
        "concept_ids": concept_ids,
        "output_files": files,
    }
