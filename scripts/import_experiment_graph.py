"""预检或导入 OPM 实验、算例、结果和水驱比较实例图谱。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.knowledge.neo4j.experiment_importer import Neo4jExperimentImporter


def main() -> int:
    """dry-run 默认只构建计划；显式省略该参数时才连接 Neo4j。"""
    parser = argparse.ArgumentParser(description="导入 PetroAgent 实验实例图谱")
    parser.add_argument("--dry-run", action="store_true", help="只校验并输出节点计数，不连接 Neo4j")
    parser.add_argument("--experiment", action="append", dest="experiments", help="限定实验 ID，可重复传入")
    args = parser.parse_args()
    importer = Neo4jExperimentImporter(ROOT)
    plan = importer.build_plan(args.experiments)
    print(json.dumps({"mode": "dry-run" if args.dry_run else "import", **plan.summary()}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings

    settings = Neo4jSettings.from_env(ROOT / ".env")
    with Neo4jClient(settings) as client:
        client.verify()
        summary = importer.import_all(client, args.experiments)
    print(json.dumps({"database": settings.database, "imported": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
