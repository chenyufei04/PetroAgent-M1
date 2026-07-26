from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


DATASETS = {
    "polymer_simple2D": ("https://github.com/OPM/opm-tests.git", "polymer_simple2D"),
    "spe9": ("https://github.com/OPM/opm-data.git", "spe9"),
}


def fetch(name: str, destination: Path) -> Path:
    repository, subdirectory = DATASETS[name]
    target = destination / name
    if target.exists():
        raise FileExistsError(f"目标已存在，请先移动或改名: {target}")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="petro-agent-opm-") as temp:
        checkout = Path(temp) / "repo"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", repository, str(checkout)],
            check=True,
        )
        subprocess.run(["git", "-C", str(checkout), "sparse-checkout", "set", subdirectory], check=True)
        source = checkout / subdirectory
        if not source.exists():
            raise FileNotFoundError(f"上游仓库中未找到目录: {subdirectory}")
        shutil.copytree(source, target)
        revision = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        (target / "UPSTREAM_REVISION.txt").write_text(
            f"repository={repository}\nrevision={revision}\nsubdirectory={subdirectory}\n",
            encoding="utf-8",
        )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Download selected official OPM case directories")
    parser.add_argument("datasets", nargs="+", choices=sorted(DATASETS))
    parser.add_argument("--destination", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    for dataset in args.datasets:
        print(fetch(dataset, args.destination))


if __name__ == "__main__":
    main()

