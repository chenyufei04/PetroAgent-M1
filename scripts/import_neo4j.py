"""把版本化 YAML 知识图谱导入 Neo4j。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.knowledge.neo4j.importer import Neo4jKnowledgeImporter


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 PetroAgent YAML 知识图谱")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只校验并统计待导入内容，不连接或写入 Neo4j",
    )
    args = parser.parse_args()

    importer = Neo4jKnowledgeImporter(ROOT / "knowledge_graph")
    plan = importer.build_plan()
    print("待导入:", plan.summary())
    if args.dry_run:
        print("Dry run 完成，未写入 Neo4j")
        return

    from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings

    settings = Neo4jSettings.from_env(ROOT / ".env")
    with Neo4jClient(settings) as client:
        client.verify()
        summary = importer.import_all(client)
    print(f"Neo4j 导入完成: database={settings.database}, {summary}")


if __name__ == "__main__":
    main()
