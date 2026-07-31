from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from petro_agent.adapters.opm import (
    FlowExecutionConfig,
    inspect_flow_environment,
)


def main() -> int:
    defaults = FlowExecutionConfig.from_environment()

    parser = argparse.ArgumentParser(
        description="检查 WSL 或本机 OPM Flow 环境"
    )
    parser.add_argument(
        "--mode",
        choices=["wsl", "native"],
        default=defaults.execution_mode,
    )
    parser.add_argument(
        "--distribution",
        default=defaults.wsl_distribution,
    )
    parser.add_argument(
        "--flow-command",
        default=defaults.flow_command,
    )
    args = parser.parse_args()

    config = FlowExecutionConfig(
        execution_mode=args.mode,
        wsl_distribution=args.distribution,
        flow_command=args.flow_command,
        timeout_seconds=defaults.timeout_seconds,
    )

    result = inspect_flow_environment(config)

    print(
        json.dumps(
            result.__dict__,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if result.available else 1


if __name__ == "__main__":
    raise SystemExit(main())