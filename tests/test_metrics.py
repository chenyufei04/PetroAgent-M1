"""验证基础生产指标的确定性计算。"""

import pandas as pd

from petro_agent.core.metrics import enrich_common_metrics


def test_calculates_water_cut_and_cumulative_oil():
    frame = pd.DataFrame({
        "time_days": [0, 1, 2],
        "oil_rate_m3_day": [10, 8, 6],
        "water_rate_m3_day": [0, 2, 4],
    })
    result = enrich_common_metrics(frame)
    assert result["water_cut_fraction"].tolist() == [0.0, 0.2, 0.4]
    assert result["cumulative_oil_m3"].tolist() == [0, 8, 14]
