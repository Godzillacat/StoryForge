"""FastAPI 装配入口。

P1a 只挂 /api/health；后续任务的 router 依次追加到 include_router 区。
"""

from __future__ import annotations

from fastapi import FastAPI

from app import config

app = FastAPI(title="StoryForge", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}
