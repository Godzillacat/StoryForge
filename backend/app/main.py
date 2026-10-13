from __future__ import annotations

from fastapi import FastAPI

from app import config
from app.db.session import init_db

app = FastAPI(title="StoryForge", version="0.1.0")
init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}
