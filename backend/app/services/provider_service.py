"""服务商管理。密钥只经 DPAPI 存取，接口只回显屏蔽态（D-01）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import dpapi
from app.db.models import GenerationRun, Provider
from app.runtime.llm import ChatConfig, HttpxChatClient


def list_providers(session: Session) -> list[Provider]:
    return list(session.scalars(select(Provider).order_by(Provider.priority)))


def _key_ref(provider_id: str) -> str:
    return f"provider:{provider_id}"


def create_provider(session: Session, *, api_key: str | None, **fields) -> Provider:
    provider = Provider(**fields)
    session.add(provider)
    session.commit()
    if api_key:
        provider.api_key_ref = _key_ref(provider.id)
        dpapi.set_secret(provider.api_key_ref, api_key)
        session.commit()
    return provider


def update_provider(session: Session, provider_id: str, *, api_key: str | None, **fields) -> Provider:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise ValueError(f"服务商不存在：{provider_id}")
    for key, value in fields.items():
        if value is not None:
            setattr(provider, key, value)
    if api_key:
        provider.api_key_ref = _key_ref(provider.id)
        dpapi.set_secret(provider.api_key_ref, api_key)
    session.commit()
    return provider


def delete_provider(session: Session, provider_id: str) -> None:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise ValueError(f"服务商不存在：{provider_id}")
    if provider.api_key_ref:
        dpapi.delete_secret(provider.api_key_ref)
    session.delete(provider)
    session.commit()


def masked_key(provider: Provider) -> str:
    if not provider.api_key_ref:
        return ""
    return dpapi.mask(dpapi.get_secret(provider.api_key_ref) or "")


def test_connection(session: Session, provider_id: str) -> dict:
    """一键连通性测试。失败给出可读原因，不抛异常给界面。"""
    provider = session.get(Provider, provider_id)
    if provider is None:
        return {"ok": False, "message": f"服务商不存在：{provider_id}"}
    if not provider.base_url:
        return {"ok": False, "message": "尚未填写接口地址"}

    api_key = dpapi.get_secret(provider.api_key_ref) if provider.api_key_ref else ""
    client = HttpxChatClient()
    config = ChatConfig(base_url=provider.base_url, api_key=api_key or "", model="")
    try:
        _sync_probe(client, config)
    except Exception as exc:  # noqa: BLE001 — 界面要看到原因而不是堆栈
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": "连接正常"}


def _sync_probe(client: HttpxChatClient, config: ChatConfig) -> None:
    import asyncio

    async def probe() -> None:
        # 用一个必然失败的极短请求探测连通性；401/404 说明地址可达，
        # 网络类错误才是真的连不上。
        from app.runtime.llm import ChatFailure

        try:
            await client.complete(config, [{"role": "user", "content": "ping"}], {"max_tokens": 1})
        except ChatFailure as exc:
            if exc.error.kind == "network" or exc.error.kind == "timeout":
                raise

    asyncio.run(probe())


def project_cost_summary(session: Session, project_id: str) -> dict:
    runs = session.scalars(
        select(GenerationRun).where(GenerationRun.project_id == project_id)
    ).all()
    return {
        "runs": len(runs),
        "prompt_tokens": sum(r.prompt_tokens for r in runs),
        "completion_tokens": sum(r.completion_tokens for r in runs),
        "cost_estimate": round(sum(r.cost_estimate for r in runs), 6),
    }
