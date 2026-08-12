"""开发启动器：python backend/run.py"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import uvicorn  # noqa: E402

from config import SETTINGS  # noqa: E402

if __name__ == "__main__":
    print(f"[AlienLearn] http://{SETTINGS.host}:{SETTINGS.port}  （改端口：.env 里设 PORT）")
    uvicorn.run(
        "main:app",
        host=SETTINGS.host,
        port=SETTINGS.port,
        reload=True,
        reload_dirs=[str(HERE)],
    )
