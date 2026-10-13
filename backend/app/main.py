from __future__ import annotations

from fastapi import FastAPI

from app import config
from app.api import agents, architecture, ideas, projects, providers, runs, tools
from app.db.session import SessionLocal, init_db
from app.services.seed_service import seed_agents, seed_tools

app = FastAPI(title="StoryForge", version="0.1.0")


@app.on_event("startup")
def _bootstrap() -> None:
    init_db()
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}


for module in (projects, ideas, architecture, agents, runs, tools, providers):
    app.include_router(module.router)
