"""提供案例分析、实验结果、文件下载和知识图谱查询接口。"""

from __future__ import annotations

from pathlib import Path
import csv
import json
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import yaml
import pandas as pd

from petro_agent.agents import AnalysisAssistant
from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings
from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService
from petro_agent.llm import LlmSettings, create_provider
from petro_agent.pipeline import analyze_csv

from .serializers import serialize_result
from .request_logging import configure_api_logger


ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "config" / "cases"
DATA_ROOT = ROOT / "data" / "demo"
UPLOAD_ROOT = ROOT / "data" / "uploads"
OUTPUT_ROOT = ROOT / "outputs"
EXPERIMENT_ROOT = OUTPUT_ROOT / "experiments"
FRONTEND_DIST = ROOT / "frontend" / "dist"
API_LOGGER = configure_api_logger(ROOT)

app = FastAPI(title="PetroAgent Web Demo API", version="0.10.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_api_request(request: Request, call_next):
    """统一记录所有 HTTP 调用；不保存请求正文、查询值和认证信息等敏感内容。"""
    started = perf_counter()
    supplied_request_id = request.headers.get("x-request-id", "")
    request_id = supplied_request_id if 0 < len(supplied_request_id) <= 128 else uuid4().hex
    common = {
        "event": "api_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", "")[:512],
    }
    try:
        response = await call_next(request)
    except Exception as exc:
        # 未处理异常先写日志再交回 FastAPI/uvicorn，确保 500 调用也有追踪记录。
        API_LOGGER.exception(
            "接口调用异常",
            extra={
                **common,
                "status_code": 500,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:1000],
            },
        )
        raise
    response.headers["X-Request-ID"] = request_id
    API_LOGGER.info(
        "接口调用完成",
        extra={
            **common,
            "status_code": response.status_code,
            "duration_ms": round((perf_counter() - started) * 1000, 3),
        },
    )
    return response


class AnalysisRequest(BaseModel):
    """指定待分析案例及可选的用户上传数据集。"""
    case_id: str = "polymer_simple2d"
    dataset_id: str | None = None


class GraphRequest(BaseModel):
    """限定知识子图查询的概念集合和返回规模。"""
    concept_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=300)


class GraphViewRequest(BaseModel):
    """指定预定义图谱视图和最大返回规模。"""
    view: str = "all"
    limit: int = Field(default=200, ge=1, le=500)


class AssistantChatRequest(BaseModel):
    """只读分析助手请求；当前实验与方案必须由页面显式传入。"""

    experiment_id: str = Field(min_length=1, max_length=120)
    case_id: str = Field(min_length=1, max_length=160)
    question: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=10)


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
    """列出实验血缘、运行状态以及是否已有分析产物。"""
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
            "comparison_role": data.get("comparison_role", "scenario"),
            "paired_experiment_id": data.get("paired_experiment_id"),
            "analyzed": (directory / "analysis" / "summary.json").is_file(),
            "updated_at": data.get("updated_at"),
        })
    return experiments


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict:
    """返回单个实验摘要，并补齐安全的图表和数据下载 URL。"""
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
    comparison = payload.get("waterflood_comparison")
    if comparison:
        comparison["figures"] = [
            {**item, "url": base + item["file"]}
            for item in comparison.get("figures", [])
        ]
        comparison["report_url"] = base + comparison["report"]
        comparison["paired_case_metrics_url"] = base + comparison["paired_case_metrics"]
        comparison["paired_time_series_url"] = base + comparison["paired_time_series"]
    economics = payload.get("techno_economics")
    if economics:
        # 只拼接 analysis 目录内的受控相对路径，实际下载仍由安全文件接口校验。
        for field in (
            "case_economics", "constraints", "rankings", "report", "ranking_report",
            "metric_observations", "rule_executions", "recommendations", "explanation_chains",
        ):
            if economics.get(field):
                economics[f"{field}_url"] = base + economics[field]
        economics["rankings_api_url"] = f"/api/experiments/{experiment_id}/techno-economic-rankings"
        economics["explanation_api_template"] = f"/api/experiments/{experiment_id}/cases/{{case_id}}/explanation"
    return payload


@app.get("/api/experiments/{experiment_id}/techno-economic-rankings")
def get_techno_economic_rankings(experiment_id: str) -> dict:
    """返回文件系统中的技术经济排名；该接口不依赖 Neo4j 在线状态。"""
    directory = _experiment_dir(experiment_id)
    analysis = directory / "analysis" / "techno_economics"
    summary_path = analysis / "summary.json"
    rankings_path = analysis / "scenario_rankings.csv"
    if not summary_path.is_file() or not rankings_path.is_file():
        raise HTTPException(409, "实验尚未生成技术经济排名")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(rankings_path)
    # 通过 JSON 转换把 CSV 中的 NaN 变为 null，保证 FastAPI 返回严格 JSON。
    rows = json.loads(frame.to_json(orient="records"))
    return {**summary, "rows": rows}


@app.get("/api/experiments/{experiment_id}/cases/{case_id}/explanation")
def get_scenario_explanation(experiment_id: str, case_id: str) -> dict:
    """返回单方案从指标观测、规则执行到推荐证据的完整解释链。"""
    # 多领域适配说明：解释链结构是跨领域契约，可以直接复用；新领域只需生成同结构数据。
    # 领域专用 KPI、曲线或作业层级应增加独立接口，不要改变本接口的通用返回语义。
    directory = _experiment_dir(experiment_id)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", case_id):
        raise HTTPException(400, "非法算例编号")
    path = directory / "analysis" / "techno_economics" / "explanation_chains.json"
    file_payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    file_chain = next(
        (item for item in file_payload.get("cases", []) if item.get("case_id") == case_id),
        None,
    )
    # 在线时优先走知识图谱关系链；连接失败时回退到同一分析阶段生成的可审计 JSON。
    try:
        settings = Neo4jSettings.from_env(ROOT / ".env")
        with Neo4jClient(settings) as client:
            client.verify()
            graph_chain = Neo4jQueryService(client).scenario_explanation(case_id)
        if graph_chain and graph_chain.get("recommendation"):
            if file_chain:
                # 图谱可能尚未执行最新一轮回写；按稳定执行 ID 补齐单位等新增证据字段。
                local_rules = {
                    item["rule_execution_id"]: item
                    for item in file_chain.get("rule_executions", [])
                }
                graph_chain["rule_executions"] = [
                    {
                        **item,
                        **{
                            key: value
                            for key, value in local_rules.get(item.get("rule_execution_id"), {}).items()
                            if item.get(key) is None
                        },
                    }
                    for item in graph_chain.get("rule_executions", [])
                ]
                local_evidence = file_chain.get("evidence") or {}
                graph_evidence = graph_chain.get("evidence") or {}
                graph_chain["evidence"] = {
                    **graph_evidence,
                    **{key: value for key, value in local_evidence.items() if graph_evidence.get(key) is None},
                }
            return {"source": "neo4j", **graph_chain}
    except Exception:
        pass
    if not path.is_file():
        raise HTTPException(409, "实验尚未生成语义解释链")
    payload = file_payload
    chain = file_chain
    if chain is None:
        raise HTTPException(404, "算例解释链不存在")
    return {"source": "file", "model_id": payload.get("model_id"), **chain}


def _scenario_graph(chain: dict) -> dict:
    """把通用解释链转换成前端可直接渲染的方案子图。

    多领域适配说明：这里只识别稳定的语义角色，不识别聚合物浓度、井筒压力等
    领域字段。新领域只要继续产出 observation/rule/recommendation/evidence 四类对象，
    就能复用同一个工作台和图谱组件。
    """
    case_id = str(chain["case_id"])
    recommendation = chain.get("recommendation") or {}
    evidence = chain.get("evidence") or {}
    nodes = [{"id": case_id, "label": case_id, "type": "SimulationCase", "properties": {"case_id": case_id}}]
    edges: list[dict] = []

    for item in chain.get("observations", []):
        node_id = str(item["observation_id"])
        nodes.append({
            "id": node_id,
            "label": str(item.get("concept_id") or item.get("source_field") or node_id),
            "type": "MetricObservation",
            "properties": item,
        })
        edges.append({"id": f"{case_id}:observation:{node_id}", "source": case_id, "target": node_id, "label": "观测"})

    for item in chain.get("rule_executions", []):
        node_id = str(item["rule_execution_id"])
        nodes.append({
            "id": node_id,
            "label": str(item.get("rule_id") or node_id),
            "type": "RuleExecution",
            "properties": item,
            "passed": bool(item.get("passed")),
        })
        edges.append({"id": f"{case_id}:rule:{node_id}", "source": case_id, "target": node_id, "label": "执行"})

    recommendation_id = recommendation.get("recommendation_id")
    if recommendation_id:
        nodes.append({
            "id": str(recommendation_id),
            "label": str(recommendation.get("decision") or "推荐结论"),
            "type": "Recommendation",
            "properties": recommendation,
        })
        edges.append({"id": f"{case_id}:recommendation", "source": case_id, "target": str(recommendation_id), "label": "形成推荐"})
        for execution_id in recommendation.get("justifying_execution_ids", []):
            edges.append({
                "id": f"{recommendation_id}:justified:{execution_id}",
                "source": str(recommendation_id),
                "target": str(execution_id),
                "label": "依据",
            })

    source_id = evidence.get("source_id")
    if source_id:
        evidence_node_id = f"source:{source_id}"
        nodes.append({"id": evidence_node_id, "label": str(source_id), "type": "Source", "properties": evidence})
        if recommendation_id:
            edges.append({"id": f"{recommendation_id}:source", "source": str(recommendation_id), "target": evidence_node_id, "label": "证据"})
    return {"status": "online" if chain.get("source") == "neo4j" else "file", "nodes": nodes, "edges": edges}


@app.get("/api/experiments/{experiment_id}/cases/{case_id}/context")
def get_scenario_context(experiment_id: str, case_id: str) -> dict:
    """返回以当前实验方案为唯一上下文的领域无关工作台契约。"""
    directory = _experiment_dir(experiment_id)
    chain = get_scenario_explanation(experiment_id, case_id)
    rankings_path = directory / "analysis" / "techno_economics" / "scenario_rankings.csv"
    scenario: dict = {"case_id": case_id}
    ranking_rows: list[dict] = []
    ranking_metadata: dict = {}
    if rankings_path.is_file():
        ranking_rows = json.loads(pd.read_csv(rankings_path).to_json(orient="records"))
        # 不假设主键列名；只要一行中有字段值等于 case_id，就认为它是当前方案。
        scenario = next((row for row in ranking_rows if case_id in row.values()), scenario)
        summary_path = rankings_path.parent / "summary.json"
        if summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            ranking_metadata = {
                key: summary.get(key)
                for key in ("ranking_policy", "assumption_status", "case_count")
                if summary.get(key) is not None
            }

    observations = chain.get("observations", [])
    parameters = [
        item for item in observations
        if any(token in str(item.get("source_field", "")).lower() for token in ("concentration", "rate", "duration", "parameter"))
    ]
    parameter_ids = {item.get("observation_id") for item in parameters}
    metrics = [item for item in observations if item.get("observation_id") not in parameter_ids]
    rules = chain.get("rule_executions", [])
    return {
        "contract_version": "scenario-context/v1",
        "experiment_id": experiment_id,
        "case_id": case_id,
        "scenario": scenario,
        # 完整排名仍限定在当前实验内，供“全部方案”和跨方案比较问题使用。
        # 新领域只需在自己的分析产物中提供 scenario_rank 与方案标识，无需修改 Agent。
        "rankings": ranking_rows,
        "ranking_metadata": ranking_metadata,
        "parameters": parameters,
        "metrics": metrics,
        "rules": rules,
        "rule_summary": {
            "total": len(rules),
            "passed": sum(bool(item.get("passed")) for item in rules),
            "failed": sum(not bool(item.get("passed")) for item in rules),
        },
        "recommendation": chain.get("recommendation") or {},
        "evidence": chain.get("evidence") or {},
        "provenance": {"source": chain.get("source"), "model_id": chain.get("model_id")},
        "graph": _scenario_graph(chain),
    }


@app.get("/api/experiments/{experiment_id}/files/{file_path:path}")
def get_experiment_file(experiment_id: str, file_path: str):
    """仅允许下载指定实验 analysis 目录内的文件。"""
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


@app.get("/api/graph/experiments/{experiment_id}/rankings")
def experiment_rankings(experiment_id: str) -> dict:
    """返回 Neo4j 中的实验方案排名；数据库离线时保持页面其余功能可用。"""
    _experiment_dir(experiment_id)
    try:
        settings = Neo4jSettings.from_env(ROOT / ".env")
        with Neo4jClient(settings) as client:
            client.verify()
            rows = Neo4jQueryService(client).experiment_rankings(experiment_id)
        return {"status": "online", "experiment_id": experiment_id, "rows": rows}
    except Exception as exc:
        return {
            "status": "offline",
            "experiment_id": experiment_id,
            "message": f"Neo4j 暂不可用：{exc}",
            "rows": [],
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


@app.get("/api/assistant/status")
def assistant_status() -> dict:
    """报告大模型配置状态，但不返回 API Key 等敏感信息。"""
    settings = LlmSettings.from_env()
    return {
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "mode": (
            "offline-debug" if settings.provider == "mock"
            else "local-ollama" if settings.provider == "ollama"
            else "openai-compatible"
        ),
        "read_only": True,
    }


@app.post("/api/assistant/chat")
def assistant_chat(payload: AssistantChatRequest) -> dict:
    """让 Qwen 基于当前方案事实回答，并返回受控页面展示指令。"""
    try:
        assistant = AnalysisAssistant(create_provider(), get_scenario_context)
        # 历史消息只允许 user/assistant 文本，避免客户端覆盖系统提示或无限扩大上下文。
        history = [
            {"role": item.get("role", ""), "content": str(item.get("content", ""))[:4000]}
            for item in payload.history
            if item.get("role") in {"user", "assistant"} and str(item.get("content", "")).strip()
        ]
        return assistant.chat(
            payload.experiment_id,
            payload.case_id,
            payload.question.strip(),
            history=history,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
