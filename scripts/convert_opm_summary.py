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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="读取 OPM ESMRY，枚举向量及单位并生成 PetroAgent 标准 CSV"
    )
    parser.add_argument("summary_file", help="OPM Flow 生成的 .ESMRY 文件")
    parser.add_argument("--output-dir", required=True, help="转换结果输出目录")
    parser.add_argument("--case-id", help="覆盖默认案例标识")
    args = parser.parse_args()
    result = convert_esmry(
        args.summary_file,
        args.output_dir,
        case_id=args.case_id,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
