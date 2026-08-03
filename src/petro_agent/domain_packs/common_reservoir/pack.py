"""实现适用于常规油藏案例的通用领域规则包。"""

from petro_agent.core.metrics import enrich_common_metrics
from petro_agent.core.models import CanonicalDataset, ValidationFinding
from petro_agent.validators.common import validate_common


class CommonReservoirPack:
    name = "common_reservoir"

    def enrich(self, dataset: CanonicalDataset) -> CanonicalDataset:
        dataset.frame = enrich_common_metrics(dataset.frame, dataset.metadata.get("pore_volume_m3"))
        return dataset

    def validate(self, dataset: CanonicalDataset) -> list[ValidationFinding]:
        return validate_common(dataset)
