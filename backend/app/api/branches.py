"""场景分支接口。路由层只做参数校验、错误翻译与事件转发。"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.schemas import BranchCreate, BranchUpdate, TextWrite
from app.db.models import SceneBranch
from app.db.session import get_session
from app.runtime.llm import ChatFailure, StreamUsage
from app.runtime.pricing import compute_cost, estimate_tokens
from app.services import branch_service, text_service

router = APIRouter(prefix="/api", tags=["branches"])

_MISSING_PREFIXES = ("场景不存在", "分支不存在", "分支不属于这个场景")


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(_MISSING_PREFIXES):
        return HTTPException(status_code=404, detail=message)
    if (
        "已锁定" in message
        or "已锁定的段落" in message
        or "没有可采纳的草稿" in message
        or "未处理的 A/B" in message
    ):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/scenes/{scene_id}/branches")
def list_branches(scene_id: str, session: Session = Depends(get_session)) -> list[dict]:
    try:
        return branch_service.list_branches(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/scenes/{scene_id}/branches", status_code=201)
def create_branch(
    scene_id: str, payload: BranchCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        row = branch_service.create_branch(
            session, scene_id, payload.name, payload.note
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    return branch_service.serialize_branch_detail(row)


# ---- A/B 并排生成 ----


@router.post("/scenes/{scene_id}/ab", status_code=201)
def create_ab(scene_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return branch_service.ab_create(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/ab")
def current_ab(scene_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return branch_service.ab_current(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/scenes/{scene_id}/ab/{branch_id}/adopt")
def adopt_ab(
    scene_id: str, branch_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return branch_service.ab_adopt(session, scene_id, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/scenes/{scene_id}/ab/{branch_id}/discard")
def discard_ab(
    scene_id: str, branch_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return branch_service.ab_discard(session, scene_id, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/branches/{branch_id}")
def get_branch(branch_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return branch_service.get_branch(session, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.patch("/branches/{branch_id}")
def update_branch(
    branch_id: str, payload: BranchUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        return branch_service.update_branch(
            session, branch_id, name=payload.name, note=payload.note
        )
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.put("/branches/{branch_id}/body")
def save_body(
    branch_id: str, payload: TextWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        return branch_service.save_branch_body(session, branch_id, payload.content)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.put("/branches/{branch_id}/draft")
def save_draft(
    branch_id: str, payload: TextWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        return branch_service.save_branch_draft(session, branch_id, payload.content)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/branches/{branch_id}/revisions")
def list_revisions(branch_id: str, session: Session = Depends(get_session)) -> list[dict]:
    try:
        return branch_service.list_branch_revisions(session, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/branches/{branch_id}/adopt")
def adopt_draft(branch_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return branch_service.adopt_branch_draft(session, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/branches/{branch_id}/merge")
def merge_branch(branch_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return branch_service.merge_branch(session, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.delete("/branches/{branch_id}", status_code=204)
def discard_branch(branch_id: str, session: Session = Depends(get_session)) -> None:
    try:
        branch_service.discard_branch(session, branch_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/branches/{branch_id}/generate")
async def generate_branch(
    branch_id: str, request: Request, session: Session = Depends(get_session)
):
    """与主版完全相同的链路，只是结果写进分支的草稿。"""
    row = session.get(SceneBranch, branch_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"分支不存在：{branch_id}")
    try:
        spec = text_service.prepare_generation(session, row.scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc

    prepared = spec.prepared
    if prepared.prompt.error:
        raise HTTPException(status_code=400, detail=prepared.prompt.error["message"])

    async def events():
        parts: list[str] = []
        started = time.monotonic()
        finalized = False
        run_id: str | None = None
        stream_usage: StreamUsage | None = None

        def usage(content: str) -> tuple[int, int, float, str]:
            if stream_usage is not None:
                return (
                    stream_usage.prompt_tokens or spec.prompt_tokens,
                    stream_usage.completion_tokens,
                    compute_cost(
                        stream_usage.prompt_tokens or spec.prompt_tokens,
                        stream_usage.completion_tokens,
                        spec.prices,
                    ),
                    "provider",
                )
            completion = estimate_tokens(content)
            return (
                spec.prompt_tokens,
                completion,
                compute_cost(spec.prompt_tokens, completion, spec.prices),
                "estimated",
            )

        def finish(content: str, status: str, error: dict | None) -> None:
            prompt_tokens, completion_tokens, cost, source = usage(content)
            text_service.finalize_run(
                run_id,
                row.scene_id,
                content=content,
                status=status,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_estimate=cost,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=error,
                usage_source=source,
                branch_id=branch_id,
            )

        try:
            run_id = text_service.create_run(spec)
            yield _sse(
                "run",
                {
                    "run_id": run_id,
                    "model": spec.model,
                    "agent": spec.agent_name,
                    "estimated_tokens": spec.prompt_tokens,
                    "trimmed": spec.trimmed,
                },
            )
            async for event in prepared.client.stream(
                prepared.config, prepared.prompt.messages, prepared.params
            ):
                if await request.is_disconnected():
                    raise asyncio.CancelledError
                if isinstance(event, StreamUsage):
                    stream_usage = event
                    continue
                parts.append(event.text)
                yield _sse("delta", {"text": event.text})

            content = "".join(parts)
            finish(content, "ok", None)
            finalized = True
            yield _sse("done", {"chars": len(content), "draft": True})
        except asyncio.CancelledError:
            if not finalized and run_id is not None:
                finish("".join(parts), "cancelled", None)
                finalized = True
            raise
        except ChatFailure as exc:
            if not finalized and run_id is not None:
                finish(
                    "".join(parts),
                    "error",
                    {"kind": exc.kind, "message": exc.message},
                )
                finalized = True
            yield _sse("error", {"kind": exc.kind, "message": exc.message})
        except Exception as exc:  # noqa: BLE001
            if not finalized and run_id is not None:
                finish(
                    "".join(parts),
                    "error",
                    {"kind": "unknown", "message": str(exc)},
                )
                finalized = True
            yield _sse("error", {"kind": "unknown", "message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")
