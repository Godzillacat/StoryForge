"""上下文组装（上位文档 §5.4、D-09）。

槽位按优先级取值，超预算时从最低优先级开始裁剪，
裁剪结果必须能被界面明示「这次砍掉了什么」。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.runtime.pricing import estimate_tokens

# 优先级数值越大越优先。100 段永不裁剪。
P_NEVER = 100
P_HIGH = 80
P_MID = 50
P_LOW = 20


class SlotSource(Protocol):
    """项目态只读视图。runtime 只依赖这个协议，不依赖数据库。"""

    def project_core(self) -> str | None: ...
    def parsed_idea(self) -> str | None: ...
    def raw_idea(self) -> str | None: ...
    def story_bible(self) -> str | None: ...
    def architecture(self) -> str | None: ...
    def tool_library(self) -> str | None: ...
    def style_samples(self) -> str | None: ...
    def world_context(self) -> str | None: ...
    def timeline(self) -> str | None: ...
    def volume_outline(self) -> str | None: ...
    def chapter_outline(self) -> str | None: ...
    def scene_card(self) -> str | None: ...
    def scene_characters(self) -> str | None: ...
    def recent_text(self) -> str | None: ...
    def scene_text(self) -> str | None: ...
    def related_settings(self) -> str | None: ...
    def foreshadow_ledger(self) -> str | None: ...
    def summarize(self, slot_key: str, text: str) -> str: ...


@dataclass(frozen=True)
class SlotSpec:
    key: str
    label: str
    priority: int
    over_budget: str  # "never" | "summarize" | "drop"


SLOT_REGISTRY: dict[str, SlotSpec] = {
    spec.key: spec
    for spec in (
        SlotSpec("project_core", "项目核心信息", P_NEVER, "never"),
        SlotSpec("story_bible", "故事圣经摘要", P_HIGH, "summarize"),
        SlotSpec("architecture", "幕/卷骨架", P_HIGH, "summarize"),
        SlotSpec("parsed_idea", "灵感解析卡", P_HIGH, "summarize"),
        SlotSpec("raw_idea", "灵感原话", P_MID, "drop"),
        SlotSpec("tool_library", "创作工具库摘要", P_MID, "drop"),
        SlotSpec("style_samples", "风格样本", P_LOW, "drop"),
        SlotSpec("world_context", "世界观摘要", P_HIGH, "summarize"),
        SlotSpec("chapter_outline", "本章章纲", P_HIGH, "summarize"),
        SlotSpec("volume_outline", "本卷纲要", P_HIGH, "summarize"),
        SlotSpec("timeline", "故事内时间线", P_MID, "summarize"),
        SlotSpec("scene_card", "当前场景卡", P_NEVER, "never"),
        SlotSpec("scene_characters", "出场人物完整卡", P_NEVER, "never"),
        SlotSpec("recent_text", "最近已采纳正文", P_MID, "drop"),
        SlotSpec("scene_text", "当前已采纳正文", P_NEVER, "never"),
        SlotSpec("related_settings", "相关设定条目（检索）", P_MID, "summarize"),
        SlotSpec("foreshadow_ledger", "伏笔账本", P_HIGH, "summarize"),
        # 修订建议专用的两个槽位：不来自项目态投影，由调用方在一次运行里
        # 显式传值（见 DbSlotSource.__getattr__）。本次改动永不裁剪 ——
        # 被裁掉就等于让模型不知道这次改了什么。
        SlotSpec("impact_target", "这次改了什么", P_NEVER, "never"),
        SlotSpec("impact_candidates", "受影响对象的现值", P_NEVER, "never"),
    )
}


@dataclass(frozen=True)
class ContextBundle:
    contents: dict[str, str] = field(default_factory=dict)
    trimmed: dict[str, str] = field(default_factory=dict)
    estimated_tokens: int = 0
    over_budget: bool = False


def _tokens_of(contents: dict[str, str]) -> int:
    return sum(estimate_tokens(text) for text in contents.values())


def build_context(
    version_slots: list[str],
    source: SlotSource,
    token_budget: int,
    compressor: Callable[[str, str], str] | None = None,
) -> ContextBundle:
    summarize = compressor or source.summarize

    contents: dict[str, str] = {}
    for key in version_slots:
        spec = SLOT_REGISTRY.get(key)
        if spec is None:
            continue  # 未注册的槽位键（如 P1b 才有的场景卡）静默跳过
        value = getattr(source, key)()
        if value:
            contents[key] = value

    trimmed: dict[str, str] = {}
    if _tokens_of(contents) <= token_budget:
        return ContextBundle(contents=contents, estimated_tokens=_tokens_of(contents))

    # 从最低优先级开始依次处理，直到落进预算
    for spec in sorted((SLOT_REGISTRY[k] for k in contents), key=lambda s: s.priority):
        if _tokens_of(contents) <= token_budget:
            break
        if spec.over_budget == "never":
            continue
        if spec.over_budget == "summarize":
            compressed = summarize(spec.key, contents[spec.key])
        else:
            compressed = ""
        if compressed:
            contents[spec.key] = compressed
            trimmed[spec.key] = "压缩为要点"
        else:
            del contents[spec.key]
            trimmed[spec.key] = "已丢弃"

    final_tokens = _tokens_of(contents)
    return ContextBundle(
        contents=contents,
        trimmed=trimmed,
        estimated_tokens=final_tokens,
        over_budget=final_tokens > token_budget,
    )
