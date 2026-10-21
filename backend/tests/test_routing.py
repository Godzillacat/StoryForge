from app.runtime.routing import normalize_routing_entry, resolve_binding


def _resolve(**kwargs):
    base = {
        "version_binding": {},
        "version_profile": "balanced",
        "task_type": "write",
        "routing": {},
        "default_model": None,
        "profile_is_authorial": True,
    }
    base.update(kwargs)
    return resolve_binding(**base)


def test_version_binding_wins_over_routing():
    result = _resolve(
        version_binding={"provider_id": "p1", "model": "m-own"},
        routing={"write": {"provider_id": "p2", "model": "m-route"}},
    )

    assert result.binding == {"provider_id": "p1", "model": "m-own"}


def test_route_fills_missing_provider():
    result = _resolve(
        version_binding={"model": "m-own"},
        routing={"write": {"provider_id": "p2", "model": "m-route"}},
    )

    assert result.binding == {"provider_id": "p2", "model": "m-own"}


def test_route_model_used_when_version_has_none():
    result = _resolve(routing={"write": {"model": "m-route"}})

    assert result.binding == {"model": "m-route"}


def test_default_model_is_last_resort():
    assert _resolve(default_model="m-default").binding == {"model": "m-default"}


def test_missing_model_leaves_binding_empty():
    result = _resolve()

    assert "model" not in result.binding


def test_preset_profile_does_not_block_the_route():
    """预置出厂带 strict，那不是作者选的 —— 分路里的参数档要能生效。"""
    result = _resolve(
        version_profile="strict",
        routing={"write": {"param_profile": "creative"}},
        profile_is_authorial=False,
    )

    assert result.profile == "creative"


def test_authorial_version_profile_wins_over_route():
    result = _resolve(
        version_profile="creative",
        routing={"write": {"param_profile": "strict"}},
        profile_is_authorial=True,
    )

    assert result.profile == "creative"


def test_route_profile_absent_falls_back_to_version():
    result = _resolve(version_profile="strict", profile_is_authorial=False)

    assert result.profile == "strict"


def test_profile_defaults_to_balanced():
    assert _resolve().profile == "balanced"


def test_unknown_task_type_is_ignored():
    result = _resolve(routing={"polish": {"model": "m-other"}}, task_type="write")

    assert "model" not in result.binding


def test_string_entry_becomes_model_only():
    assert normalize_routing_entry("  m-text  ") == {"model": "m-text"}
    assert normalize_routing_entry("   ") == {}
    assert normalize_routing_entry(None) == {}
    assert normalize_routing_entry(["x"]) == {}
    assert normalize_routing_entry({"model": "m"}) == {"model": "m"}


def test_string_route_entry_used():
    result = _resolve(routing={"write": "m-text"})

    assert result.binding == {"model": "m-text"}
