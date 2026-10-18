"""正文与流式执笔。路由层只做参数校验、错误翻译与事件转发。"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.runtime.llm import ChatFailure
from app.runtime.pricing import compute_cost, estimate_tokens
from app.services import text_service

router = APIRouter(prefix="/api", tags=["text"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(("场景不存在", "修订不存在", "草稿已被替换或删除")):
        return HTTPException(status_code=404, detail=message)
    if message.startswith(("当前没有可采纳的草稿", "场景的章节结构已损坏")):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/scenes/{scene_id}/generate")
async def generate_scene(
    scene_id: str, request: Request, session: Session = Depends(get_session)
):
    # 校验、上下文组装与模型解析全部在返回流之前完成：既不会先花钱，
    # 也能让「未绑定模型」这类错误走普通 JSON 状态码而不是 200 + error 事件。
    try:
        spec = text_service.prepare_generation(session, scene_id)
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

        def usage(content: str) -> tuple[int, int, float]:
            # 流式不请求服务商 usage（不赌 stream_options 兼容性），
            # 这两个数都是估算值，精确记账留 P3。
            prompt_tokens = spec.prompt_tokens
            completion_tokens = estimate_tokens(content)
            cost = compute_cost(prompt_tokens, completion_tokens, spec.prices)
            return prompt_tokens, completion_tokens, cost

        def finish(content: str, status: str, error: dict | None) -> tuple[str | None, int]:
            prompt_tokens, completion_tokens, cost = usage(content)
            duration = int((time.monotonic() - started) * 1000)
            draft_id = text_service.finalize_run(
                run_id,
                scene_id,
                content=content,
                status=status,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_estimate=cost,
                duration_ms=duration,
                error=error,
            )
            return draft_id, duration

        try:
            # 运行记录在生成器开头创建，而不是在路由里 —— 客户端若在流真正开始
            # 前就断开，不会留下一条永远停在 running 的孤儿记录。
            #
            # **`run` 的 yield 必须在这层 try 里面。** Starlette 在发送失败或
            # 被取消时不保证 aclose 响应体迭代器；生成器最终被 finalizer 关闭
            # 时，GeneratorExit 会落在这个 yield 上，而不是下面的循环里。若把
            # 它留在 try 外，收尾永远不执行，运行记录会永久停在 running。
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

            async for chunk in prepared.client.stream(
                prepared.config, prepared.prompt.messages, prepared.params
            ):
                if await request.is_disconnected():
                    raise asyncio.CancelledError
                parts.append(chunk)
                yield _sse("delta", {"text": chunk})

            content = "".join(parts)
            draft_id, duration = finish(content, "ok", None)
            finalized = True
            prompt_tokens, completion_tokens, cost = usage(content)
            yield _sse(
                "done",
                {
                    "run_id": run_id,
                    "status": "ok",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost_estimate": cost,
                    "duration_ms": duration,
                    "chars": len(content),
                    "draft_id": draft_id,
                },
            )
        except asyncio.CancelledError:
            # 作者停止或客户端断开：已收内容保留，状态记 cancelled；之后
            # 由 finally / 上游作用域退出关闭模型流，避免继续计费。
            if not finalized:
                finalized = True
                finish("".join(parts), "cancelled", None)
            raise
        except ChatFailure as exc:
            content = "".join(parts) or exc.partial_text
            if not finalized:
                finalized = True
                status = "partial" if content.strip() else "error"
                finish(
                    content,
                    status,
                    {"kind": exc.error.kind, "message": exc.error.message},
                )
            yield _sse(
                "error",
                {
                    "run_id": run_id,
                    "kind": exc.error.kind,
                    "message": exc.error.message,
                    "chars": len(content),
                },
            )
        except Exception as exc:  # noqa: BLE001
            content = "".join(parts)
            if not finalized:
                finalized = True
                finish(
                    content,
                    "partial" if content.strip() else "error",
                    {"kind": "runtime", "message": str(exc)},
                )
            yield _sse(
                "error",
                {
                    "run_id": run_id,
                    "kind": "runtime",
                    "message": str(exc),
                    "chars": len(content),
                },
            )
        finally:
            # 兜底覆盖「在 run / delta / done 的 yield 上被关闭」「CancelledError
            # 之外的 BaseException（如 GeneratorExit）」等路径。run_id 为 None
            # 说明 create_run 自己就失败了，没有可收敛的记录。
            if not finalized and run_id is not None:
                finalized = True
                finish("".join(parts), "cancelled", None)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
