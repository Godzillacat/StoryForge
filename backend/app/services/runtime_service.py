"""把运行时接上数据库：准备执行上下文 → 调用模型 → 写 generation_run。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.crypto import dpapi
from app.db.models import Agent, AgentVersion, GenerationRun, Provider
from app.runtime.execute import (
    PreparedPrompt,
    RunResult,
    execute_prepared,
    prepare_prompt,
)
from app.runtime.llm import ChatClient, ChatConfig, HttpxChatClient
from app.services.slot_source import DbSlotSource


@dataclass(frozen=True)
class PreparedExecution:
    agent: Agent
    version: AgentVersion
    provider: Provider
    model: str
    params: dict
    prices: dict | None
    config: ChatConfig
    prompt: PreparedPrompt
    client: ChatClient


class RuntimeService:
    def __init__(self, session: Session, client: ChatClient | None = None) -> None:
        self._session = session
        self._client = client

    def _resolve_client(self, timeout: float) -> ChatClient:
        """单独成一个方法，测试可以替换它以注入假传输层。

        不缓存默认客户端：超时是逐次运行解析出来的，缓存会让第一次的值
        粘住后续所有调用。
        """
        if self._client is not None:
            return self._client
        return HttpxChatClient(timeout=timeout)

    def _resolve_timeout(self, binding: dict) -> float:
        """超时三层解析：角色卡 → 全局设置 → 默认。让慢模型可被单独放宽。"""
        agent_level = binding.get("timeout_seconds")
        if agent_level:
            return float(agent_level)
        return float(config.load_settings().get("request_timeout_seconds", 300))

    def resolve_provider(
        self, version: AgentVersion
    ) -> tuple[Provider, str, str, dict]:
        """返回 (provider, base_url, api_key, prices)。密钥从 DPAPI 取，不进数据库。"""
        binding = version.model_binding_json or {}
        provider_id = binding.get("provider_id")

        provider: Provider | None = None
        if provider_id:
            provider = self._session.get(Provider, provider_id)
        if provider is None:
            provider = self._session.scalars(
                select(Provider).where(Provider.enabled.is_(True)).order_by(Provider.priority)
            ).first()
        if provider is None:
            raise ValueError("没有可用的服务商，请先在「模型与费用」里配置并启用一家")

        api_key = dpapi.get_secret(provider.api_key_ref) if provider.api_key_ref else ""
        if api_key is None:
            api_key = ""
        prices = binding.get("prices") or {}
        return provider, provider.base_url, api_key, prices

    def prepare_context(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> tuple[Agent, AgentVersion, PreparedPrompt]:
        agent = self._session.get(Agent, agent_id)
        if agent is None:
            raise ValueError(f"智能体不存在：{agent_id}")
        if not agent.current_version_id:
            raise ValueError(f"智能体「{agent.name}」没有可用版本")
        version = self._session.get(AgentVersion, agent.current_version_id)
        if version is None:
            raise ValueError(f"智能体「{agent.name}」的当前版本已丢失")

        settings = config.load_settings()
        source = DbSlotSource(self._session, project_id, extra_slots=extra)
        prompt = prepare_prompt(
            system_prompt=version.system_prompt,
            context_slots=version.context_slots_json or [],
            output_schema=version.output_schema_json,
            token_budget=int(settings.get("context_token_budget", 8000)),
            source=source,
            # 没有输出契约的预置是纯文本执笔：首场天然可能没有人物、检索结果
            # 或前情正文，缺槽位按空串渲染；结构化预置仍严格报缺变量。
            allow_missing=version.output_schema_json is None,
        )
        return agent, version, prompt

    def prepare(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> PreparedExecution:
        agent, version, prompt = self.prepare_context(project_id, agent_id, extra)
        provider, base_url, api_key, prices = self.resolve_provider(version)
        binding = version.model_binding_json or {}
        settings = config.load_settings()

        # 不要回落到 provider.name —— 那是服务商的显示名，不是模型 ID，
        # 发出去必然被拒，而错误信息会把作者引到错误的方向。
        model = binding.get("model") or settings.get("default_model")
        if not model:
            raise ValueError(
                f"智能体「{agent.name}」还没有绑定模型，请先在「智能体工作室」为它指定一个"
            )
        params = {
            **settings.get("default_params", {}),
            **(binding.get("params") or {}),
        }
        return PreparedExecution(
            agent=agent,
            version=version,
            provider=provider,
            model=model,
            params=params,
            prices=prices,
            config=ChatConfig(base_url=base_url, api_key=api_key, model=model),
            prompt=prompt,
            client=self._resolve_client(self._resolve_timeout(binding)),
        )

    def execute(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> tuple[GenerationRun, RunResult]:
        prepared = self.prepare(project_id, agent_id, extra)
        result = _run_sync(
            execute_prepared,
            prepared.prompt,
            config=prepared.config,
            params=prepared.params,
            prices=prepared.prices,
            client=prepared.client,
        )
        run = self._persist_run(project_id, prepared, result)
        return run, result

    def _persist_run(
        self, project_id: str, prepared: PreparedExecution, result: RunResult
    ) -> GenerationRun:
        run = GenerationRun(
            project_id=project_id,
            agent_id=prepared.agent.id,
            agent_version_id=prepared.version.id,
            provider_id=prepared.provider.id,
            model=prepared.model,
            params_json=prepared.params,
            rendered_prompt=result.rendered_prompt,
            raw_output=result.raw_output,
            parsed_json=result.parsed,
            structured=result.structured,
            # 契约失败的原因必须落库，否则调试台无法解释「为什么没结构化」
            parse_error=result.parse_error,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_estimate=result.cost_estimate,
            duration_ms=result.duration_ms,
            status=result.status,
            error_json=result.error,
            trimmed_json=result.trimmed,
        )
        self._session.add(run)
        self._session.commit()
        return run


def _run_sync(coro_factory, *args, **kwargs):
    """运行 async 运行时。

    services 层被 FastAPI 同步路由与 pytest 同步测试同时调用，
    因此这里按「是否已有事件循环」分派，不强制调用方改成 async。
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory(*args, **kwargs))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro_factory(*args, **kwargs)).result()
