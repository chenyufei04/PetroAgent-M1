"""验证通用数据质量规则及物理范围检查。"""

import pandas as pd

from petro_agent.core.models import CanonicalDataset, SourceInfo
from petro_agent.validators.common import validate_common


def make_dataset(frame):
    return CanonicalDataset(
        "test", "reservoir_engineering", "water_flooding", frame, {},
        SourceInfo("test", "test"),
    )


def test_flags_out_of_bounds_water_cut():
    findings = validate_common(make_dataset(pd.DataFrame({
        "time_days": [0, 1],
        "water_cut_fraction": [0.2, 1.2],
    })))
    finding = next(item for item in findings if item.rule_id == "WATER_CUT_BOUNDS")
    assert not finding.passed


def test_accepts_monotonic_recovery():
    findings = validate_common(make_dataset(pd.DataFrame({
        "time_days": [0, 1, 2],
        "recovery_factor_fraction": [0.0, 0.1, 0.2],
    })))
    assert next(item for item in findings if item.rule_id == "RECOVERY_MONOTONIC").passed
