from app.runtime.params import PARAM_PROFILE_LABELS, PARAM_PROFILES, resolve_params


def test_profiles_carry_temperature_and_top_p_only():
    assert set(PARAM_PROFILES) == {"strict", "balanced", "creative"}
    for values in PARAM_PROFILES.values():
        assert set(values) == {"temperature", "top_p"}
        assert "max_tokens" not in values


def test_labels_match_profiles():
    assert set(PARAM_PROFILE_LABELS) == set(PARAM_PROFILES)


def test_each_profile_gets_its_own_values():
    for name, values in PARAM_PROFILES.items():
        merged, warnings = resolve_params(profile=name, default_params={})
        assert warnings == []
        assert merged["temperature"] == values["temperature"]
        assert merged["top_p"] == values["top_p"]


def test_global_defaults_are_kept():
    merged, _ = resolve_params(
        profile="balanced",
        default_params={"max_tokens": 4096, "temperature": 0.1},
    )

    assert merged["max_tokens"] == 4096


def test_profile_overrides_global_default():
    merged, _ = resolve_params(
        profile="strict", default_params={"temperature": 0.9, "max_tokens": 2048}
    )

    assert merged["temperature"] == 0.2
    assert merged["max_tokens"] == 2048


def test_version_override_wins():
    merged, _ = resolve_params(
        profile="strict",
        default_params={"max_tokens": 4096},
        override={"max_tokens": 8000, "temperature": 0.5},
    )

    assert merged["max_tokens"] == 8000
    assert merged["temperature"] == 0.5


def test_unknown_profile_falls_back_with_warning():
    merged, warnings = resolve_params(profile="wild", default_params={})

    assert merged["temperature"] == PARAM_PROFILES["balanced"]["temperature"]
    assert len(warnings) == 1
    assert "wild" in warnings[0]


def test_empty_profile_uses_balanced_without_warning():
    merged, warnings = resolve_params(profile=None, default_params={})

    assert warnings == []
    assert merged["temperature"] == PARAM_PROFILES["balanced"]["temperature"]
