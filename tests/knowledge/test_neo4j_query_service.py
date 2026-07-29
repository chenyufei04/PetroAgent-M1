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
