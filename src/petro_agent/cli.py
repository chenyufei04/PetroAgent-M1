from __future__ import annotations

import argparse
import json
from pathlib import Path

from petro_agent.adapters.eclipse_deck import inspect_deck
from petro_agent.pipeline import analyze_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PetroAgent M1 deterministic analysis CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Analyze a standardized CSV")
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--config", type=Path, required=True)
    analyze.add_argument("--output", type=Path, default=Path("outputs"))
    deck = sub.add_parser("inspect-deck", help="Inspect an Eclipse/OPM deck and INCLUDE graph")
    deck.add_argument("--input", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "analyze":
        result = analyze_csv(args.input, args.config, args.output)
        print(json.dumps({
            "case_id": result.dataset.case_id,
            "rows": len(result.dataset.frame),
            "failed_rules": sum(not finding.passed for finding in result.findings),
            "report": str(args.output / "reports" / f"{result.dataset.case_id}.md"),
        }, ensure_ascii=False, indent=2))
    elif args.command == "inspect-deck":
        print(json.dumps(inspect_deck(args.input).__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

