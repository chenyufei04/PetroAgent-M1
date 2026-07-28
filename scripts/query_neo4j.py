"""Print Neo4j graph evidence as readable triples."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings
from petro_agent.knowledge.neo4j.query_service import Neo4jQueryService


def main() -> None:
    settings = Neo4jSettings.from_env(ROOT / ".env")
    with Neo4jClient(settings) as client:
        service = Neo4jQueryService(client)
        counts = service.graph_counts()
        triples = service.domain_triples()

    print(
        f"Neo4j 图谱: database={settings.database}, "
        f"节点={counts['nodes']}, 关系={counts['relationships']}"
    )
    print(f"概念关系: 共 {len(triples)} 条")
    for index, row in enumerate(triples, start=1):
        print(
            f"{index:02d}. {row['subject']} [{row['subject_id']}] "
            f"--{row['relation']} [{row['relation_id']}]--> "
            f"{row['object']} [{row['object_id']}]"
        )


if __name__ == "__main__":
    main()
