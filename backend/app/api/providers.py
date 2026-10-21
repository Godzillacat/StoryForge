from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import config
from app.api.schemas import (
    ModelPriceIn,
    ProviderCreate,
    ProviderTest,
    ProviderUpdate,
    SettingsUpdate,
)
from app.db.session import get_session
from app.services import provider_service

router = APIRouter(prefix="/api", tags=["providers"])


def _provider_out(session: Session, provider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "kind": provider.kind,
        "base_url": provider.base_url,
        # 只回显屏蔽态，永不返回明文（D-01）
        "api_key_masked": provider_service.masked_key(provider),
        "enabled": provider.enabled,
        "priority": provider.priority,
    }


@router.get("/providers")
def list_providers(session: Session = Depends(get_session)) -> list[dict]:
    return [_provider_out(session, p) for p in provider_service.list_providers(session)]


@router.post("/providers", status_code=201)
def create_provider(payload: ProviderCreate, session: Session = Depends(get_session)) -> dict:
    fields = payload.model_dump(exclude={"api_key"})
    provider = provider_service.create_provider(session, api_key=payload.api_key, **fields)
    return _provider_out(session, provider)


@router.patch("/providers/{provider_id}")
def update_provider(
    provider_id: str, payload: ProviderUpdate, session: Session = Depends(get_session)
) -> dict:
    fields = payload.model_dump(exclude={"api_key"}, exclude_none=True)
    try:
        provider = provider_service.update_provider(
            session, provider_id, api_key=payload.api_key, **fields
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _provider_out(session, provider)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, session: Session = Depends(get_session)) -> None:
    try:
        provider_service.delete_provider(session, provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/test")
def test_provider(
    provider_id: str, payload: ProviderTest | None = None, session: Session = Depends(get_session)
) -> dict:
    return provider_service.test_connection(
        session, provider_id, model=payload.model if payload else None
    )


@router.get("/settings")
def get_settings() -> dict:
    return config.load_settings()


@router.put("/settings")
def update_settings(payload: SettingsUpdate) -> dict:
    config.save_settings(payload.values)
    return config.load_settings()


@router.get("/projects/{project_id}/cost")
def project_cost(project_id: str, session: Session = Depends(get_session)) -> dict:
    return provider_service.project_cost_summary(session, project_id)


def _price_out(row) -> dict:
    return {
        "id": row.id,
        "provider_id": row.provider_id,
        "model": row.model,
        "input_price": row.input_price,
        "output_price": row.output_price,
        "currency": row.currency,
    }


@router.get("/model-prices")
def list_model_prices(session: Session = Depends(get_session)) -> list[dict]:
    return [_price_out(row) for row in provider_service.list_prices(session)]


@router.put("/model-prices")
def upsert_model_price(
    payload: ModelPriceIn, session: Session = Depends(get_session)
) -> dict:
    try:
        row = provider_service.upsert_price(session, **payload.model_dump())
    except ValueError as exc:
        status = 404 if "不存在" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return _price_out(row)


@router.delete("/model-prices/{price_id}", status_code=204)
def delete_model_price(
    price_id: str, session: Session = Depends(get_session)
) -> None:
    try:
        provider_service.delete_price(session, price_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
