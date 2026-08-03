"""解析 Eclipse/OPM Deck，并提取分析所需的关键字与引用关系。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


INCLUDE_PATTERN = re.compile(r"\bINCLUDE\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)
KEYWORD_PATTERN = re.compile(r"^\s*([A-Z][A-Z0-9_-]{1,15})\b")


@dataclass(frozen=True)
class DeckInspection:
    root_file: str
    files: list[str]
    keywords: list[str]
    missing_includes: list[str]


def inspect_deck(root: Path) -> DeckInspection:
    visited: set[Path] = set()
    missing: list[str] = []
    keywords: set[str] = set()

    def walk(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            clean = line.split("--", 1)[0]
            match = KEYWORD_PATTERN.match(clean)
            if match:
                keywords.add(match.group(1).upper())
        for include in INCLUDE_PATTERN.findall(text):
            child = (path.parent / include).resolve()
            if child.exists():
                walk(child)
            else:
                missing.append(str(child))

    walk(root)
    return DeckInspection(
        root_file=str(root.resolve()),
        files=sorted(str(path) for path in visited),
        keywords=sorted(keywords),
        missing_includes=sorted(set(missing)),
    )
