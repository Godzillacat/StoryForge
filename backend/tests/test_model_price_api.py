def _provider(client):
    return client.post(
        "/api/providers",
        json={"name": "百炼", "base_url": "https://api.example.com/v1"},
    ).json()


def test_upsert_list_and_delete(client):
    provider = _provider(client)

    created = client.put(
        "/api/model-prices",
        json={
            "provider_id": provider["id"],
            "model": "qwen-flash",
            "input_price": 0.3,
            "output_price": 0.6,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["model"] == "qwen-flash"
    assert body["currency"] == "CNY"

    listed = client.get("/api/model-prices").json()
    assert any(row["id"] == body["id"] for row in listed)

    assert client.delete(f"/api/model-prices/{body['id']}").status_code == 204
    assert client.get("/api/model-prices").json() == []


def test_unknown_provider_is_404(client):
    response = client.put(
        "/api/model-prices",
        json={
            "provider_id": "nope",
            "model": "m1",
            "input_price": 1,
            "output_price": 1,
        },
    )
    assert response.status_code == 404


def test_negative_price_is_422_or_400(client):
    provider = _provider(client)
    response = client.put(
        "/api/model-prices",
        json={
            "provider_id": provider["id"],
            "model": "m1",
            "input_price": -1,
            "output_price": 1,
        },
    )
    assert response.status_code in (400, 422)


def test_delete_missing_price_is_404(client):
    assert client.delete("/api/model-prices/nope").status_code == 404
