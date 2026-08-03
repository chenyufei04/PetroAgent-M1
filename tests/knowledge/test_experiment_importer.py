"""验证实验实例图谱计划、文件摘要和幂等写入语句。"""

from pathlib import Path

from petro_agent.knowledge.neo4j.experiment_importer import Neo4jExperimentImporter


ROOT = Path(__file__).resolve().parents[2]


class FakeResult:
    def consume(self):
        return None


class FakeSession:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.fake_session = FakeSession()

    def session(self):
        return self.fake_session


def test_experiment_plan_contains_paired_runs_without_time_points():
    plan = Neo4jExperimentImporter(ROOT).build_plan()

    assert plan.summary() == {
        "analysis_cases": 1,
        "experiments": 2,
        "simulation_cases": 12,
        "decks": 2,
        "parameter_sets": 12,
        "simulator_runs": 12,
        "metric_results": 12,
        "datasets": 4,
        "reports": 2,
        "comparisons": 9,
    }
    assert {item["row_count"] for item in plan.datasets} >= {3, 9, 693, 2098}
    assert max(item["incremental_cumulative_oil_m3"] for item in plan.comparisons) > 1400


def test_import_uses_constraints_and_merge_statements():
    importer = Neo4jExperimentImporter(ROOT)
    client = FakeClient()

    importer.import_all(client)

    queries = "\n".join(query for query, _ in client.fake_session.calls)
    assert "CREATE CONSTRAINT" in queries
    assert "MERGE (n:Experiment" in queries
    assert "MERGE (p)-[:HAS_COMPARISON]->(c)" in queries
