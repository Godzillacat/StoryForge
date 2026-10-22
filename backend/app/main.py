from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import config
from app.api import (
    agents,
    architecture,
    audit,
    batches,
    chapters,
    export,
    foreshadows,
    ideas,
    impact,
    logic,
    locks,
    pipeline,
    projects,
    providers,
    runs,
    search,
    snapshots,
    slots,
    text,
    timeline,
    tools,
    world,
    writeback,
)
from app.db.session import SessionLocal, init_db
from app.services.batch_service import recover_jobs
from app.services.pipeline_service import recover_runs
from app.services.seed_service import seed_agents, seed_tools


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """建表并预置阵容与工具库。两个预置函数都是幂等的，每次启动跑一遍是安全的。"""
    init_db()
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)
    # 进程内 worker 不跨重启：未完成的任务恢复为暂停，由作者手动继续。
    recover_jobs()
    recover_runs()
    yield


app = FastAPI(title="StoryForge", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}


for module in (
    projects,
    ideas,
    architecture,
    agents,
    runs,
    tools,
    providers,
    search,
    slots,
    world,
    timeline,
    chapters,
    foreshadows,
    text,
    audit,
    logic,
    writeback,
    batches,
    export,
    pipeline,
    locks,
    impact,
    snapshots,
):
    app.include_router(module.router)
