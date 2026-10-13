import json
import os

from app import config


def test_data_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    assert config.data_dir() == tmp_path


def test_data_dir_creates_directory(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "StoryForge"
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(target))
    assert config.data_dir().is_dir()


def test_db_path_lives_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    assert config.db_path().parent == tmp_path
    assert config.db_path().name == "storyforge.db"


def test_secrets_path_lives_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    assert config.secrets_path().parent == tmp_path
    assert config.secrets_path().name == "secrets.bin"


def test_load_settings_returns_defaults_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    settings = config.load_settings()
    assert settings["context_token_budget"] == 8000
    assert settings["default_params"] == {"temperature": 0.7, "max_tokens": 4096}


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    config.save_settings({"context_token_budget": 1234})
    assert config.load_settings()["context_token_budget"] == 1234
    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert on_disk["context_token_budget"] == 1234


def test_missing_keys_are_backfilled_on_load(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.json").write_text('{"context_token_budget": 500}', encoding="utf-8")
    settings = config.load_settings()
    assert settings["context_token_budget"] == 500
    assert settings["default_params"] == {"temperature": 0.7, "max_tokens": 4096}
