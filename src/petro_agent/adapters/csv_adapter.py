"""读取表格数据并转换为 PetroAgent 统一数据契约。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from petro_agent.core.models import CanonicalDataset, SourceInfo


class CsvAdapter:
    def load(self, source: Path, config: dict) -> CanonicalDataset:
        # 多领域适配说明：通用 CSV 只依赖案例 YAML 的映射和单位。若新领域需要多表关联、
        # 特殊二进制格式或按井/层/作业段重塑数据，应新增适配器，不要在这里判断领域名称。
        frame = pd.read_csv(source)
        mapping = config.get("column_mapping", {})
        frame = frame.rename(columns=mapping)
        required = config.get("required_columns", ["time_days"])
        missing = [name for name in required if name not in frame.columns]
        if missing:
            raise ValueError(f"缺少必需字段: {', '.join(missing)}")
        return CanonicalDataset(
            case_id=config["case_id"],
            domain=config.get("domain", "reservoir_engineering"),
            process=config.get("process", "unknown"),
            frame=frame,
            units=config.get("units", {}),
            source=SourceInfo(
                source_type=config.get("source_type", "csv"),
                model=config.get("model", source.stem),
                source_files=[str(source)],
                repository=config.get("repository"),
                revision=config.get("revision"),
            ),
            metadata=config.get("metadata", {}),
        )
