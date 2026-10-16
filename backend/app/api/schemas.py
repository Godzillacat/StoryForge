"""接口出入参模型。api 层只做参数校验，业务在 services。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    genre: str | None = None
    sub_genre: str | None = None
    tone: str | None = None
    target_length: int | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    genre: str | None = None
    sub_genre: str | None = None
    tone: str | None = None
    target_length: int | None = None
    summary: str | None = None
    logic_check_level: str | None = None


class IdeaCreate(BaseModel):
    raw_text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class ActPayload(BaseModel):
    seq: int
    name: str
    purpose: str | None = None
    target_word_ratio: float | None = None
    summary: str | None = None


class ArchitectureAdopt(BaseModel):
    tool_ref: str | None = None
    logline: str | None = None
    theme: str | None = None
    premise: str | None = None
    ending_direction: str | None = None
    acts: list[ActPayload] = Field(default_factory=list)
    run_id: str | None = None


class VersionCreate(BaseModel):
    system_prompt: str | None = None
    model_binding_json: dict[str, Any] | None = None
    param_profile: str | None = None
    context_slots_json: list[str] | None = None
    output_schema_json: dict[str, Any] | None = None
    skills_json: list[str] | None = None
    trigger_mode: str | None = None
    note: str = ""


class RunRequest(BaseModel):
    project_id: str
    agent_id: str


class ProviderCreate(BaseModel):
    name: str
    kind: str = "custom"
    base_url: str = ""
    api_key: str | None = None
    enabled: bool = True
    priority: int = 0


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class AgentUpdate(BaseModel):
    """agent 级字段。改这些不动版本 —— 版本只承载提示词与运行配置（D-06）。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    role_label: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)
    enabled: bool | None = None


class ProviderTest(BaseModel):
    model: str | None = None


class EntryCreate(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    description: str = ""
    hardness: str | None = None
    source_run_id: str | None = None


class EntryUpdate(BaseModel):
    type: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = None
    tags: list[str] | None = None
    summary: str | None = None
    description: str | None = None
    hardness: str | None = None
    source_run_id: str | None = None
