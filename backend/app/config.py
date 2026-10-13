"""本机数据目录与全局设置的唯一入口。

程序本体只读，所有可变数据都在 %LOCALAPPDATA%\\StoryForge 之下。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SETTINGS: dict = {
    "context_token_budget": 8000,
    "default_params": {"temperature": 0.7, "max_tokens": 4096},
    "model_routing": {},
    "budget_alert": None,
}


def data_dir() -> Path:
    override = os.environ.get("STORYFORGE_DATA_DIR")
    if override:
        base = Path(override)
    else:
        local_appdata = os.environ.get("LOCALAPPDATA")
        base = (Path(local_appdata) if local_appdata else Path.home() / ".local" / "share") / "StoryForge"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "storyforge.db"


def secrets_path() -> Path:
    return data_dir() / "secrets.bin"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def project_assets_dir(project_id: str) -> Path:
    path = data_dir() / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict:
    path = settings_path()
    stored: dict = {}
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stored = {}
    merged = {**DEFAULT_SETTINGS, **stored}
    # default_params 逐键合并，避免旧设置文件缺键后被整体覆盖
    merged["default_params"] = {**DEFAULT_SETTINGS["default_params"], **stored.get("default_params", {})}
    return merged


def save_settings(values: dict) -> None:
    merged = {**load_settings(), **values}
    settings_path().write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
