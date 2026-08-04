"""验证 Neo4j 只读查询的参数、结果映射和图视图。"""


class FakeRecord(dict):
    pass


class FakeResult:
    def __iter__(self):
        return iter([
            FakeRecord(
                source_id="salinity",
                source_name="矿化度",
                target_id="viscosity",
                target_name="黏度",
                relation_id="AFFECTS",
                relation_name="影响",
            )
        ])


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, *_args, **_kwargs):
        return FakeResult()


class FakeClient:
    def session(self):
        return FakeSession()


def test_concept_subgraph_maps_nodes_and_edges():
    from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService

    graph = Neo4jQueryService(FakeClient()).concept_subgraph(["salinity"])

    assert [node["id"] for node in graph["nodes"]] == ["salinity", "viscosity"]
    assert graph["edges"][0]["label"] == "影响"


class RankingSession(FakeSession):
    def run(self, *_args, **_kwargs):
        return [FakeRecord(
            case_id="polymer-1",
            polymer_concentration=1.5,
            injection_rate=200,
            final_cumulative_oil_m3=498828.0,
            incremental_cumulative_oil_m3=1474.3,
            incremental_oil_percent=0.296,
            baseline_case_id="water-200",
        )]


class RankingClient:
    def session(self):
        return RankingSession()


def test_experiment_rankings_returns_traceable_baseline():
    from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService

    rows = Neo4jQueryService(RankingClient()).experiment_rankings("polymer_sensitivity_v1")

    assert rows[0]["incremental_cumulative_oil_m3"] == 1474.3
    assert rows[0]["baseline_case_id"] == "water-200"


class ExplanationResult:
    def single(self):
        return FakeRecord(
            case_id="polymer-1",
            observations=[{"observation_id": "o1", "concept_id": "net_incremental_value"}],
            rule_executions=[{"rule_execution_id": "x1", "rule_id": "PF-ECO-002", "passed": False}],
            recommendation={"decision": "技术可行但经济未通过"},
            evidence={"source_id": "petroagent_techno_economic_model_v1"},
        )


class ExplanationSession(FakeSession):
    def run(self, *_args, **_kwargs):
        return ExplanationResult()


class ExplanationClient:
    def session(self):
        return ExplanationSession()


def test_scenario_explanation_maps_complete_chain():
    from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService

    payload = Neo4jQueryService(ExplanationClient()).scenario_explanation("polymer-1")

    assert payload["observations"][0]["concept_id"] == "net_incremental_value"
    assert payload["rule_executions"][0]["rule_id"] == "PF-ECO-002"
    assert payload["recommendation"]["decision"] == "技术可行但经济未通过"
