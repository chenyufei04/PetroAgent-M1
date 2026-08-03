"""验证 CSV/XLSX 上传、字段检查和后续分析接口。"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from petro_agent.api.main import app


client = TestClient(app)


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_days": [0.0, 1.0],
            "oil_rate_m3_day": [10.0, 9.0],
            "water_rate_m3_day": [1.0, 2.0],
            "water_cut_fraction": [0.09, 0.18],
            "recovery_factor_fraction": [0.0, 0.1],
            "polymer_concentration_kg_m3": [0.0, 1.0],
        }
    )


def test_upload_csv_and_run_imported_dataset() -> None:
    content = sample_frame().to_csv(index=False).encode("utf-8")
    upload = client.post(
        "/api/datasets/upload",
        data={"case_id": "polymer_simple2d"},
        files={"file": ("sample.csv", content, "text/csv")},
    )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["ready_for_analysis"] is True
    assert payload["row_count"] == 2

    analysis = client.post(
        "/api/analysis/run",
        json={
            "case_id": "polymer_simple2d",
            "dataset_id": payload["dataset_id"],
        },
    )
    assert analysis.status_code == 200
    assert analysis.json()["summary"]["data_rows"] == 2


def test_upload_xlsx_uses_named_sheet() -> None:
    content = BytesIO()
    with pd.ExcelWriter(content, engine="openpyxl") as writer:
        pd.DataFrame({"note": ["ignore"]}).to_excel(
            writer, sheet_name="说明", index=False
        )
        sample_frame().to_excel(writer, sheet_name="数据", index=False)
    upload = client.post(
        "/api/datasets/upload",
        data={"case_id": "polymer_simple2d", "sheet_name": "数据"},
        files={
            "file": (
                "sample.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload.status_code == 200
    assert upload.json()["sheet_name"] == "数据"
    assert upload.json()["ready_for_analysis"] is True


def test_upload_reports_missing_required_columns() -> None:
    content = b"foo,bar\n1,2\n"
    upload = client.post(
        "/api/datasets/upload",
        data={"case_id": "polymer_simple2d"},
        files={"file": ("invalid.csv", content, "text/csv")},
    )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["ready_for_analysis"] is False
    assert "time_days" in payload["missing_required_columns"]
