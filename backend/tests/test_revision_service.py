"""修订建议：槽位、预置、任务类型（Task 1）与生成（Task 2）。

Task 1 的用例先跑红、再实现：新槽位没注册时上下文组装会整段跳过，
新任务类型没登记时 `find_by_task_type` 找不到智能体。
Task 2 的用例同样先跑红：`revision_service` 模块一开始并不存在。
"""

import json

import pytest
from sqlalchemy import select

from app.db.models import Architecture, Chapter, Project, Scene, Volume


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
