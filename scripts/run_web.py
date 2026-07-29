from pathlib import Path
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


if __name__ == "__main__":
    uvicorn.run(
        "petro_agent.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        app_dir=str(SRC),
    )
