"""从聚合物 Deck 生成独立、可审计且不含化学驱关键字的水驱基准。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "polymer_simple2D" / "2D_THREEPHASE_POLY_HETER.DATA"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "waterflood_baseline" / "2D_THREEPHASE_WATER_HETER.DATA"
PROHIBITED_KEYWORDS = {
    "POLYMER", "WPOLYMER", "PLYVISC", "PLYROCK", "PLYADS", "PLMIXPAR",
    "PLYMAX", "PLYSHLOG",
}


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _keyword(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("--"):
        return ""
    return stripped.split()[0].upper()


def build_waterflood_deck(source_text: str) -> tuple[str, dict[str, int]]:
    """移除聚合物模型激活项，同时保留井控和注入速率参数。"""
    lines = source_text.splitlines(keepends=True)
    output: list[str] = []
    removed = {
        "runspec_polymer": 0,
        "poly_include": 0,
        "wpolymer_blocks": 0,
        "rptsched_polymer_token": 0,
    }
    index = 0
    expect_rptsched_options = False
    while index < len(lines):
        line = lines[index]
        keyword = _keyword(line)

        # RPTSCHED options may be on the following non-comment line. Process
        # them before keyword detection because that line starts with POLYMER.
        if expect_rptsched_options:
            if not keyword:
                output.append(line)
                index += 1
                continue
            line, replacements = re.subn(
                r"\bPOLYMER\b\s*", "", line, flags=re.IGNORECASE
            )
            removed["rptsched_polymer_token"] += replacements
            expect_rptsched_options = False
            output.append(line)
            index += 1
            continue

        if line.strip().upper() == "POLYMER":
            removed["runspec_polymer"] += 1
            index += 1
            continue
        if keyword == "WPOLYMER":
            removed["wpolymer_blocks"] += 1
            index += 1
            while index < len(lines):
                block_line = lines[index]
                index += 1
                if "/" in block_line.split("--", 1)[0]:
                    break
            continue
        if keyword == "INCLUDE" and index + 1 < len(lines):
            include_line = lines[index + 1]
            if re.search(r"['\"]POLY\.inc['\"]", include_line, re.IGNORECASE):
                removed["poly_include"] += 1
                index += 2
                continue
        if keyword == "RPTSCHED":
            if "POLYMER" in line.upper():
                line, replacements = re.subn(
                    r"\bPOLYMER\b\s*", "", line, flags=re.IGNORECASE
                )
                removed["rptsched_polymer_token"] += replacements
            elif "/" not in line.split("--", 1)[0]:
                expect_rptsched_options = True
        output.append(line)
        index += 1
    return "".join(output), removed


def validate_waterflood_deck(text: str, removed: dict[str, int]) -> dict[str, object]:
    """确认化学驱关键字已清除且水驱时序结构保持完整。"""
    active_keywords = [_keyword(line) for line in text.splitlines()]
    remaining = sorted(set(active_keywords) & PROHIBITED_KEYWORDS)
    checks = {
        "removed_exactly_one_runspec_polymer": removed["runspec_polymer"] == 1,
        "removed_exactly_one_poly_include": removed["poly_include"] == 1,
        "removed_three_wpolymer_blocks": removed["wpolymer_blocks"] == 3,
        "removed_rptsched_polymer_token": removed["rptsched_polymer_token"] == 1,
        "no_active_polymer_keywords": not remaining,
        "no_polymer_concentration_token": "{{PETRO_PARAM_POLYMER_CONCENTRATION}}" not in text,
        "three_injection_rate_tokens": text.count("{{PETRO_PARAM_INJECTION_RATE}}") == 3,
        "three_water_injection_controls": active_keywords.count("WCONINJE") == 3,
        "three_production_controls": active_keywords.count("WCONPROD") == 3,
        "three_tstep_blocks": active_keywords.count("TSTEP") == 3,
        "has_schedule": active_keywords.count("SCHEDULE") == 1,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "remaining_prohibited_keywords": remaining,
    }


def prepare(source: Path, output: Path) -> dict[str, object]:
    """生成水驱 Deck 和包含哈希、移除计数的来源清单。"""
    source_bytes = source.read_bytes()
    source_text = source_bytes.decode("utf-8")
    waterflood_text, removed = build_waterflood_deck(source_text)
    validation = validate_waterflood_deck(waterflood_text, removed)
    if not validation["passed"]:
        raise ValueError(f"水驱 Deck 校验失败：{validation}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(waterflood_text, encoding="utf-8", newline="\n")
    provenance = {
        "variant": "waterflood_baseline",
        "source_deck": str(source.resolve()),
        "source_sha256": _sha256_bytes(source_bytes),
        "generated_deck": str(output.resolve()),
        "generated_sha256": _sha256_bytes(output.read_bytes()),
        "removed": removed,
        "validation": validation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "聚合物 Deck 原文件未修改。",
            "已移除 POLYMER、POLY.inc INCLUDE、全部 WPOLYMER 和 RPTSCHED 中的 POLYMER 请求。",
            "网格、PVT、相渗、井位、井控、时间步和注入速率占位符保持不变。",
        ],
    }
    (output.parent / "baseline_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description="从聚合物算例生成独立、可审计的水驱基准 Deck")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-only", action="store_true", help="只检查转换，不写文件")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if args.check_only:
        text, removed = build_waterflood_deck(source.read_text(encoding="utf-8"))
        result = {"removed": removed, "validation": validate_waterflood_deck(text, removed)}
    else:
        result = prepare(source, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
