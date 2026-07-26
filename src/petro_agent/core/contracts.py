from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import CanonicalDataset, ValidationFinding


class DatasetAdapter(Protocol):
    def load(self, source: Path, config: dict) -> CanonicalDataset: ...


class DomainPack(Protocol):
    name: str

    def enrich(self, dataset: CanonicalDataset) -> CanonicalDataset: ...

    def validate(self, dataset: CanonicalDataset) -> list[ValidationFinding]: ...

