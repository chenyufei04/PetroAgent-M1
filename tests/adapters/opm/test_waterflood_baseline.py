"""验证聚合物 Deck 到独立水驱基准的转换约束。"""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "prepare_waterflood_baseline.py"
SPEC = importlib.util.spec_from_file_location("prepare_waterflood_baseline", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_original_polymer_deck_converts_to_valid_waterflood():
    source = MODULE.DEFAULT_SOURCE.read_text(encoding="utf-8")
    converted, removed = MODULE.build_waterflood_deck(source)
    validation = MODULE.validate_waterflood_deck(converted, removed)

    assert validation["passed"] is True
    assert removed == {
        "runspec_polymer": 1,
        "poly_include": 1,
        "wpolymer_blocks": 3,
        "rptsched_polymer_token": 1,
    }
    assert "{{PETRO_PARAM_POLYMER_CONCENTRATION}}" not in converted
    assert converted.count("{{PETRO_PARAM_INJECTION_RATE}}") == 3
