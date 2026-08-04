"""把已验证的 OPM 实验摘要幂等写入 Neo4j 实例图谱。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .client import Neo4jClient


@dataclass(frozen=True)
class ExperimentImportPlan:
    """保存待写入节点；关系可由这些稳定主键确定性重建。"""

    analysis_cases: list[dict]
    experiments: list[dict]
    simulation_cases: list[dict]
    decks: list[dict]
    parameter_sets: list[dict]
    simulator_runs: list[dict]
    metric_results: list[dict]
    datasets: list[dict]
    reports: list[dict]
    comparisons: list[dict]
    economic_evaluations: list[dict]
    metric_observations: list[dict]
    rule_executions: list[dict]
    recommendations: list[dict]

    def summary(self) -> dict[str, int]:
        """返回 dry-run 和导入回执共用的节点计数。"""
        return {field: len(getattr(self, field)) for field in self.__dataclass_fields__}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str | None:
    """仅对存在的本地文件计算哈希，避免把 WSL 路径误判为本地文件。"""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Neo4jExperimentImporter:
    """从实验文件系统构建并写入轻量、可追溯的实例图谱。"""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.experiment_root = self.project_root / "outputs" / "experiments"

    def build_plan(self, experiment_ids: list[str] | None = None) -> ExperimentImportPlan:
        """读取实验摘要；默认选择显式声明配对关系的全部实验。"""
        if experiment_ids is None:
            manifests = {
                path.parent.name: _read_json(path)
                for path in sorted(self.experiment_root.glob("*/experiment_manifest.json"))
            }
            selected = {
                experiment_id
                for experiment_id, manifest in manifests.items()
                if manifest.get("paired_experiment_id")
            }
            # 旧实验清单可能早于配对字段生成，因此同时纳入被引用的实验。
            selected.update(
                manifest["paired_experiment_id"]
                for manifest in manifests.values()
                if manifest.get("paired_experiment_id")
            )
            experiment_ids = sorted(selected)
        experiments: list[dict] = []
        simulation_cases: list[dict] = []
        decks: dict[str, dict] = {}
        parameter_sets: list[dict] = []
        simulator_runs: list[dict] = []
        metric_results: list[dict] = []
        datasets: list[dict] = []
        reports: list[dict] = []
        analysis_cases: dict[str, dict] = {}

        for experiment_id in experiment_ids:
            directory = self.experiment_root / experiment_id
            manifest = _read_json(directory / "experiment_manifest.json")
            analysis_case_id = str(manifest.get("analysis_case_id") or "unknown")
            analysis_cases[analysis_case_id] = {
                "analysis_case_id": analysis_case_id,
                "name": analysis_case_id,
            }
            experiments.append({
                "experiment_id": experiment_id,
                "analysis_case_id": analysis_case_id,
                "data_nature": manifest.get("data_nature"),
                "design": manifest.get("design"),
                "case_count": int(manifest.get("case_count", 0)),
                "comparison_role": manifest.get("comparison_role", "scenario"),
                "paired_experiment_id": manifest.get("paired_experiment_id"),
                "updated_at": manifest.get("updated_at"),
            })
            base_deck = Path(str(manifest.get("base_deck", "")))
            local_base_deck = base_deck if base_deck.is_absolute() and base_deck.exists() else self._local_path(base_deck)
            deck_id = f"deck:{experiment_id}:base"
            decks[deck_id] = {
                "deck_id": deck_id,
                "experiment_id": experiment_id,
                "path": str(manifest.get("base_deck", "")),
                "sha256": _sha256(local_base_deck),
                "role": "base",
            }
            self._append_dataset_nodes(directory, experiment_id, datasets)

            report_path = directory / "analysis" / "report.md"
            if report_path.is_file():
                reports.append(self._file_node(report_path, f"report:{experiment_id}:sensitivity", experiment_id, "sensitivity"))

            for case_manifest_path in sorted((directory / "cases").glob("*/case_manifest.json")):
                case = _read_json(case_manifest_path)
                case_id = str(case["case_id"])
                parameters = case.get("parameters", {})
                simulation_cases.append({
                    "case_id": case_id,
                    "experiment_id": experiment_id,
                    "status": case.get("status"),
                    "finished_at": case.get("finished_at"),
                })
                parameter_sets.append({
                    "parameter_set_id": f"params:{case_id}",
                    "case_id": case_id,
                    "polymer_concentration": parameters.get("polymer_concentration"),
                    "injection_rate": parameters.get("injection_rate"),
                    "polymer_concentration_unit": manifest.get("parameter_units", {}).get("polymer_concentration"),
                    "injection_rate_unit": manifest.get("parameter_units", {}).get("injection_rate"),
                })
                flow = case.get("flow", {})
                simulator_runs.append({
                    "run_id": f"run:{case_id}",
                    "case_id": case_id,
                    "return_code": flow.get("return_code"),
                    "command": " ".join(str(item) for item in flow.get("command", [])),
                    "manifest_file": flow.get("manifest_file"),
                    "flow_reused": bool(case.get("flow_reused", False)),
                })
                labels = case.get("labels", {})
                metric_results.append({
                    "metric_result_id": f"metrics:{case_id}",
                    "case_id": case_id,
                    **{key: value for key, value in labels.items() if isinstance(value, (int, float))},
                })

        comparisons = self._comparison_nodes(experiment_ids)
        economic_evaluations = self._economic_evaluation_nodes(experiment_ids)
        metric_observations, rule_executions, recommendations = self._semantic_nodes(experiment_ids)
        comparison_report = self.experiment_root / "polymer_sensitivity_v1" / "analysis" / "waterflood_comparison" / "report.md"
        if comparison_report.is_file() and "polymer_sensitivity_v1" in experiment_ids:
            reports.append(self._file_node(
                comparison_report,
                "report:polymer_sensitivity_v1:waterflood_comparison",
                "polymer_sensitivity_v1",
                "waterflood_comparison",
            ))
        economics_dir = self.experiment_root / "polymer_sensitivity_v1" / "analysis" / "techno_economics"
        if "polymer_sensitivity_v1" in experiment_ids:
            for name, role in (
                ("case_economics.csv", "techno_economic_cases"),
                ("constraint_evaluations.csv", "constraint_evaluations"),
                ("scenario_rankings.csv", "scenario_rankings"),
                ("metric_observations.csv", "metric_observations"),
                ("rule_executions.csv", "rule_executions"),
                ("recommendations.csv", "recommendations"),
            ):
                path = economics_dir / name
                if path.is_file():
                    datasets.append(self._analysis_dataset_node(path, "polymer_sensitivity_v1", role))
            for name, role in (("report.md", "techno_economics"), ("ranking_report.md", "scenario_ranking")):
                path = economics_dir / name
                if path.is_file():
                    reports.append(self._file_node(path, f"report:polymer_sensitivity_v1:{role}", "polymer_sensitivity_v1", role))
        return ExperimentImportPlan(
            list(analysis_cases.values()), experiments, simulation_cases,
            list(decks.values()), parameter_sets, simulator_runs, metric_results,
            datasets, reports, comparisons, economic_evaluations,
            metric_observations, rule_executions, recommendations,
        )

    def _local_path(self, path: Path) -> Path:
        """把项目内记录的相对路径或 WSL 项目路径映射回当前工作区。"""
        text = str(path).replace("\\", "/")
        marker = "/petro-agent/"
        if marker in text:
            return self.project_root / text.split(marker, 1)[1]
        return self.project_root / path

    def _file_node(self, path: Path, node_id: str, experiment_id: str, role: str) -> dict:
        return {
            "report_id": node_id,
            "experiment_id": experiment_id,
            "role": role,
            "path": str(path.relative_to(self.project_root)).replace("\\", "/"),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }

    def _append_dataset_nodes(self, directory: Path, experiment_id: str, target: list[dict]) -> None:
        """只登记文件级元数据；完整时间序列继续保存在 CSV 中。"""
        for name, role in (("cases.csv", "case_summary"), ("time_series.csv", "time_series")):
            path = directory / "dataset" / name
            if not path.is_file():
                continue
            target.append({
                "dataset_id": f"dataset:{experiment_id}:{role}",
                "experiment_id": experiment_id,
                "role": role,
                "path": str(path.relative_to(self.project_root)).replace("\\", "/"),
                "sha256": _sha256(path),
                "row_count": int(len(pd.read_csv(path))),
                "size_bytes": path.stat().st_size,
            })

    def _analysis_dataset_node(self, path: Path, experiment_id: str, role: str) -> dict:
        """登记分析 CSV 的文件摘要，不把完整明细复制进图数据库。"""
        return {
            "dataset_id": f"dataset:{experiment_id}:{role}",
            "experiment_id": experiment_id,
            "role": role,
            "path": str(path.relative_to(self.project_root)).replace("\\", "/"),
            "sha256": _sha256(path),
            "row_count": int(len(pd.read_csv(path))),
            "size_bytes": path.stat().st_size,
        }

    def _comparison_nodes(self, experiment_ids: list[str]) -> list[dict]:
        path = self.experiment_root / "polymer_sensitivity_v1" / "analysis" / "waterflood_comparison" / "paired_case_metrics.csv"
        if not path.is_file() or not {"polymer_sensitivity_v1", "waterflood_baseline_v1"} <= set(experiment_ids):
            return []
        rows = pd.read_csv(path)
        return [{
            "comparison_id": f"comparison:{row.polymer_case_id}:vs:{row.waterflood_case_id}",
            "polymer_case_id": row.polymer_case_id,
            "waterflood_case_id": row.waterflood_case_id,
            "incremental_cumulative_oil_m3": float(row.incremental_cumulative_oil_m3),
            "incremental_oil_percent": float(row.incremental_oil_percent),
            "water_cut_change_percentage_points": float(row.water_cut_change_percentage_points),
            "incremental_field_pressure_bar": float(row.incremental_field_pressure_bar),
            "source_dataset_path": str(path.relative_to(self.project_root)).replace("\\", "/"),
        } for row in rows.itertuples(index=False)]

    def _economic_evaluation_nodes(self, experiment_ids: list[str]) -> list[dict]:
        """把方案级排名摘要转换为轻量节点，完整计算列仍保留在 CSV。"""
        path = self.experiment_root / "polymer_sensitivity_v1" / "analysis" / "techno_economics" / "scenario_rankings.csv"
        if not path.is_file() or "polymer_sensitivity_v1" not in experiment_ids:
            return []
        rows = pd.read_csv(path)
        fields = [
            "scenario_rank", "ranking_tier", "recommendation",
            "polymer_mass_kg", "polymer_mass_tonnes", "peak_daily_polymer_kg_day",
            "incremental_oil_m3", "incremental_oil_bbl", "net_incremental_value",
            "break_even_polymer_price_per_kg", "break_even_oil_price_per_bbl",
            "technically_feasible", "economically_positive",
            "constraint_violation_count", "constraint_violations",
            "assumption_status", "currency",
        ]
        evaluations = []
        for row in rows.to_dict(orient="records"):
            # Neo4j 属性不接收 NaN；无定义的盈亏平衡值直接省略，而不是写入伪数值。
            properties = {key: row[key] for key in fields if key in row and pd.notna(row[key])}
            evaluations.append({
                "economic_evaluation_id": f"economics:{row['polymer_case_id']}",
                "case_id": row["polymer_case_id"],
                "source_dataset_path": str(path.relative_to(self.project_root)).replace("\\", "/"),
                **properties,
            })
        return evaluations

    def _semantic_nodes(self, experiment_ids: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
        """读取分析阶段生成的规则执行、指标语义绑定和推荐解释。"""
        directory = self.experiment_root / "polymer_sensitivity_v1" / "analysis" / "techno_economics"
        if "polymer_sensitivity_v1" not in experiment_ids:
            return [], [], []

        def read_rows(name: str) -> list[dict]:
            path = directory / name
            if not path.is_file():
                return []
            rows = []
            for row in pd.read_csv(path).to_dict(orient="records"):
                rows.append({key: value for key, value in row.items() if pd.notna(value)})
            return rows

        observations = read_rows("metric_observations.csv")
        executions = read_rows("rule_executions.csv")
        recommendations = read_rows("recommendations.csv")
        for item in recommendations:
            raw_ids = item.pop("justifying_execution_ids", "[]")
            item["justifying_execution_ids"] = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
        return observations, executions, recommendations

    def import_all(self, client: "Neo4jClient", experiment_ids: list[str] | None = None) -> dict[str, int]:
        """使用唯一约束和 MERGE 写入节点及血缘关系。"""
        plan = self.build_plan(experiment_ids)
        with client.session() as session:
            self._create_constraints(session)
            for label, key, rows in (
                ("AnalysisCase", "analysis_case_id", plan.analysis_cases),
                ("Experiment", "experiment_id", plan.experiments),
                ("SimulationCase", "case_id", plan.simulation_cases),
                ("Deck", "deck_id", plan.decks),
                ("ParameterSet", "parameter_set_id", plan.parameter_sets),
                ("SimulatorRun", "run_id", plan.simulator_runs),
                ("MetricResult", "metric_result_id", plan.metric_results),
                ("Dataset", "dataset_id", plan.datasets),
                ("Report", "report_id", plan.reports),
                ("Comparison", "comparison_id", plan.comparisons),
                ("EconomicEvaluation", "economic_evaluation_id", plan.economic_evaluations),
                ("MetricObservation", "observation_id", plan.metric_observations),
                ("RuleExecution", "rule_execution_id", plan.rule_executions),
                ("Recommendation", "recommendation_id", plan.recommendations),
            ):
                self._merge_nodes(session, label, key, rows)
            self._write_relationships(session, plan)
        return plan.summary()

    @staticmethod
    def _create_constraints(session) -> None:
        for label, key in (
            ("AnalysisCase", "analysis_case_id"), ("Experiment", "experiment_id"),
            ("SimulationCase", "case_id"), ("Deck", "deck_id"),
            ("ParameterSet", "parameter_set_id"), ("SimulatorRun", "run_id"),
            ("MetricResult", "metric_result_id"), ("Dataset", "dataset_id"),
            ("Report", "report_id"), ("Comparison", "comparison_id"),
            ("EconomicEvaluation", "economic_evaluation_id"),
            ("MetricObservation", "observation_id"),
            ("RuleExecution", "rule_execution_id"),
            ("Recommendation", "recommendation_id"),
        ):
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
            ).consume()

    @staticmethod
    def _merge_nodes(session, label: str, key: str, rows: list[dict]) -> None:
        if not rows:
            return
        session.run(
            f"UNWIND $rows AS row MERGE (n:{label} {{{key}: row.{key}}}) SET n += row",
            rows=rows,
        ).consume()

    @staticmethod
    def _write_relationships(session, plan: ExperimentImportPlan) -> None:
        """关系类型固定在代码中，不接受外部输入拼接 Cypher。"""
        queries = [
            ("UNWIND $rows AS row MATCH (a:AnalysisCase {analysis_case_id: row.analysis_case_id}), (e:Experiment {experiment_id: row.experiment_id}) MERGE (a)-[:HAS_EXPERIMENT]->(e)", plan.experiments),
            ("UNWIND $rows AS row MATCH (e:Experiment {experiment_id: row.experiment_id}), (c:SimulationCase {case_id: row.case_id}) MERGE (e)-[:HAS_CASE]->(c)", plan.simulation_cases),
            ("UNWIND $rows AS row MATCH (e:Experiment {experiment_id: row.experiment_id}), (d:Deck {deck_id: row.deck_id}) MERGE (e)-[:USES_DECK]->(d)", plan.decks),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (p:ParameterSet {parameter_set_id: row.parameter_set_id}) MERGE (c)-[:HAS_PARAMETER_SET]->(p)", plan.parameter_sets),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (r:SimulatorRun {run_id: row.run_id}) MERGE (c)-[:EXECUTED_AS]->(r)", plan.simulator_runs),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (m:MetricResult {metric_result_id: row.metric_result_id}) MERGE (c)-[:HAS_RESULT]->(m)", plan.metric_results),
            ("UNWIND $rows AS row MATCH (e:Experiment {experiment_id: row.experiment_id}), (d:Dataset {dataset_id: row.dataset_id}) MERGE (e)-[:GENERATED_DATASET]->(d)", plan.datasets),
            ("UNWIND $rows AS row MATCH (e:Experiment {experiment_id: row.experiment_id}), (r:Report {report_id: row.report_id}) MERGE (e)-[:GENERATED_REPORT]->(r)", plan.reports),
            ("UNWIND $rows AS row MATCH (p:SimulationCase {case_id: row.polymer_case_id}), (c:Comparison {comparison_id: row.comparison_id}), (w:SimulationCase {case_id: row.waterflood_case_id}) MERGE (p)-[:HAS_COMPARISON]->(c) MERGE (c)-[:USES_BASELINE]->(w)", plan.comparisons),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (x:EconomicEvaluation {economic_evaluation_id: row.economic_evaluation_id}) MERGE (c)-[:HAS_ECONOMIC_EVALUATION]->(x)", plan.economic_evaluations),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (o:MetricObservation {observation_id: row.observation_id}), (concept:Concept {concept_id: row.concept_id}) MERGE (c)-[:HAS_OBSERVATION]->(o) MERGE (o)-[:OBSERVES]->(concept)", plan.metric_observations),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (x:RuleExecution {rule_execution_id: row.rule_execution_id}), (r:Rule {rule_id: row.rule_id}) MERGE (c)-[:EXECUTED_RULE]->(x) MERGE (x)-[:EXECUTES]->(r)", plan.rule_executions),
            ("UNWIND $rows AS row MATCH (x:RuleExecution {rule_execution_id: row.rule_execution_id}), (s:Source {source_id: row.evidence_source_id}) MERGE (x)-[:SUPPORTED_BY]->(s)", plan.rule_executions),
            ("UNWIND $rows AS row MATCH (c:SimulationCase {case_id: row.case_id}), (r:Recommendation {recommendation_id: row.recommendation_id}), (s:Source {source_id: row.evidence_source_id}) MERGE (c)-[:PRODUCES_RECOMMENDATION]->(r) MERGE (r)-[:SUPPORTED_BY]->(s)", plan.recommendations),
        ]
        for query, rows in queries:
            if rows:
                session.run(query, rows=rows).consume()
        if plan.recommendations:
            justification_rows = [
                {"recommendation_id": item["recommendation_id"], "rule_execution_id": execution_id}
                for item in plan.recommendations
                for execution_id in item.get("justifying_execution_ids", [])
            ]
            session.run(
                "UNWIND $rows AS row MATCH (r:Recommendation {recommendation_id: row.recommendation_id}), (x:RuleExecution {rule_execution_id: row.rule_execution_id}) MERGE (r)-[:JUSTIFIED_BY]->(x)",
                rows=justification_rows,
            ).consume()
        if plan.rule_executions and plan.metric_observations:
            # 依据规则 USES_INPUT 的概念连接同一算例观测，形成可查询的实际输入证据链。
            session.run(
                "MATCH (x:RuleExecution)<-[:EXECUTED_RULE]-(c:SimulationCase)-[:HAS_OBSERVATION]->(o:MetricObservation)-[:OBSERVES]->(concept:Concept), (x)-[:EXECUTES]->(:Rule)-[:USES_INPUT]->(concept) MERGE (x)-[:USES_OBSERVATION]->(o)"
            ).consume()
