"""生成生产动态等静态科研图表。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "petro-agent-matplotlib"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from petro_agent.core.models import CanonicalDataset


PLOT_FIELDS = [
    ("oil_rate_m3_day", "Oil rate"),
    ("water_cut_fraction", "Water cut"),
    ("recovery_factor_fraction", "Recovery factor"),
    ("injector_bhp_bar", "Injector BHP"),
    ("polymer_concentration_kg_m3", "Polymer concentration"),
]


def create_figures(dataset: CanonicalDataset, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    x = "injected_pv" if "injected_pv" in dataset.frame else "time_days"
    if x not in dataset.frame:
        return []
    paths: list[Path] = []
    for field, label in PLOT_FIELDS:
        if field not in dataset.frame:
            continue
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        ax.plot(dataset.frame[x], dataset.frame[field], linewidth=2)
        ax.set_xlabel(f"{x} ({dataset.units.get(x, '-')})")
        ax.set_ylabel(f"{label} ({dataset.units.get(field, '-')})")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        path = output_dir / f"{dataset.case_id}_{field}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths
