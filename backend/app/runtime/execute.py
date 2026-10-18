"""运行时编排：槽位收集 → 预算裁剪 → 提示词渲染 → 模型调用 → 契约校验。

这里不碰数据库、不碰 FastAPI。准备步骤与执行步骤拆开，流式路径复用同一个
渲染结果；落库仍由 services 层负责。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.runtime.context import SlotSource, build_context
from app.runtime.contract import describe_contract
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
class PreparedPrompt:
    rendered_prompt: str
    messages: list[dict]
    trimmed: dict[str, str]
    prompt_tokens: int
    contents: dict[str, str]
    over_budget: bool
    output_schema: dict | None
    error: dict | None = None


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


def prepare_prompt(
    *,
    system_prompt: str,
    context_slots: list[str],
    output_schema: dict | None,
    token_budget: int,
    source: SlotSource,
    allow_missing: bool = False,
) -> PreparedPrompt:
    bundle = build_context(context_slots, source, token_budget)
    try:
        rendered = render(
            system_prompt, bundle.contents, allow_missing=allow_missing
        )
    except MissingVariableError as exc:
        return PreparedPrompt(
            rendered_prompt="",
            messages=[],
            trimmed=bundle.trimmed,
            prompt_tokens=0,
            contents=bundle.contents,
            over_budget=bundle.over_budget,
            output_schema=output_schema,
            error={"kind": "template", "message": str(exc)},
        )

    # 契约说明块在渲染之后追加：块里没有模板变量，而落库的 rendered_prompt
    # 必须是真正发出去的那一份，调试台才对得上（D-03）。
    contract_block = describe_contract(output_schema)
    if contract_block:
        rendered = f"{rendered}\n\n{contract_block}"

    return PreparedPrompt(
        rendered_prompt=rendered,
        messages=[{"role": "user", "content": rendered}],
        trimmed=bundle.trimmed,
        prompt_tokens=estimate_tokens(rendered),
        contents=bundle.contents,
        over_budget=bundle.over_budget,
        output_schema=output_schema,
    )


def _failure(
    prepared: PreparedPrompt,
    started: float,
    message: str,
    *,
    kind: str = "runtime",
    status: str = "error",
    raw_output: str = "",
    prices: dict | None = None,
) -> RunResult:
    prompt_tokens = estimate_tokens(prepared.rendered_prompt)
    completion_tokens = estimate_tokens(raw_output)
    return RunResult(
        rendered_prompt=prepared.rendered_prompt,
        raw_output=raw_output,
        parsed=None,
        structured=False,
        parse_error=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate=compute_cost(prompt_tokens, completion_tokens, prices),
        duration_ms=int((time.monotonic() - started) * 1000),
        status=status,
        error={"kind": kind, "message": message},
        trimmed=prepared.trimmed,
    )


async def execute_prepared(
    prepared: PreparedPrompt,
    *,
    config: ChatConfig,
    params: dict,
    prices: dict | None,
    client: ChatClient,
    started: float | None = None,
) -> RunResult:
    started_at = time.monotonic() if started is None else started
    if prepared.error:
        return _failure(
            prepared,
            started_at,
            prepared.error["message"],
            kind=prepared.error["kind"],
            prices=prices,
        )

    try:
        chat = await client.complete(config, prepared.messages, params)
    except ChatFailure as exc:
        # 失败不丢内容：已收到的片段照样返回给作者（上位文档 §4.10）
        return _failure(
            prepared,
            started_at,
            exc.error.message,
            kind=exc.error.kind,
            status="partial" if exc.partial_text else "error",
            raw_output=exc.partial_text,
            prices=prices,
        )

    parsed, structured, parse_error = apply_contract(
        chat.text, prepared.output_schema
    )
    completion_tokens = chat.completion_tokens or estimate_tokens(chat.text)
    prompt_tokens = chat.prompt_tokens or prepared.prompt_tokens
    return RunResult(
        rendered_prompt=prepared.rendered_prompt,
        raw_output=chat.text,
        parsed=parsed,
        structured=structured,
        parse_error=parse_error,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate=compute_cost(prompt_tokens, completion_tokens, prices),
        duration_ms=int((time.monotonic() - started_at) * 1000),
        status="ok",
        error=None,
        trimmed=prepared.trimmed,
    )


async def execute_run(inp: ExecuteInput, source: SlotSource, client: ChatClient) -> RunResult:
    started = time.monotonic()
    prepared = prepare_prompt(
        system_prompt=inp.system_prompt,
        context_slots=inp.context_slots,
        output_schema=inp.output_schema,
        token_budget=inp.token_budget,
        source=source,
    )
    return await execute_prepared(
        prepared,
        config=ChatConfig(base_url=inp.base_url, api_key=inp.api_key, model=inp.model),
        params=inp.params,
        prices=inp.prices,
        client=client,
        started=started,
    )
