"""接口出入参模型。api 层只做参数校验，业务在 services。"""

from __future__ import annotations

from typing import Any, Literal

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
    # 人物专属字段（type == "character" 才有意义），其余类型留空
    appearance: str = ""
    personality: str = ""
    desire: str = ""
    fear: str = ""
    arc_type: str = ""
    abilities: str = ""
    speech_style: str = ""
    current_state: str = ""


class EntryUpdate(BaseModel):
    type: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = None
    tags: list[str] | None = None
    summary: str | None = None
    description: str | None = None
    hardness: str | None = None
    source_run_id: str | None = None
    # 人物专属字段（type == "character" 才有意义），其余类型留空
    appearance: str | None = None
    personality: str | None = None
    desire: str | None = None
    fear: str | None = None
    arc_type: str | None = None
    abilities: str | None = None
    speech_style: str | None = None
    current_state: str | None = None


class RelationCreate(BaseModel):
    from_id: str
    to_id: str
    kind: str = Field(min_length=1, max_length=60)
    strength: int | None = Field(default=None, ge=1, le=5)
    note: str = ""
    create_reverse: bool = False


class RelationUpdate(BaseModel):
    kind: str | None = Field(default=None, min_length=1, max_length=60)
    strength: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None


class VolumeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    purpose: str = ""
    summary: str = ""
    act_seq: int | None = None
    target_words: int | None = None
    status: str = "planned"


class VolumeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = None
    summary: str | None = None
    act_seq: int | None = None
    target_words: int | None = None
    status: str | None = None


class ChapterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    pov: str = ""
    target_words: int | None = None
    emotional_tone: str = ""
    lines: list[str] = Field(default_factory=list)
    hook: str = ""
    summary: str = ""
    conflict_level: int | None = None
    dialogue_ratio: float | None = None
    hook_strength: int | None = None
    status: str = "planned"


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    pov: str | None = None
    target_words: int | None = None
    emotional_tone: str | None = None
    lines: list[str] | None = None
    hook: str | None = None
    summary: str | None = None
    conflict_level: int | None = None
    dialogue_ratio: float | None = None
    hook_strength: int | None = None
    status: str | None = None


class MoveRequest(BaseModel):
    direction: Literal["up", "down"]


class SceneCreate(BaseModel):
    goal: str = ""
    conflict: str = ""
    turn: str = ""
    characters: list[str] = Field(default_factory=list)  # 名称
    location: str | None = None  # 名称
    story_time: str = ""
    pov: str = ""
    target_words_min: int | None = None
    target_words_max: int | None = None
    foreshadow_plants: list[str] = Field(default_factory=list)
    foreshadow_pays: list[str] = Field(default_factory=list)
    status: str = "planned"


class SceneUpdate(BaseModel):
    goal: str | None = None
    conflict: str | None = None
    turn: str | None = None
    characters: list[str] | None = None
    location: str | None = None
    story_time: str | None = None
    pov: str | None = None
    target_words_min: int | None = None
    target_words_max: int | None = None
    foreshadow_plants: list[str] | None = None
    foreshadow_pays: list[str] | None = None
    status: str | None = None


class SceneWrite(BaseModel):
    mode: Literal["replace", "append"]
    source_run_id: str | None = None
    scenes: list[dict[str, Any]] = Field(default_factory=list)


class PlanChapter(BaseModel):
    title: str = ""
    pov: str = ""
    target_words: int | None = None
    emotional_tone: str = ""
    lines: list[str] = Field(default_factory=list)
    hook: str = ""
    summary: str = ""
    conflict_level: int | None = None
    dialogue_ratio: float | None = None
    hook_strength: int | None = None
    status: str = "planned"


class PlanVolume(BaseModel):
    name: str = ""
    purpose: str = ""
    summary: str = ""
    act_seq: int | None = None
    target_words: int | None = None
    status: str = "planned"
    chapters: list[PlanChapter] = Field(default_factory=list)


class ChapterPlanWrite(BaseModel):
    mode: Literal["replace", "append"]
    source_run_id: str | None = None
    volumes: list[PlanVolume] = Field(default_factory=list)


class ForeshadowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    note: str = ""
    status: str = "planned"


class ForeshadowUpdate(BaseModel):
    # plant_scene_id 由场景挂接管理，不开放这里改。
    name: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None
    plan_pay_scene_id: str | None = None
    status: str | None = None
