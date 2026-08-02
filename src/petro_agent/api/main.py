from __future__ import annotations

from pathlib import Path
import csv
import json
import re
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import yaml
import pandas as pd

from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings
from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService
from petro_agent.pipeline import analyze_csv

from .serializers import serialize_result


ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "config" / "cases"
DATA_ROOT = ROOT / "data" / "demo"
UPLOAD_ROOT = ROOT / "data" / "uploads"
OUTPUT_ROOT = ROOT / "outputs"
EXPERIMENT_ROOT = OUTPUT_ROOT / "experiments"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="PetroAgent Web Demo API", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    case_id: str = "polymer_simple2d"
    dataset_id: str | None = None


class GraphRequest(BaseModel):
    concept_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=300)


class GraphViewRequest(BaseModel):
    view: str = "all"
    limit: int = Field(default=200, ge=1, le=500)


def _case_config(case_id: str) -> Path:
    if not case_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "非法案例编号")
    path = (CONFIG_ROOT / f"{case_id}.yaml").resolve()
    if path.parent != CONFIG_ROOT.resolve() or not path.is_file():
        raise HTTPException(404, "案例不存在")
    return path


def _dataset_dir(dataset_id: str) -> Path:
    if not re.fullmatch(r"ds_[0-9a-f]{12}", dataset_id):
        raise HTTPException(400, "非法数据集编号")
    target = (UPLOAD_ROOT / dataset_id).resolve()
    if target.parent != UPLOAD_ROOT.resolve() or not target.is_dir():
        raise HTTPException(404, "导入数据集不存在")
    return target


def _read_uploaded_frame(path: Path, sheet_name: str | None = None) -> tuple[pd.DataFrame, str | None]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8-sig"), None
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="gb18030"), None
    if suffix == ".xlsx":
        book = pd.ExcelFile(path)
        selected = sheet_name or book.sheet_names[0]
        if selected not in book.sheet_names:
            raise ValueError(f"Sheet 不存在：{selected}")
        return pd.read_excel(book, sheet_name=selected), selected
    raise ValueError("仅支持 CSV 和 XLSX 文件")


def _dataset_payload(dataset_id: str) -> dict:
    directory = _dataset_dir(dataset_id)
    return json.loads((directory / "metadata.json").read_text(encoding="utf-8"))


def _experiment_dir(experiment_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", experiment_id):
        raise HTTPException(400, "非法实验编号")
    target = (EXPERIMENT_ROOT / experiment_id).resolve()
    if target.parent != EXPERIMENT_ROOT.resolve() or not target.is_dir():
        raise HTTPException(404, "实验不存在")
    return target


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/cases")
def list_cases() -> list[dict]:
    experiment_links: dict[str, list[str]] = {}
    for manifest in EXPERIMENT_ROOT.glob("*/experiment_manifest.json"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        analysis_case_id = data.get("analysis_case_id")
        if analysis_case_id:
            experiment_links.setdefault(str(analysis_case_id), []).append(manifest.parent.name)
    cases = []
    for path in sorted(CONFIG_ROOT.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        source = DATA_ROOT / f"{path.stem}_demo.csv"
        if path.stem == "polymer_simple2d":
            source = DATA_ROOT / "polymer_simple2d_demo.csv"
        cases.append({
            "case_id": path.stem,
            "case_name": data.get("case_id", path.stem),
            "domain": data.get("domain"),
            "process": data.get("process"),
            "runnable": source.is_file(),
            "experiments": sorted(experiment_links.get(path.stem, [])),
        })
    return cases


@app.get("/api/experiments")
def list_experiments() -> list[dict]:
    experiments = []
    for directory in sorted(EXPERIMENT_ROOT.glob("*")):
        manifest = directory / "experiment_manifest.json"
        if not directory.is_dir() or not manifest.is_file():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        experiments.append({
            "experiment_id": directory.name,
            "analysis_case_id": data.get("analysis_case_id"),
            "data_nature": data.get("data_nature"),
            "case_count": data.get("case_count", 0),
            "status_counts": data.get("status_counts", {}),
            "analyzed": (directory / "analysis" / "summary.json").is_file(),
            "updated_at": data.get("updated_at"),
        })
    return experiments


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict:
    directory = _experiment_dir(experiment_id)
    summary_file = directory / "analysis" / "summary.json"
    if not summary_file.is_file():
        raise HTTPException(409, "实验尚未生成敏感性分析结果")
    payload = json.loads(summary_file.read_text(encoding="utf-8"))
    base = f"/api/experiments/{experiment_id}/files/"
    payload["figures"] = [
        {**item, "url": base + item["file"]} for item in payload.get("figures", [])
    ]
    payload["report_url"] = base + payload["report"]
    payload["case_metrics_url"] = base + "case_metrics.csv"
    return payload


@app.get("/api/experiments/{experiment_id}/files/{file_path:path}")
def get_experiment_file(experiment_id: str, file_path: str):
    analysis_dir = (_experiment_dir(experiment_id) / "analysis").resolve()
    target = (analysis_dir / file_path).resolve()
    if analysis_dir not in target.parents or not target.is_file():
        raise HTTPException(404, "实验分析文件不存在")
    return FileResponse(target, filename=target.name)


@app.post("/api/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    case_id: str = Form("polymer_simple2d"),
    sheet_name: str | None = Form(None),
) -> dict:
    """Import one CSV/XLSX file and prepare a bounded preview for later analysis."""
    config_path = _case_config(case_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(415, "仅支持 CSV 和 XLSX 文件")
    content = await file.read()
    max_bytes = 20 * 1024 * 1024
    if not content:
        raise HTTPException(400, "上传文件为空")
    if len(content) > max_bytes:
        raise HTTPException(413, "文件不能超过 20 MB")

    dataset_id = f"ds_{uuid4().hex[:12]}"
    directory = UPLOAD_ROOT / dataset_id
    directory.mkdir(parents=True, exist_ok=False)
    original = directory / f"original{suffix}"
    original.write_bytes(content)
    try:
        frame, selected_sheet = _read_uploaded_frame(original, sheet_name)
        if frame.empty:
            raise ValueError("文件中没有可读取的数据行")
        frame.columns = [str(column).strip() for column in frame.columns]
        canonical = directory / "data.csv"
        frame.to_csv(canonical, index=False, encoding="utf-8-sig")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        required = config.get("required_columns", ["time_days"])
        mapping = config.get("column_mapping", {})
        mapped_columns = [mapping.get(column, column) for column in frame.columns]
        missing = [column for column in required if column not in mapped_columns]
        preview_rows = frame.head(20).where(pd.notna(frame), None).to_dict("records")
        preview_rows = json.loads(json.dumps(preview_rows, ensure_ascii=False, default=str))
        metadata = {
            "dataset_id": dataset_id,
            "filename": Path(file.filename or f"dataset{suffix}").name,
            "file_type": suffix.lstrip("."),
            "case_id": case_id,
            "sheet_name": selected_sheet,
            "columns": list(frame.columns),
            "row_count": len(frame),
            "missing_required_columns": missing,
            "ready_for_analysis": not missing,
            "preview_rows": preview_rows,
        }
        (directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return metadata
    except Exception as exc:
        for child in directory.iterdir():
            child.unlink()
        directory.rmdir()
        raise HTTPException(422, f"文件读取失败：{exc}") from exc


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: str) -> dict:
    return _dataset_payload(dataset_id)


@app.post("/api/analysis/run")
def run_analysis(payload: AnalysisRequest) -> dict:
    config = _case_config(payload.case_id)
    case_id_override = None
    if payload.dataset_id:
        metadata = _dataset_payload(payload.dataset_id)
        if metadata["case_id"] != payload.case_id:
            raise HTTPException(409, "数据集与所选案例不匹配")
        if not metadata["ready_for_analysis"]:
            missing = ", ".join(metadata["missing_required_columns"])
            raise HTTPException(422, f"导入文件缺少必需字段：{missing}")
        source = _dataset_dir(payload.dataset_id) / "data.csv"
        case_id_override = f"{payload.case_id}_{payload.dataset_id}"
    else:
        source = DATA_ROOT / f"{payload.case_id}_demo.csv"
        if payload.case_id == "polymer_simple2d":
            source = DATA_ROOT / "polymer_simple2d_demo.csv"
        if not source.is_file():
            raise HTTPException(409, "该案例尚未配置演示数据文件")
    try:
        result = analyze_csv(source, config, OUTPUT_ROOT, case_id_override)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"数据无法执行当前案例规则：{exc}") from exc
    return serialize_result(result, OUTPUT_ROOT)


@app.post("/api/graph/subgraph")
def graph_subgraph(payload: GraphRequest) -> dict:
    try:
        settings = Neo4jSettings.from_env(ROOT / ".env")
        with Neo4jClient(settings) as client:
            client.verify()
            graph = Neo4jQueryService(client).concept_subgraph(
                payload.concept_ids,
                payload.limit,
            )
        return {"status": "online", **graph}
    except Exception as exc:
        return {
            "status": "offline",
            "message": f"Neo4j 暂不可用：{exc}",
            "nodes": [],
            "edges": [],
        }


@app.post("/api/graph/view")
def graph_view(payload: GraphViewRequest) -> dict:
    """Execute a predefined read-only Neo4j query for the graph workbench."""
    try:
        settings = Neo4jSettings.from_env(ROOT / ".env")
        with Neo4jClient(settings) as client:
            client.verify()
            graph = Neo4jQueryService(client).graph_view(
                payload.view,
                payload.limit,
            )
        return {"status": "online", "view": payload.view, **graph}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        return {
            "status": "offline",
            "view": payload.view,
            "message": f"Neo4j 暂不可用：{exc}",
            "nodes": [],
            "edges": [],
        }


@app.get("/api/outputs/{category}/{filename}")
def download_output(category: str, filename: str):
    target = _safe_output_file(category, filename)
    return FileResponse(target, filename=filename)


def _safe_output_file(category: str, filename: str) -> Path:
    if category not in {"reports", "runs", "figures"}:
        raise HTTPException(404, "输出分类不存在")
    if Path(filename).name != filename:
        raise HTTPException(400, "非法文件名")
    target = (OUTPUT_ROOT / category / filename).resolve()
    if target.parent != (OUTPUT_ROOT / category).resolve() or not target.is_file():
        raise HTTPException(404, "输出文件不存在")
    return target


@app.get("/api/outputs/preview/{category}/{filename}")
def preview_output(category: str, filename: str) -> dict:
    """Return a bounded, UI/LangChain-friendly preview of a text output."""
    target = _safe_output_file(category, filename)
    suffix = target.suffix.lower()
    if suffix == ".csv":
        with target.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = []
            for index, row in enumerate(reader):
                if index >= 200:
                    break
                rows.append(dict(row))
            return {
                "kind": "table",
                "name": filename,
                "columns": reader.fieldnames or [],
                "rows": rows,
                "truncated": index >= 200 if rows else False,
            }
    if suffix == ".json":
        data = json.loads(target.read_text(encoding="utf-8"))
        return {"kind": "document", "format": "json", "name": filename, "content": data}
    if suffix in {".md", ".txt"}:
        content = target.read_text(encoding="utf-8")
        limit = 100_000
        return {
            "kind": "document",
            "format": "markdown" if suffix == ".md" else "text",
            "name": filename,
            "content": content[:limit],
            "truncated": len(content) > limit,
        }
    raise HTTPException(415, "该文件类型不支持结构化预览")


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
