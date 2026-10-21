"""服务商管理。密钥只经 DPAPI 存取，接口只回显屏蔽态（D-01）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.crypto import dpapi
from app.db.models import AgentVersion, GenerationRun, ModelPrice, Provider
from app.runtime.llm import ChatConfig, ChatFailure, HttpxChatClient


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


# ---- 模型单价 ----

def list_prices(session: Session) -> list[ModelPrice]:
    return list(
        session.scalars(
            select(ModelPrice).order_by(ModelPrice.provider_id, ModelPrice.model)
        )
    )


def get_price(session: Session, provider_id: str, model: str) -> ModelPrice | None:
    return session.scalars(
        select(ModelPrice).where(
            ModelPrice.provider_id == provider_id, ModelPrice.model == model
        )
    ).first()


def price_dict(session: Session, provider_id: str | None, model: str | None) -> dict | None:
    """给运行时用的单价快照。runtime 层不认识 ORM，所以在这里转成 dict。"""
    if not provider_id or not model:
        return None
    row = get_price(session, provider_id, model)
    if row is None:
        return None
    return {
        "input_price": row.input_price,
        "output_price": row.output_price,
        "currency": row.currency,
    }


def upsert_price(
    session: Session,
    *,
    provider_id: str,
    model: str,
    input_price: float,
    output_price: float,
    currency: str = "CNY",
) -> ModelPrice:
    if session.get(Provider, provider_id) is None:
        raise ValueError(f"服务商不存在：{provider_id}")
    if input_price < 0 or output_price < 0:
        raise ValueError("单价不能为负数")
    row = get_price(session, provider_id, model)
    if row is None:
        row = ModelPrice(provider_id=provider_id, model=model)
        session.add(row)
    row.input_price = input_price
    row.output_price = output_price
    row.currency = currency or "CNY"
    session.commit()
    return row


def delete_price(session: Session, price_id: str) -> None:
    row = session.get(ModelPrice, price_id)
    if row is None:
        raise ValueError(f"单价记录不存在：{price_id}")
    session.delete(row)
    session.commit()


# 按 HTTP 状态码给判定，比按 error.kind 分得更细：
# 404 与 400 在 kind 上都是 bad_request，但对作者的含义完全不同。
_STATUS_LABELS = {
    400: "请求被拒",
    401: "密钥无效",
    403: "密钥无效",
    404: "接口地址或模型名不存在",
    429: "额度不足或限流",
}

_KIND_LABELS = {
    "network": "网络不可达",
    "timeout": "请求超时",
    "auth": "密钥无效",
    "rate_limit": "额度不足或限流",
    "server": "服务商错误",
    "bad_request": "请求被拒",
}


def _first_bound_model(session: Session, provider_id: str) -> str | None:
    """找一个绑定到该服务商的模型名。

    角色卡没显式写 provider_id 时，运行时会回落到第一个启用的服务商 ——
    所以若全局只有一个启用的服务商，未指定归属的模型也算它的。
    """
    enabled_ids = [
        p.id for p in session.scalars(select(Provider).where(Provider.enabled.is_(True)))
    ]
    fallback_allowed = len(enabled_ids) == 1 and enabled_ids[0] == provider_id

    loose: str | None = None
    for version in session.scalars(select(AgentVersion)):
        binding = version.model_binding_json or {}
        model = binding.get("model")
        if not model:
            continue
        if binding.get("provider_id") == provider_id:
            return str(model)
        if fallback_allowed and binding.get("provider_id") is None:
            loose = loose or str(model)
    return loose


def test_connection(session: Session, provider_id: str, model: str | None = None) -> dict:
    """一键连通性测试。

    必须带一个模型名：用空模型名发请求只能证明地址可达，任何 400/401/404
    都会被当成「连接正常」，是假阳性的根源。
    """
    provider = session.get(Provider, provider_id)
    if provider is None:
        return {"ok": False, "message": f"服务商不存在：{provider_id}"}
    if not provider.base_url:
        return {"ok": False, "message": "尚未填写接口地址"}

    target_model = model or _first_bound_model(session, provider_id)
    if not target_model:
        return {
            "ok": False,
            "message": "请先为某个智能体绑定模型，或在此填写测试用模型",
        }

    api_key = dpapi.get_secret(provider.api_key_ref) if provider.api_key_ref else ""
    timeout = float(config.load_settings().get("request_timeout_seconds", 300))
    client = HttpxChatClient(timeout=timeout)
    chat_config = ChatConfig(base_url=provider.base_url, api_key=api_key or "", model=target_model)

    try:
        _sync_probe(client, chat_config)
    except ChatFailure as exc:
        label = _STATUS_LABELS.get(exc.error.status or 0) or _KIND_LABELS.get(
            exc.error.kind, "调用失败"
        )
        return {"ok": False, "message": f"{label}：{exc.error.message}"}
    except Exception as exc:  # noqa: BLE001 — 界面要看到原因而不是堆栈
        return {"ok": False, "message": f"调用失败：{exc}"}
    return {"ok": True, "message": f"连接正常，模型 {target_model} 可用"}


def _sync_probe(client: HttpxChatClient, config: ChatConfig) -> None:
    import asyncio

    async def probe() -> None:
        # 极短的请求即可判定：密钥、地址、模型名任一处不对都会被服务商拒绝。
        await client.complete(config, [{"role": "user", "content": "ping"}], {"max_tokens": 1})

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
