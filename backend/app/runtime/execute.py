"""运行时编排：槽位收集 → 预算裁剪 → 提示词渲染 → 模型调用 → 契约校验 → 落库产物。

这里不碰数据库、不碰 FastAPI，只产出一个 RunResult，由 services 层负责写库。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.runtime.context import SlotSource, build_context
from app.runtime.llm import ChatClient, ChatConfig, ChatFailure
from app.runtime.pricing import compute_cost, estimate_tokens
from app.runtime.render import MissingVariableError, render
from app.runtime.schema import apply_contract


@dataclass(frozen=True)
class ExecuteInput:
    project_id: str
    agent_id: str
    version_id: str
    provider_id: str | None
    model: str
    base_url: str
    api_key: str
    params: dict
    system_prompt: str
    context_slots: list[str]
    output_schema: dict | None
    token_budget: int
    prices: dict | None = None


@dataclass(frozen=True)
class RunResult:
    rendered_prompt: str
    raw_output: str
    parsed: Any | None
    structured: bool
    parse_error: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float
    duration_ms: int
    status: str  # ok | partial | error
    error: dict | None
    trimmed: dict[str, str]


def _failure(
    inp: ExecuteInput,
    started: float,
    message: str,
    *,
    kind: str = "runtime",
    status: str = "error",
    rendered_prompt: str = "",
    raw_output: str = "",
    trimmed: dict[str, str] | None = None,
) -> RunResult:
    prompt_tokens = estimate_tokens(rendered_prompt)
    completion_tokens = estimate_tokens(raw_output)
    return RunResult(
        rendered_prompt=rendered_prompt,
        raw_output=raw_output,
        parsed=None,
        structured=False,
        parse_error=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate=compute_cost(prompt_tokens, completion_tokens, inp.prices),
        duration_ms=int((time.monotonic() - started) * 1000),
        status=status,
        error={"kind": kind, "message": message},
        trimmed=trimmed or {},
    )


async def execute_run(inp: ExecuteInput, source: SlotSource, client: ChatClient) -> RunResult:
    started = time.monotonic()

    bundle = build_context(inp.context_slots, source, inp.token_budget)
    try:
        rendered_prompt = render(inp.system_prompt, bundle.contents)
    except MissingVariableError as exc:
        return _failure(inp, started, str(exc), kind="template", trimmed=bundle.trimmed)

    messages = [{"role": "user", "content": rendered_prompt}]
    config = ChatConfig(base_url=inp.base_url, api_key=inp.api_key, model=inp.model)

    try:
        chat = await client.complete(config, messages, inp.params)
    except ChatFailure as exc:
        # 失败不丢内容：已收到的片段照样返回给作者（上位文档 §4.10）
        return _failure(
            inp,
            started,
            exc.error.message,
            kind=exc.error.kind,
            status="partial" if exc.partial_text else "error",
            rendered_prompt=rendered_prompt,
            raw_output=exc.partial_text,
            trimmed=bundle.trimmed,
        )

    parsed, structured, parse_error = apply_contract(chat.text, inp.output_schema)
    return RunResult(
        rendered_prompt=rendered_prompt,
        raw_output=chat.text,
        parsed=parsed,
        structured=structured,
        parse_error=parse_error,
        prompt_tokens=chat.prompt_tokens,
        completion_tokens=chat.completion_tokens,
        cost_estimate=compute_cost(chat.prompt_tokens, chat.completion_tokens, inp.prices),
        duration_ms=int((time.monotonic() - started) * 1000),
        status="ok",
        error=None,
        trimmed=bundle.trimmed,
    )
