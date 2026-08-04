"""定义案例、规则结果、指标和分析输出等核心数据模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SourceInfo:
    source_type: str
    model: str
    source_files: list[str] = field(default_factory=list)
    repository: str | None = None
    revision: str | None = None


@dataclass
class CanonicalDataset:
    # 多领域适配说明：这是跨领域稳定契约。新领域优先通过 frame、units、source 和
    # metadata 表达差异；只有多个领域共同需要新语义时才扩展核心字段。
    case_id: str
    domain: str
    process: str
    frame: pd.DataFrame
    units: dict[str, str]
    source: SourceInfo
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "domain": self.domain,
            "process": self.process,
            "columns": list(self.frame.columns),
            "row_count": len(self.frame),
            "units": self.units,
            "source": asdict(self.source),
            "metadata": self.metadata,
        }

    def write_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.frame.to_csv(path, index=False)


@dataclass(frozen=True)
class ValidationFinding:
    rule_id: str
    severity: str
    passed: bool
    message: str
    observed: Any = None
    concept_id: str | None = None
    expected: Any = None
    actual_unit: str | None = None
    canonical_unit: str | None = None
    source_id: str | None = None
    source_name: str | None = None
    clause: str | None = None
    applicability: str | None = None


@dataclass
class AnalysisResult:
    dataset: CanonicalDataset
    summary: dict[str, Any]
    findings: list[ValidationFinding]
    figures: list[Path] = field(default_factory=list)
