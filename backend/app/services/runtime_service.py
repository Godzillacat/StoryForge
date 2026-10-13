"""把运行时接上数据库：组装 ExecuteInput → execute_run → 写 generation_run。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.crypto import dpapi
from app.db.models import Agent, AgentVersion, GenerationRun, Provider
from app.runtime.execute import ExecuteInput, RunResult, execute_run
from app.runtime.llm import ChatClient, HttpxChatClient
from app.services.slot_source import DbSlotSource


class RuntimeService:
    def __init__(self, session: Session, client: ChatClient | None = None) -> None:
        self._session = session
        self._client = client

    def _resolve_client(self) -> ChatClient:
        """单独成一个方法，测试可以替换它以注入假传输层。"""
        if self._client is None:
            self._client = HttpxChatClient()
        return self._client

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

    def execute(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> tuple[GenerationRun, RunResult]:
        agent = self._session.get(Agent, agent_id)
        if agent is None:
            raise ValueError(f"智能体不存在：{agent_id}")
        if not agent.current_version_id:
            raise ValueError(f"智能体「{agent.name}」没有可用版本")

        version = self._session.get(AgentVersion, agent.current_version_id)
        if version is None:
            raise ValueError(f"智能体「{agent.name}」的当前版本已丢失")

        provider, base_url, api_key, prices = self.resolve_provider(version)
        binding = version.model_binding_json or {}
        settings = config.load_settings()

        source = DbSlotSource(self._session, project_id)
        inp = ExecuteInput(
            project_id=project_id,
            agent_id=agent.id,
            version_id=version.id,
            provider_id=provider.id,
            model=binding.get("model") or settings.get("default_model") or provider.name,
            base_url=base_url,
            api_key=api_key,
            params={**settings.get("default_params", {}), **(binding.get("params") or {})},
            system_prompt=version.system_prompt,
            context_slots=version.context_slots_json or [],
            output_schema=version.output_schema_json,
            token_budget=int(settings.get("context_token_budget", 8000)),
            prices=prices,
        )

        result = _run_sync(execute_run, inp, source, self._resolve_client())

        run = GenerationRun(
            project_id=project_id,
            agent_id=agent.id,
            agent_version_id=version.id,
            provider_id=provider.id,
            model=inp.model,
            params_json=inp.params,
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
        return run, result


def _run_sync(coro_factory, *args):
    """运行 async 运行时。

    services 层被 FastAPI 同步路由与 pytest 同步测试同时调用，
    因此这里按「是否已有事件循环」分派，不强制调用方改成 async。
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory(*args))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro_factory(*args)).result()
