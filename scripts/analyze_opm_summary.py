from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.adapters.opm import convert_esmry
from petro_agent.pipeline import analyze_csv


def main() -> int:
    parser = argparse.ArgumentParser(
        description="完成 ESMRY → 标准 CSV → 图表、规则和统一科研报告"
    )
    parser.add_argument("summary_file", help="OPM Flow 生成的 .ESMRY 文件")
    parser.add_argument("--output-root", default=str(ROOT / "outputs"))
    parser.add_argument(
        "--config",
        default=str(ROOT / "config/cases/opm_polymer_summary.yaml"),
    )
    parser.add_argument("--case-id", help="覆盖默认案例标识")
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    converted = convert_esmry(
        args.summary_file,
        output_root / "converted",
        case_id=args.case_id,
    )
    result = analyze_csv(
        Path(converted.standard_csv),
        Path(args.config),
        output_root,
        case_id_override=args.case_id or Path(args.summary_file).stem.lower(),
    )
    passed = sum(item.passed for item in result.findings)
    payload = {
        "case_id": result.dataset.case_id,
        "standard_csv": converted.standard_csv,
        "vector_catalog_csv": converted.vector_catalog_csv,
        "metadata_json": converted.metadata_json,
        "report": str(output_root / "reports" / f"{result.dataset.case_id}.md"),
        "figures": [str(item) for item in result.figures],
        "rules_passed": passed,
        "rules_failed": len(result.findings) - passed,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
