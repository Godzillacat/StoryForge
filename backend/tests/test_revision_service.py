"""修订建议：槽位、预置、任务类型（Task 1）、生成（Task 2）与应用（Task 3）。

Task 1 的用例先跑红、再实现：新槽位没注册时上下文组装会整段跳过，
新任务类型没登记时 `find_by_task_type` 找不到智能体。
Task 2 的用例同样先跑红：`revision_service` 模块一开始并不存在。
Task 3 的用例先跑红：`apply()` 不存在，且运行记录里还没有服务端解析结果。
"""

import json

import pytest
from sqlalchemy import select

from app.db.models import (
    Architecture,
    ChangeLog,
    Chapter,
    GenerationRun,
    Project,
    Scene,
    Volume,
)


@pytest.fixture()
def project(session):
    """一个带故事圣经的项目，并预置默认阵容。

    `seed_agents` 不随 `session` fixture 自动执行，而本文件的用例都要找
    「修订建议师」；故事圣经则是因为提示词引用了 `{{ story_bible }}`，
    结构化预置缺变量会让渲染整段失败（`allow_missing` 默认关）。
    """
    from app.services.seed_service import seed_agents

    seed_agents(session)
    project = Project(name="雾港", genre="悬疑")
    session.add(project)
    session.flush()
    session.add(
        Architecture(
            project_id=project.id,
            logline="一个替妹妹赎罪的兄长在雾港寻找失踪的船主。",
        )
    )
    session.commit()
    return project


@pytest.fixture()
def runtime_ready(session, project):
    """跑智能体的两个前置条件：一家启用的服务商、角色卡上绑定的模型名。

    真实 HTTP 调用由测试注入的假传输层接管，密钥留空即可。`RuntimeService`
    不再把服务商显示名当模型 ID 回落，所以模型名必须显式绑上。
    """
    from app.db.models import AgentVersion, Provider

    session.add(
        Provider(
            name="测试服务商",
            kind="custom",
            base_url="https://api.example.com/v1",
            enabled=True,
        )
    )
    for version in session.scalars(select(AgentVersion)):
        binding = dict(version.model_binding_json or {})
        if not binding.get("model"):
            version.model_binding_json = {**binding, "model": "test-model"}
    session.commit()


@pytest.fixture()
def scenes(session, project):
    """一卷一章三场：两场可改、一场锁定；章有摘要。"""
    volume = Volume(project_id=project.id, seq=0, name="雾港")
    session.add(volume)
    session.flush()
    chapter = Chapter(
        volume_id=volume.id,
        seq=0,
        title="失踪的船主",
        summary="兄长在码头打听船主的下落",
    )
    session.add(chapter)
    session.flush()
    first = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="找到船主的下落",
        conflict="码头工人不肯开口",
        turn="有人递来一张旧船票",
    )
    second = Scene(
        chapter_id=chapter.id,
        seq=1,
        goal="追问旧船票的来处",
        conflict="船票上的日期是三年前",
        turn="遇见妹妹的旧友",
    )
    locked = Scene(
        chapter_id=chapter.id,
        seq=2,
        goal="锁定场景的目标",
        conflict="锁定冲突",
        turn="锁定转折",
        locked=True,
    )
    session.add_all([first, second, locked])
    session.commit()
    return {"volume": volume, "chapter": chapter, "first": first, "second": second, "locked": locked}


@pytest.fixture()
def many_scenes(session, project):
    """一章五场：足够凑出 13 条互不重复的 (对象, 字段) 建议。"""
    volume = Volume(project_id=project.id, seq=0, name="雾港")
    session.add(volume)
    session.flush()
    chapter = Chapter(
        volume_id=volume.id, seq=0, title="多场景章", summary="这一章的摘要"
    )
    session.add(chapter)
    session.flush()
    for index in range(5):
        session.add(
            Scene(
                chapter_id=chapter.id,
                seq=index,
                goal=f"目标{index + 1}",
                conflict=f"冲突{index + 1}",
                turn=f"转折{index + 1}",
            )
        )
    session.commit()
    return {"volume": volume, "chapter": chapter}


def _architecture_of(session, project):
    return session.scalars(
        select(Architecture).where(Architecture.project_id == project.id)
    ).first()


def _content(suggestions) -> str:
    return json.dumps({"suggestions": suggestions}, ensure_ascii=False)


def _model_client(content: str):
    """固定返回一份模型输出的假传输层（沿用 test_world_api.py 的写法）。"""
    import httpx

    from app.runtime.llm import HttpxChatClient

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 15},
            },
        )

    return HttpxChatClient(transport=httpx.MockTransport(handler))


def _failing_client(status: int = 500, message: str = "服务端炸了"):
    import httpx

    from app.runtime.llm import HttpxChatClient

    def handler(request):
        return httpx.Response(status, json={"error": {"message": message}})

    return HttpxChatClient(transport=httpx.MockTransport(handler))


# ---- Task 1：槽位、预置与任务类型 ----


def test_impact_slots_render_from_extra(session, project):
    """两个新槽位只在该次运行里由调用方显式传值，不进通用项目态投影。"""
    from app.services.runtime_service import RuntimeService
    from app.services import agent_service

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    assert agent is not None
    _agent, _version, prepared = RuntimeService(session).prepare_context(
        project.id,
        agent.id,
        {
            "impact_target": "主角动机改为替妹妹赎罪",
            "impact_candidates": "1. 第1卷 第1章 场景2 · 目标：旧值",
        },
    )
    assert prepared.error is None
    assert "主角动机" in prepared.rendered_prompt
    assert "场景2" in prepared.rendered_prompt


def test_revision_agent_has_contract_and_slots(session, project):
    """预置卡的身份、槽位与输出契约。"""
    from app.db.models.agent import AgentVersion
    from app.services import agent_service

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    assert agent is not None
    assert agent.task_type == "revision_suggest"
    assert agent.preset_key == "revision-advisor"

    version = session.get(AgentVersion, agent.current_version_id)
    assert version is not None
    assert version.context_slots_json == [
        "project_core",
        "story_bible",
        "impact_target",
        "impact_candidates",
    ]

    schema = version.output_schema_json
    assert set(schema["properties"]) == {"suggestions", "open_questions"}
    assert schema["required"] == ["suggestions"]
    item = schema["properties"]["suggestions"]["items"]
    assert set(item["required"]) == {"target_label", "field", "after", "reason"}
    assert schema["properties"]["open_questions"]["type"] == "array"


def test_revision_prompt_asks_for_reasons_in_chinese(session, project):
    """提示词护栏：条数上限、四个可改字段、不编造对象名，且不手写英文键。"""
    from app.db.models.agent import AgentVersion
    from app.services import agent_service

    agent = agent_service.find_by_task_type(session, "revision_suggest")
    version = session.get(AgentVersion, agent.current_version_id)
    prompt = version.system_prompt

    assert "12" in prompt
    for word in ("目标", "冲突", "转折", "摘要"):
        assert word in prompt
    assert "编造" in prompt
    assert "{{ impact_target }}" in prompt
    assert "{{ impact_candidates }}" in prompt


def test_db_slot_source_forwards_only_non_private_names(session, project):
    """`__getattr__` 通用转发：传了键但值为空给 None，下划线开头报 AttributeError。"""
    from app.services.slot_source import DbSlotSource

    source = DbSlotSource(
        session,
        project.id,
        extra_slots={"impact_target": "主角动机改为替妹妹赎罪", "impact_candidates": ""},
    )
    assert source.impact_target() == "主角动机改为替妹妹赎罪"
    # 键传了、值为空：返回 None，上下文组装据此当空槽位跳过。
    assert source.impact_candidates() is None
    with pytest.raises(AttributeError):
        source._no_such_internal_attribute


def test_db_slot_source_raises_for_unknown_slot_names(session, project):
    """不在 extra_slots 里的槽位名必须抛 AttributeError，不许静默为空。

    否则 `hasattr` 恒真、`getattr(..., default)` 永不生效 —— 槽位名拼错
    不会报错，只会让模型少看到一段上下文。
    """
    from app.services.slot_source import DbSlotSource

    source = DbSlotSource(session, project.id, extra_slots={})
    assert hasattr(source, "no_such_slot") is False
    with pytest.raises(AttributeError):
        source.no_such_slot


def test_impact_candidates_slot_is_never_trimmed():
    """候选清单是模型唯一能照抄的对象名来源，压成摘要就等于让它编名字。"""
    from app.runtime.context import SLOT_REGISTRY

    assert SLOT_REGISTRY["impact_candidates"].over_budget == "never"


def test_impact_candidates_slot_has_top_priority():
    """既然永不裁剪，优先级就该是 P_NEVER —— `P_HIGH` + `never` 语义打架。"""
    from app.runtime.context import P_NEVER, SLOT_REGISTRY

    assert SLOT_REGISTRY["impact_candidates"].priority == P_NEVER


# ---- Task 2：suggest() ----


def test_suggest_filters_locked_and_unknown_labels(
    session, project, scenes, runtime_ready
):
    """锁定对象不出现；编造的对象名进 dropped；before 由服务端现取。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    client = _model_client(
        _content(
            [
                {
                    "target_label": "第1卷 第1章 场景1",
                    "field": "目标",
                    "after": "改后的目标",
                    "reason": "动机变了",
                },
                {
                    "target_label": "第1卷 第1章 场景2",
                    "field": "冲突",
                    "after": "改后的冲突",
                    "reason": "冲突要跟上",
                },
                {
                    "target_label": "第1卷 第1章（失踪的船主）",
                    "field": "章的摘要",
                    "after": "改后的摘要",
                    "reason": "摘要要覆盖新动机",
                },
                # 锁定场景：生成时就不该出现在候选里。
                {
                    "target_label": "第1卷 第1章 场景3",
                    "field": "目标",
                    "after": "想改锁定的场景",
                    "reason": "不该出现",
                },
                # 编造的对象名：对不上就丢弃并计数，不猜。
                {
                    "target_label": "第9卷 第9章 场景9",
                    "field": "目标",
                    "after": "编造的对象",
                    "reason": "编的",
                },
                # 正文不在可改的四个字段里。
                {
                    "target_label": "第1卷 第1章 场景1",
                    "field": "正文",
                    "after": "改正文",
                    "reason": "不许改正文",
                },
            ]
        )
    )

    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=client
    )

    assert result["llm_status"] == "ok"
    assert result["run_id"]

    by_label = {s["target_label"]: s for s in result["suggestions"]}
    assert set(by_label) == {
        "第1卷 第1章 场景1",
        "第1卷 第1章 场景2",
        "第1卷 第1章（失踪的船主）",
    }
    # 锁定场景既不出现，也没有被当成「编造」混进建议。
    assert all(s["target_id"] != scenes["locked"].id for s in result["suggestions"])

    # 中文标签归一成英文键，再过白名单。
    assert by_label["第1卷 第1章 场景1"]["field"] == "goal"
    assert by_label["第1卷 第1章 场景2"]["field"] == "conflict"
    assert by_label["第1卷 第1章（失踪的船主）"]["field"] == "summary"
    assert by_label["第1卷 第1章 场景1"]["field_label"] == "目标"
    assert all(
        s["field"] in {"goal", "conflict", "turn", "summary"}
        for s in result["suggestions"]
    )

    # before 一律服务端现取，模型给什么都不能用（这里干脆没给）。
    assert by_label["第1卷 第1章 场景1"]["before"] == "找到船主的下落"
    assert by_label["第1卷 第1章 场景2"]["before"] == "船票上的日期是三年前"
    assert by_label["第1卷 第1章（失踪的船主）"]["before"] == "兄长在码头打听船主的下落"

    # 锁定场景、编造对象、非法字段各丢一条。
    assert result["dropped"] == 3
    assert [s["index"] for s in result["suggestions"]] == [0, 1, 2]
    assert all(s["target_type"] in {"scene", "chapter"} for s in result["suggestions"])


def test_suggest_caps_at_twelve(session, project, many_scenes, runtime_ready):
    """模型给 13 条、且都能落到真实对象上，最终也只留 12 条。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    suggestions = []
    for index in range(4):
        for field, label in (("goal", "目标"), ("conflict", "冲突"), ("turn", "转折")):
            suggestions.append(
                {
                    "target_label": f"第1卷 第1章 场景{index + 1}",
                    "field": label,
                    "after": f"新{label}{index + 1}",
                    "reason": "跟本次改动一致",
                }
            )
    suggestions.append(
        {
            "target_label": "第1卷 第1章（多场景章）",
            "field": "摘要",
            "after": "新摘要",
            "reason": "摘要要覆盖新动机",
        }
    )
    assert len(suggestions) == 13

    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=_model_client(_content(suggestions))
    )

    assert result["llm_status"] == "ok"
    assert len(result["suggestions"]) == 12
    keys = [(s["target_id"], s["field"]) for s in result["suggestions"]]
    assert len(keys) == len(set(keys))
    assert [s["index"] for s in result["suggestions"]] == list(range(12))


def test_suggest_dedupes_same_object_and_field(
    session, project, scenes, runtime_ready
):
    """同一对象同一字段只留第一条，后面的计数丢弃。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    client = _model_client(
        _content(
            [
                {
                    "target_label": "第1卷 第1章 场景1",
                    "field": "目标",
                    "after": "第一次改",
                    "reason": "先来的",
                },
                {
                    "target_label": "第1卷 第1章 场景1",
                    "field": "目标",
                    "after": "第二次改",
                    "reason": "后来的",
                },
            ]
        )
    )

    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=client
    )

    assert result["llm_status"] == "ok"
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["after"] == "第一次改"
    assert result["dropped"] == 1


def test_suggest_accepts_english_field_keys(session, project, scenes, runtime_ready):
    """英文原值也接受：归一化不能只认中文。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    client = _model_client(
        _content(
            [
                {
                    "target_label": "第1卷 第1章 场景2",
                    "field": "turn",
                    "after": "新转折",
                    "reason": "跟本次改动一致",
                }
            ]
        )
    )

    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=client
    )

    assert result["llm_status"] == "ok"
    assert result["suggestions"][0]["field"] == "turn"
    assert result["suggestions"][0]["before"] == "遇见妹妹的旧友"


def test_duplicate_candidate_labels_are_dropped_as_ambiguous(
    session, project, runtime_ready
):
    """标签撞车时不许「第一个匹配就写」：歧义标签整批丢弃。"""
    from app.services import revision_service

    upper = Volume(project_id=project.id, seq=0, name="上卷")
    lower = Volume(project_id=project.id, seq=0, name="下卷")
    session.add_all([upper, lower])
    session.flush()
    upper_chapter = Chapter(volume_id=upper.id, seq=0, title="第一章")
    lower_chapter = Chapter(volume_id=lower.id, seq=0, title="第一章")
    session.add_all([upper_chapter, lower_chapter])
    session.flush()
    session.add_all(
        [
            Scene(chapter_id=upper_chapter.id, seq=0, goal="上卷目标"),
            Scene(chapter_id=lower_chapter.id, seq=0, goal="下卷目标"),
        ]
    )
    session.commit()

    arch = _architecture_of(session, project)
    client = _model_client(
        _content(
            [
                {
                    "target_label": "第1卷 第1章 场景1",
                    "field": "目标",
                    "after": "不知道该写进哪一场",
                    "reason": "标签撞车",
                }
            ]
        )
    )

    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=client
    )

    assert result["llm_status"] == "ok"
    assert result["suggestions"] == []
    assert result["dropped"] == 1


def test_suggest_returns_skipped_when_nothing_downstream(session, project):
    """没有下游场景/章时直接跳过，不调用模型。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    result = revision_service.suggest(session, project.id, "architecture", arch.id)

    assert result == {
        "run_id": None,
        "llm_status": "skipped",
        "suggestions": [],
        "dropped": 0,
        "warning": "没有可建议的下游对象：受影响的场景与章都已锁定，或者还没有下游内容",
    }


def test_suggest_reports_model_failure_without_raising(
    session, project, scenes, runtime_ready
):
    """模型报错时给中文原因，不把异常抛给路由层。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=_failing_client()
    )

    assert result["llm_status"] == "error"
    assert result["suggestions"] == []
    assert "服务端炸了" in result["warning"]
    assert result["run_id"]  # 失败也要留下运行记录，调试台才查得到


def test_suggest_without_provider_reports_error(session, project, scenes):
    """没有可用服务商时同样只返回 error，不抛 500。"""
    from app.db.models import AgentVersion
    from app.services import agent_service, revision_service

    # 只补模型名、不建服务商：把失败点钉在 `resolve_provider` 上，
    # 而不是先被「没绑模型」拦下（那是另一条错误路径）。
    agent = agent_service.find_by_task_type(session, "revision_suggest")
    version = session.get(AgentVersion, agent.current_version_id)
    version.model_binding_json = {"model": "test-model"}
    session.commit()

    arch = _architecture_of(session, project)
    result = revision_service.suggest(
        session,
        project.id,
        "architecture",
        arch.id,
        client=_model_client(_content([])),
    )

    assert result["llm_status"] == "error"
    assert result["suggestions"] == []
    assert "服务商" in result["warning"]


def test_suggest_reports_unstructured_output_without_half_json(
    session, project, scenes, runtime_ready
):
    """模型返回不是契约 JSON 时，不返回半截数据。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    result = revision_service.suggest(
        session,
        project.id,
        "architecture",
        arch.id,
        client=_model_client("模型没按格式返回"),
    )

    assert result["llm_status"] == "error"
    assert result["suggestions"] == []
    assert "契约" in result["warning"]


# ---- Task 3：apply() ----

_SUGGESTIONS = [
    {
        "target_label": "第1卷 第1章 场景1",
        "field": "目标",
        "after": "改后的目标",
        "reason": "动机变了",
    },
    {
        "target_label": "第1卷 第1章 场景2",
        "field": "冲突",
        "after": "改后的冲突",
        "reason": "冲突要跟上",
    },
    {
        "target_label": "第1卷 第1章（失踪的船主）",
        "field": "摘要",
        "after": "改后的摘要",
        "reason": "摘要要覆盖新动机",
    },
]


@pytest.fixture()
def run_with_suggestions(session, project, scenes, runtime_ready):
    """跑一次真实生成链路，拿到一条带三条建议的运行记录。

    应用只认运行记录里服务端存下的建议，所以夹具必须走 `suggest()` ——
    手工拼 `parsed_json` 测不到「服务端在生成时填的 before 被读回」这条。
    """
    from app.services import revision_service

    arch = _architecture_of(session, project)
    result = revision_service.suggest(
        session,
        project.id,
        "architecture",
        arch.id,
        client=_model_client(_content(_SUGGESTIONS)),
    )
    assert result["llm_status"] == "ok"
    assert [s["index"] for s in result["suggestions"]] == [0, 1, 2]
    run = session.get(GenerationRun, result["run_id"])
    assert run is not None
    return run


def _changes_of(session, target_id: str) -> list[ChangeLog]:
    return list(
        session.scalars(select(ChangeLog).where(ChangeLog.target_id == target_id))
    )


def test_apply_writes_only_accepted_and_records_history(
    session, project, scenes, run_with_suggestions
):
    """采纳一条 → 只有那一条落库，改动历史恰好一条且来源是 AI。"""
    from app.services import revision_service

    out = revision_service.apply(
        session, project.id, run_with_suggestions.id, [0]
    )

    assert out["applied"] == [
        {
            "index": 0,
            "target_label": "第1卷 第1章 场景1",
            "field": "goal",
            "field_label": "目标",
        }
    ]
    assert out["skipped"] == []
    assert session.get(Scene, scenes["first"].id).goal == "改后的目标"
    # 没勾的两条一个字都不能动。
    assert session.get(Scene, scenes["second"].id).conflict == "船票上的日期是三年前"
    assert session.get(Chapter, scenes["chapter"].id).summary == "兄长在码头打听船主的下落"

    rows = _changes_of(session, scenes["first"].id)
    assert len(rows) == 1
    assert rows[0].source == "ai"
    assert rows[0].target_type == "scene"
    assert rows[0].action == "update"
    assert rows[0].target_label == "第1卷 第1章 场景1"
    assert rows[0].summary == "修订建议 · 目标"
    assert _changes_of(session, scenes["second"].id) == []


def test_apply_skips_value_changed_after_generation(
    session, project, scenes, run_with_suggestions
):
    """生成后作者手改了目标：该条报「现值已变化」，另一条照常写入。"""
    from app.services import revision_service

    session.get(Scene, scenes["first"].id).goal = "生成后被作者改过"
    session.commit()

    out = revision_service.apply(
        session, project.id, run_with_suggestions.id, [0, 1]
    )

    assert [a["index"] for a in out["applied"]] == [1]
    assert out["skipped"] == [{"index": 0, "reason": "现值已变化"}]
    # 旧建议绝不能覆盖作者的手改。
    assert session.get(Scene, scenes["first"].id).goal == "生成后被作者改过"
    assert session.get(Scene, scenes["second"].id).conflict == "改后的冲突"
    assert _changes_of(session, scenes["first"].id) == []


def test_apply_skips_locked_scene_and_locked_volume(
    session, project, scenes, run_with_suggestions
):
    """生成后才锁上：场景锁与卷锁（章的继承）都要拦住。"""
    from app.services import revision_service

    session.get(Scene, scenes["first"].id).locked = True
    session.get(Volume, scenes["volume"].id).locked = True
    session.commit()

    out = revision_service.apply(
        session, project.id, run_with_suggestions.id, [0, 2]
    )

    assert out["applied"] == []
    assert out["skipped"] == [
        {"index": 0, "reason": "已锁定"},
        {"index": 2, "reason": "已锁定"},
    ]
    assert session.get(Scene, scenes["first"].id).goal == "找到船主的下落"
    assert session.get(Chapter, scenes["chapter"].id).summary == "兄长在码头打听船主的下落"


def test_apply_rejects_out_of_range_and_dedupes_indices(
    session, project, scenes, run_with_suggestions
):
    """越界/负数报「下标无效」；同一下标出现两次只应用一次。"""
    from app.services import revision_service

    out = revision_service.apply(
        session, project.id, run_with_suggestions.id, [99, -1, 0, 0]
    )

    assert [a["index"] for a in out["applied"]] == [0]
    assert out["skipped"] == [
        {"index": 99, "reason": "下标无效"},
        {"index": -1, "reason": "下标无效"},
    ]
    assert session.get(Scene, scenes["first"].id).goal == "改后的目标"
    # 重复下标不能写出两条历史。
    assert len(_changes_of(session, scenes["first"].id)) == 1


def test_apply_is_idempotent(session, project, scenes, run_with_suggestions):
    """同一批再应用一次：不再写库，也不再多记一条历史。"""
    from app.services import revision_service

    first = revision_service.apply(
        session, project.id, run_with_suggestions.id, [0]
    )
    assert [a["index"] for a in first["applied"]] == [0]

    second = revision_service.apply(
        session, project.id, run_with_suggestions.id, [0]
    )

    assert second["applied"] == []
    assert second["skipped"] == [{"index": 0, "reason": "已应用"}]
    assert session.get(Scene, scenes["first"].id).goal == "改后的目标"
    assert len(_changes_of(session, scenes["first"].id)) == 1


def test_apply_rejects_run_from_another_project(
    session, project, run_with_suggestions
):
    """别的项目的运行记录不许拿来写这个项目。"""
    from app.services import revision_service

    other = Project(name="别的项目")
    session.add(other)
    session.commit()

    with pytest.raises(ValueError, match="不存在"):
        revision_service.apply(session, other.id, run_with_suggestions.id, [0])


def test_apply_rejects_unknown_run_and_run_without_suggestions(session, project):
    """运行记录不存在、或它不是一次修订建议运行 → ValueError（路由映射 404/400）。"""
    from app.services import revision_service

    with pytest.raises(ValueError, match="不存在"):
        revision_service.apply(session, project.id, "no-such-run", [0])

    # 别的智能体的运行记录（parsed_json 里没有 suggestions）。
    other_run = GenerationRun(project_id=project.id, parsed_json={"open_questions": []})
    # 解析失败的运行记录（parsed_json 为空）。
    empty_run = GenerationRun(project_id=project.id, parsed_json=None)
    session.add_all([other_run, empty_run])
    session.commit()

    with pytest.raises(ValueError):
        revision_service.apply(session, project.id, other_run.id, [0])
    with pytest.raises(ValueError):
        revision_service.apply(session, project.id, empty_run.id, [0])


def test_apply_skips_deleted_object_and_illegal_field(
    session, project, scenes
):
    """落库前再兜一次：对象已删除、字段不在白名单（运行记录被改过也不写）。"""
    from app.services import revision_service

    run = GenerationRun(
        project_id=project.id,
        parsed_json={
            "suggestions": [
                {"target_label": "第1卷 第1章 场景9", "field": "目标", "after": "新值"},
                {"target_label": "第1卷 第1章（失踪的船主）", "field": "标题", "after": "新标题"},
            ],
            # 服务端解析结果里混进一条指向已删场景、一条越白名单字段。
            "resolved_suggestions": [
                {
                    "index": 0,
                    "target_type": "scene",
                    "target_id": "no-such-scene",
                    "target_label": "第1卷 第1章 场景9",
                    "field": "goal",
                    "field_label": "目标",
                    "before": "",
                    "after": "新值",
                    "reason": "编的",
                },
                {
                    "index": 1,
                    "target_type": "chapter",
                    "target_id": scenes["chapter"].id,
                    "target_label": "第1卷 第1章（失踪的船主）",
                    "field": "title",
                    "field_label": "标题",
                    "before": "失踪的船主",
                    "after": "新标题",
                    "reason": "越权字段",
                },
            ],
        },
    )
    session.add(run)
    session.commit()

    out = revision_service.apply(session, project.id, run.id, [0, 1])

    assert out["applied"] == []
    assert out["skipped"] == [
        {"index": 0, "reason": "对象已删除"},
        {"index": 1, "reason": "字段不可修改"},
    ]
    assert session.get(Chapter, scenes["chapter"].id).title == "失踪的船主"


# ---- 审查修复：解析收紧与归属校验 ----


def test_suggest_counts_overflow_in_dropped(
    session, project, many_scenes, runtime_ready
):
    """超过 12 条的有效建议不能凭空消失：溢出条数计入 dropped。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    suggestions = []
    for index in range(5):
        for field, label in (("goal", "目标"), ("conflict", "冲突"), ("turn", "转折")):
            suggestions.append(
                {
                    "target_label": f"第1卷 第1章 场景{index + 1}",
                    "field": label,
                    "after": f"新{label}{index + 1}",
                    "reason": "跟本次改动一致",
                }
            )
    assert len(suggestions) == 15

    result = revision_service.suggest(
        session,
        project.id,
        "architecture",
        arch.id,
        client=_model_client(_content(suggestions)),
    )

    assert result["llm_status"] == "ok"
    assert len(result["suggestions"]) == 12
    # 15 条全部有效，只留 12 条，剩下 3 条必须记进 dropped。
    assert result["dropped"] == 3
    assert "3" in result["warning"]


def test_normalize_field_requires_exact_match_after_prefix():
    """剥掉已知前缀后必须精确命中字段名，不做结尾模糊匹配。"""
    from app.services import revision_service

    assert revision_service._normalize_field("场景的目标") == "goal"
    assert revision_service._normalize_field("章的摘要") == "summary"
    assert revision_service._normalize_field("字段冲突") == "conflict"
    assert revision_service._normalize_field("转折") == "turn"
    # 「目标和冲突」不是任何一个字段，猜成后者比丢弃更危险。
    assert revision_service._normalize_field("目标和冲突") is None
    assert revision_service._normalize_field("目标或冲突") is None
    assert revision_service._normalize_field("正文") is None


def test_suggest_accepts_model_labels_with_line_numbers(
    session, project, scenes, runtime_ready
):
    """模型把候选行整行抄回来（带 `1.` 编号与 `｜现值`）：剥掉后仍精确命中。"""
    from app.services import revision_service

    arch = _architecture_of(session, project)
    client = _model_client(
        _content(
            [
                {
                    "target_label": "1. 第1卷 第1章 场景1｜目标：找到船主的下落",
                    "field": "场景的目标",
                    "after": "改后的目标",
                    "reason": "整行抄",
                },
                {
                    "target_label": "2. 第1卷 第1章 场景2",
                    "field": "的冲突",
                    "after": "改后的冲突",
                    "reason": "剥前缀",
                },
            ]
        )
    )

    result = revision_service.suggest(
        session, project.id, "architecture", arch.id, client=client
    )

    assert result["llm_status"] == "ok"
    assert result["dropped"] == 0
    assert [(s["target_id"], s["field"]) for s in result["suggestions"]] == [
        (scenes["first"].id, "goal"),
        (scenes["second"].id, "conflict"),
    ]
    assert result["suggestions"][0]["before"] == "找到船主的下落"


def test_suggest_errors_when_suggestions_is_not_an_array(
    session, project, scenes, runtime_ready, monkeypatch
):
    """契约挡不住时（自定义契约）也不能把「不是数组」当成「没什么要改」。"""
    from app.services import revision_service

    class _FakeRun:
        id = "fake-run"
        parsed_json = {"suggestions": "不是数组"}

    class _FakeResult:
        status = "ok"
        structured = True
        parse_error = None
        error = None

    monkeypatch.setattr(
        revision_service.RuntimeService,
        "execute",
        lambda self, *args, **kwargs: (_FakeRun(), _FakeResult()),
    )

    arch = _architecture_of(session, project)
    result = revision_service.suggest(session, project.id, "architecture", arch.id)

    assert result["llm_status"] == "error"
    assert result["suggestions"] == []
    assert "数组" in result["warning"]
    assert result["run_id"] == "fake-run"


def test_apply_writes_when_before_is_empty(
    session, project, scenes, runtime_ready
):
    """生成时字段是空串：`"" == ""` 要算通过，空字段否则永远应用不上。"""
    from app.services import revision_service

    empty = Scene(
        chapter_id=scenes["chapter"].id, seq=3, goal="", conflict="", turn=""
    )
    session.add(empty)
    session.commit()

    arch = _architecture_of(session, project)
    result = revision_service.suggest(
        session,
        project.id,
        "architecture",
        arch.id,
        client=_model_client(
            _content(
                [
                    {
                        "target_label": "第1卷 第1章 场景4",
                        "field": "目标",
                        "after": "从无到有的目标",
                        "reason": "这一场还没有目标",
                    }
                ]
            )
        ),
    )

    assert result["suggestions"][0]["before"] == ""

    out = revision_service.apply(session, project.id, result["run_id"], [0])

    assert [a["index"] for a in out["applied"]] == [0]
    assert out["skipped"] == []
    assert session.get(Scene, empty.id).goal == "从无到有的目标"


def test_apply_skips_object_from_another_project(session, project, scenes):
    """运行记录指向别的项目的对象：不写、不记历史，报「对象不属于这个项目」。"""
    from app.services import revision_service

    other = Project(name="别的项目")
    session.add(other)
    session.commit()
    other_volume = Volume(project_id=other.id, seq=0, name="别卷")
    session.add(other_volume)
    session.flush()
    other_chapter = Chapter(volume_id=other_volume.id, seq=0, title="别章")
    session.add(other_chapter)
    session.flush()
    foreign = Scene(chapter_id=other_chapter.id, seq=0, goal="别处的目标")
    session.add(foreign)
    session.commit()

    run = GenerationRun(
        project_id=project.id,
        parsed_json={
            "suggestions": [
                {"target_label": "第1卷 第1章 场景9", "field": "目标", "after": "新值"}
            ],
            "resolved_suggestions": [
                {
                    "index": 0,
                    "target_type": "scene",
                    "target_id": foreign.id,
                    "target_label": "第1卷 第1章 场景9",
                    "field": "goal",
                    "field_label": "目标",
                    "before": "别处的目标",
                    "after": "新值",
                    "reason": "越项目",
                }
            ],
        },
    )
    session.add(run)
    session.commit()

    out = revision_service.apply(session, project.id, run.id, [0])

    assert out["applied"] == []
    assert out["skipped"] == [{"index": 0, "reason": "对象不属于这个项目"}]
    assert session.get(Scene, foreign.id).goal == "别处的目标"
