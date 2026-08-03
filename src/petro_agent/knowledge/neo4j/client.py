"""封装 Neo4j 连接配置与驱动生命周期管理。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


@dataclass(frozen=True)
class Neo4jSettings:
    uri: str
    user: str
    password: str
    database: str = "petro"

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "Neo4jSettings":
        """读取统一连接变量；Docker 与原直接启动方式共用此配置入口。"""
        load_dotenv(dotenv_path=env_path)
        # 兼容旧方式（保留）：直接启动的 Neo4j 仍可继续使用 localhost 或虚拟机地址。
        # Docker 模式同样通过宿主机映射端口连接，因此不改变现有调用方。
        values = {
            "uri": os.getenv("NEO4J_URI"),
            "user": os.getenv("NEO4J_USER"),
            "password": os.getenv("NEO4J_PASSWORD"),
            "database": os.getenv("NEO4J_DATABASE", "petro"),
        }
        missing = [
            env_name
            for field, env_name in (
                ("uri", "NEO4J_URI"),
                ("user", "NEO4J_USER"),
                ("password", "NEO4J_PASSWORD"),
            )
            if not values[field]
        ]
        if missing:
            raise ValueError(f"缺少 Neo4j 环境变量: {', '.join(missing)}")
        return cls(**values)


class Neo4jClient:
    def __init__(self, settings: Neo4jSettings):
        self.settings = settings
        self.driver = GraphDatabase.driver(
            settings.uri,
            auth=(settings.user, settings.password),
        )

    def verify(self) -> None:
        self.driver.verify_connectivity()
        with self.driver.session(database=self.settings.database) as session:
            session.run("RETURN 1 AS ok").single(strict=True)

    def session(self):
        return self.driver.session(database=self.settings.database)

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
