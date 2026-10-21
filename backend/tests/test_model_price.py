import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ModelPrice, Provider
from app.runtime.pricing import compute_cost, resolve_prices
from app.services import provider_service


def _provider(session, name="百炼"):
    provider = Provider(name=name, base_url="https://api.example.com/v1")
    session.add(provider)
    session.commit()
    return provider


def test_upsert_inserts_then_updates_the_same_rows(session):
    provider = _provider(session)

    first = provider_service.upsert_price(
        session, provider_id=provider.id, model="m1", input_price=1.0, output_price=2.0
    )
    second = provider_service.upsert_price(
        session, provider_id=provider.id, model="m1", input_price=3.0, output_price=4.0
    )

    assert first.id == second.id
    assert session.query(ModelPrice).count() == 1
    assert second.input_price == 3.0


def test_unique_constraint_holds_at_the_database_level(session):
    provider = _provider(session)
    session.add(
        ModelPrice(provider_id=provider.id, model="m1", input_price=1, output_price=1)
    )
    session.commit()
    session.add(
        ModelPrice(provider_id=provider.id, model="m1", input_price=2, output_price=2)
    )

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_unknown_provider_is_rejected(session):
    with pytest.raises(ValueError, match="服务商不存在"):
        provider_service.upsert_price(
            session, provider_id="nope", model="m1", input_price=1, output_price=1
        )


def test_negative_price_is_rejected(session):
    provider = _provider(session)
    with pytest.raises(ValueError, match="不能为负数"):
        provider_service.upsert_price(
            session, provider_id=provider.id, model="m1", input_price=-1, output_price=0
        )


def test_deleting_a_provider_cascades_to_its_prices(session):
    provider = _provider(session)
    provider_service.upsert_price(
        session, provider_id=provider.id, model="m1", input_price=1, output_price=1
    )

    session.delete(session.get(Provider, provider.id))
    session.commit()

    assert session.query(ModelPrice).count() == 0


def test_resolve_prices_prefers_binding_then_table_then_none():
    assert resolve_prices({"input": 9, "output": 9}, {"input_price": 1, "output_price": 1}) == {
        "input": 9,
        "output": 9,
    }
    assert resolve_prices(None, {"input_price": 1, "output_price": 2}) == {
        "input": 1.0,
        "output": 2.0,
    }
    assert resolve_prices(None, None) is None
    assert resolve_prices({}, None) is None


def test_cost_matches_the_per_million_formula(session):
    prices = {"input": 2.0, "output": 8.0}

    assert compute_cost(1_000_000, 500_000, prices) == pytest.approx(6.0)
