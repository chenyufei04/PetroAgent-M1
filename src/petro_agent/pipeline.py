from __future__ import annotations

from pathlib import Path

from petro_agent.adapters.csv_adapter import CsvAdapter
from petro_agent.core.config import load_yaml
from petro_agent.core.metrics import summarize
from petro_agent.core.models import AnalysisResult
from petro_agent.domain_packs.common_reservoir.pack import CommonReservoirPack
from petro_agent.domain_packs.polymer_flooding.pack import PolymerFloodingPack
from petro_agent.reporting.markdown import write_report
from petro_agent.reporting.plots import create_figures


PACKS = {
    "common_reservoir": CommonReservoirPack,
    "polymer_flooding": PolymerFloodingPack,
}


def analyze_csv(source: Path, config_path: Path, output_root: Path) -> AnalysisResult:
    config = load_yaml(config_path)
    dataset = CsvAdapter().load(source, config)
    findings = []
    for name in config.get("domain_packs", ["common_reservoir"]):
        pack = PACKS[name]()
        dataset = pack.enrich(dataset)
        findings.extend(pack.validate(dataset))
    figures = create_figures(dataset, output_root / "figures")
    result = AnalysisResult(dataset, summarize(dataset.frame), findings, figures)
    write_report(result, output_root / "reports" / f"{dataset.case_id}.md")
    dataset.write_csv(output_root / "runs" / f"{dataset.case_id}_canonical.csv")
    return result

