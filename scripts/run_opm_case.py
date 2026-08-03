"""运行单个 OPM Flow Deck，并保存命令、日志和运行清单。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
from petro_agent.adapters.opm import FlowExecutionConfig, run_flow


def main() -> int:
    defaults = FlowExecutionConfig.from_environment()
    parser = argparse.ArgumentParser(description="通过 WSL 或本机 OPM Flow 运行 Deck")
    parser.add_argument("deck_file", help="根 .DATA 文件")
    parser.add_argument("--output-dir", required=True, help="独立输出目录")
    parser.add_argument("--mode", choices=["wsl", "native"], default=defaults.execution_mode)
    parser.add_argument("--distribution", default=defaults.wsl_distribution)
    parser.add_argument("--flow-command", default=defaults.flow_command)
    parser.add_argument("--timeout", type=int, default=defaults.timeout_seconds)
    parser.add_argument("flow_args", nargs="*", help="传给 Flow 的额外参数")
    args = parser.parse_args()
    result = run_flow(
        args.deck_file,
        args.output_dir,
        config=FlowExecutionConfig(
            args.mode,
            args.distribution,
            args.flow_command,
            args.timeout,
        ),
        extra_args=args.flow_args,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return result.return_code


if __name__ == "__main__":
    raise SystemExit(main())
