from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.adapters.opm import FlowExecutionConfig, run_batch_experiment


def main() -> int:
    defaults = FlowExecutionConfig.from_environment()
    parser = argparse.ArgumentParser(
        description="生成参数化 Deck、批量运行 OPM Flow 并汇总合成数据集"
    )
    parser.add_argument("config", help="参数实验 YAML 配置")
    parser.add_argument("--prepare-only", action="store_true", help="只生成派生 Deck")
    parser.add_argument("--no-resume", action="store_true", help="不复用已成功的算例")
    parser.add_argument("--mode", choices=["wsl", "native"], default=defaults.execution_mode)
    parser.add_argument("--distribution", default=defaults.wsl_distribution)
    parser.add_argument("--flow-command", default=defaults.flow_command)
    parser.add_argument("--timeout", type=int, default=defaults.timeout_seconds)
    args = parser.parse_args()
    result = run_batch_experiment(
        args.config,
        prepare_only=args.prepare_only,
        resume=not args.no_resume,
        flow_config=FlowExecutionConfig(
            args.mode, args.distribution, args.flow_command, args.timeout
        ),
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
