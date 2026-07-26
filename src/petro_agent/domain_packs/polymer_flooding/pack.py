from __future__ import annotations

from petro_agent.core.models import CanonicalDataset, ValidationFinding


class PolymerFloodingPack:
    name = "polymer_flooding"

    def enrich(self, dataset: CanonicalDataset) -> CanonicalDataset:
        frame = dataset.frame
        if "polymer_concentration_kg_m3" in frame:
            dataset.metadata["polymer_active_rows"] = int((frame["polymer_concentration_kg_m3"] > 0).sum())
        return dataset

    def validate(self, dataset: CanonicalDataset) -> list[ValidationFinding]:
        frame = dataset.frame
        if "polymer_concentration_kg_m3" not in frame:
            return [ValidationFinding(
                "POLYMER_COLUMN_PRESENT", "warning", False,
                "缺少聚合物浓度字段；若这是水驱基线则可接受",
            )]
        series = frame["polymer_concentration_kg_m3"].dropna()
        nonnegative = bool((series >= 0).all())
        return [ValidationFinding(
            "POLYMER_CONCENTRATION_NONNEGATIVE", "error", nonnegative,
            "聚合物浓度非负" if nonnegative else "聚合物浓度存在负值",
        )]

