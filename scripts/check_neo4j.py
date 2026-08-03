"""检查 Docker 或直接启动模式下的 Neo4j 连接和目标数据库。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petro_agent.knowledge.neo4j.client import Neo4jClient, Neo4jSettings


def main() -> int:
    """验证 Bolt 连通性，并输出不包含密码的诊断信息。"""
    settings = Neo4jSettings.from_env(ROOT / ".env")
    deployment_mode = os.getenv("NEO4J_DEPLOYMENT_MODE", "direct")
    result = {
        "deployment_mode": deployment_mode,
        "uri": settings.uri,
        "user": settings.user,
        "database": settings.database,
        "available": False,
        "server": None,
        "error": None,
    }
    try:
        with Neo4jClient(settings) as client:
            client.verify()
            with client.session() as session:
                record = session.run(
                    "CALL dbms.components() YIELD name, versions "
                    "RETURN name, versions[0] AS version LIMIT 1"
                ).single(strict=True)
            result["available"] = True
            result["server"] = dict(record)
    except Exception as exc:
        result["error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
