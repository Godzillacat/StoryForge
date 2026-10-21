from app.runtime.context import SLOT_REGISTRY, build_context


class FakeSource:
    def __init__(self, **fields):
        self._fields = fields

    def project_core(self):
        return self._fields.get("project_core")

    def parsed_idea(self):
        return self._fields.get("parsed_idea")

    def raw_idea(self):
        return self._fields.get("raw_idea")

    def story_bible(self):
        return self._fields.get("story_bible")

    def architecture(self):
        return self._fields.get("architecture")

    def tool_library(self):
        return self._fields.get("tool_library")

    def style_samples(self):
        return self._fields.get("style_samples")

    def summarize(self, slot_key, text):
        return f"[摘要]{text[:5]}"


def test_registry_priority_order_matches_spec():
    assert SLOT_REGISTRY["project_core"].priority > SLOT_REGISTRY["parsed_idea"].priority
    assert SLOT_REGISTRY["parsed_idea"].priority > SLOT_REGISTRY["tool_library"].priority
    assert SLOT_REGISTRY["tool_library"].priority > SLOT_REGISTRY["style_samples"].priority


def test_never_trim_slots_are_marked_never():
    assert SLOT_REGISTRY["project_core"].over_budget == "never"


def test_build_context_returns_requested_slots():
    source = FakeSource(project_core="项目：验尸官", parsed_idea="题材：悬疑")
    bundle = build_context(["parsed_idea", "project_core"], source, token_budget=10_000)
    assert bundle.contents == {"project_core": "项目：验尸官", "parsed_idea": "题材：悬疑"}
    assert bundle.trimmed == {}
    assert bundle.over_budget is False


def test_missing_slot_is_skipped_not_errored():
    source = FakeSource(project_core="项目：验尸官")
    bundle = build_context(["project_core", "story_bible"], source, token_budget=10_000)
    assert "story_bible" not in bundle.contents
    assert "story_bible" not in bundle.trimmed


def test_unknown_slot_key_is_skipped():
    source = FakeSource(project_core="项目：验尸官")
    bundle = build_context(["project_core", "不存在的槽位"], source, token_budget=10_000)
    assert list(bundle.contents) == ["project_core"]


def test_under_budget_content_is_untouched():
    source = FakeSource(parsed_idea="题材：悬疑", raw_idea="一个能听见死者遗言的验尸官")
    bundle = build_context(["parsed_idea", "raw_idea"], source, token_budget=1_000_000)
    assert bundle.contents["raw_idea"] == "一个能听见死者遗言的验尸官"
    assert bundle.over_budget is False


def test_lowest_priority_slot_is_dropped_first_when_over_budget():
    # estimate_tokens 对 CJK 约 1 token/字
    source = FakeSource(
        project_core="短",
        parsed_idea="解析卡" * 20,      # 60 tokens
        raw_idea="灵感原话" * 50,        # 200 tokens
    )
    bundle = build_context(
        ["parsed_idea", "raw_idea", "project_core"], source, token_budget=80
    )
    # over_budget 表示「裁完之后仍然超预算」，不是「裁过」。裁掉了什么由 trimmed 记录。
    assert bundle.over_budget is False
    assert "project_core" in bundle.contents        # 最高优先级保留
    assert "raw_idea" not in bundle.contents        # 最低优先级丢弃
    assert bundle.trimmed["raw_idea"] == "已丢弃"
    assert bundle.estimated_tokens <= 80


def test_summarizable_slot_is_compressed_before_dropping():
    source = FakeSource(
        project_core="短",
        parsed_idea="解析卡" * 100,     # 300 tokens
    )
    bundle = build_context(["parsed_idea", "project_core"], source, token_budget=60)
    # FakeSource.summarize 返回 f"[摘要]{text[:5]}"，"解析卡"*100 的前 5 字是 "解析卡解析"
    assert bundle.contents["parsed_idea"] == "[摘要]解析卡解析"
    assert bundle.trimmed["parsed_idea"] == "压缩为要点"


def test_drop_is_preferred_over_summarize_for_drop_slots():
    source = FakeSource(project_core="短", tool_library="工具库" * 200)
    bundle = build_context(["tool_library", "project_core"], source, token_budget=60)
    assert "tool_library" not in bundle.contents
    assert bundle.trimmed["tool_library"] == "已丢弃"


def test_trimmed_records_are_populated_for_ui_to_display():
    source = FakeSource(project_core="短", raw_idea="灵感" * 500)
    bundle = build_context(["raw_idea", "project_core"], source, token_budget=50)
    assert set(bundle.trimmed) == {"raw_idea"}


def test_estimated_tokens_is_reported():
    source = FakeSource(project_core="项目" * 10)
    bundle = build_context(["project_core"], source, token_budget=10_000)
    assert bundle.estimated_tokens == 20


def test_build_context_with_no_slots():
    bundle = build_context([], FakeSource(), token_budget=100)
    assert bundle.contents == {} and bundle.trimmed == {} and bundle.estimated_tokens == 0


def test_style_samples_slot_is_requestable():
    source = FakeSource(project_core="短", style_samples="他说话很短")
    bundle = build_context(["style_samples", "project_core"], source, token_budget=10_000)
    assert bundle.contents["style_samples"] == "他说话很短"


def test_over_budget_is_true_when_never_slot_exceeds_budget():
    source = FakeSource(project_core="字" * 500)
    bundle = build_context(["project_core"], source, token_budget=10)
    assert bundle.over_budget is True          # 裁完仍然超预算，如实上报
    assert bundle.trimmed == {}                # 但确实没裁任何东西
    assert "project_core" in bundle.contents   # never 槽位永不被裁


def test_custom_compressor_overrides_source_summarize():
    calls = []

    def compressor(slot_key, text):
        calls.append(slot_key)
        return "压缩后"

    source = FakeSource(project_core="短", parsed_idea="解析卡" * 100)
    bundle = build_context(
        ["parsed_idea", "project_core"], source, token_budget=60, compressor=compressor
    )
    assert calls == ["parsed_idea"]
    assert bundle.contents["parsed_idea"] == "压缩后"
    assert bundle.trimmed["parsed_idea"] == "压缩为要点"


def test_summarize_returning_empty_marks_slot_as_dropped():
    class EmptySummarizer(FakeSource):
        def summarize(self, slot_key, text):
            return ""

    source = EmptySummarizer(project_core="短", parsed_idea="解析卡" * 100)
    bundle = build_context(["parsed_idea", "project_core"], source, token_budget=60)
    assert "parsed_idea" not in bundle.contents
    assert bundle.trimmed["parsed_idea"] == "已丢弃"   # 记录必须如实反映「丢掉了」


def test_new_slots_are_registered():
    for key in ("world_context", "timeline", "volume_outline", "chapter_outline"):
        assert key in SLOT_REGISTRY


def test_related_settings_slot_registered():
    from app.runtime.context import P_MID, SLOT_REGISTRY

    spec = SLOT_REGISTRY["related_settings"]
    assert spec.label == "相关设定条目（检索）"
    assert spec.priority == P_MID
    assert spec.over_budget == "summarize"


def test_new_writing_slots_are_registered():
    from app.runtime.context import SLOT_REGISTRY

    assert SLOT_REGISTRY["scene_card"].over_budget == "never"
    assert SLOT_REGISTRY["scene_characters"].over_budget == "never"
    assert SLOT_REGISTRY["recent_text"].key == "recent_text"


def test_scene_text_slot_is_registered_as_never_trim():
    from app.runtime.context import P_NEVER, SLOT_REGISTRY

    spec = SLOT_REGISTRY["scene_text"]
    assert spec.label == "当前已采纳正文"
    assert spec.priority == P_NEVER
    assert spec.over_budget == "never"
