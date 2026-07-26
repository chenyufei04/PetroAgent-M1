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


@dataclass
class AnalysisResult:
    dataset: CanonicalDataset
    summary: dict[str, Any]
    findings: list[ValidationFinding]
    figures: list[Path] = field(default_factory=list)

