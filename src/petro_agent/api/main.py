from __future__ import annotations

from pathlib import Path
import csv
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import yaml

from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings
from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService
from petro_agent.pipeline import analyze_csv

from .serializers import serialize_result


ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "config" / "cases"
DATA_ROOT = ROOT / "data" / "demo"
OUTPUT_ROOT = ROOT / "outputs"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="PetroAgent Web Demo API", version="0.4.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    case_id: str = "polymer_simple2d"


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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/cases")
def list_cases() -> list[dict]:
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
        })
    return cases


@app.post("/api/analysis/run")
def run_analysis(payload: AnalysisRequest) -> dict:
    config = _case_config(payload.case_id)
    source = DATA_ROOT / f"{payload.case_id}_demo.csv"
    if payload.case_id == "polymer_simple2d":
        source = DATA_ROOT / "polymer_simple2d_demo.csv"
    if not source.is_file():
        raise HTTPException(409, "该案例尚未配置演示数据文件")
    result = analyze_csv(source, config, OUTPUT_ROOT)
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
