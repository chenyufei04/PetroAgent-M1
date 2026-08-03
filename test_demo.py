"""供人工快速检查环境变量和演示数据路径的辅助脚本。"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE", "petro")

driver = GraphDatabase.driver(
    uri,
    auth=(user, password),
)

try:
    # 验证服务器连接和账号密码
    driver.verify_connectivity()

    # 明确在 petro 数据库中执行查询
    with driver.session(database=database) as session:
        result = session.run(
            """
            RETURN
                $database AS database,
                'Neo4j connection successful' AS message
            """,
            database=database,
        )

        print(result.single().data())

finally:
    driver.close()
