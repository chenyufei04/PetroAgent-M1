"""加载并校验案例配置，统一解析项目相对路径。"""

from __future__ import annotations

from pathlib import Path

import yaml


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"配置文件必须是 YAML 对象: {path}")
    return value
