import json

import httpx
import pytest

from app.db.models import (
    Act,
    Agent,
    AgentVersion,
    Architecture,
    Chapter,
    Idea,
    PipelineRunNode,
    Project,
    Provider,
    Scene,
    SettingEntry,
    Volume,
)
from app.pipeline_executors import EXECUTORS, get_executor
from app.services.seed_service import seed_tools
from app.runtime.llm import HttpxChatClient
from app.services import runtime_service


def _project(session, name="雾港"):
    project = Project(name=name)
    session.add(project)
    session.commit()
    return project


def _provider(session):
    provider = Provider(name="测试", base_url="https://api.example.com/v1")
    session.add(provider)
    session.commit()
    # 架构与章纲预置都要读 tool_library 槽位；没有工具模板时渲染会失败，
    # 那是测试缺前置，不是执行器的问题。
    seed_tools(session)
    return provider


def _agent(session, task_type, model="test-model"):
    """夹具要带上预置的输出契约 —— 没有契约的智能体会走纯文本路径，
    结构化摘要永远出不来，测出来的不是执行器的行为。"""
    from app.agents.roster import DEFAULT_ROSTER

    preset = next((p for p in DEFAULT_ROSTER if p["task_type"] == task_type), None)
    agent = Agent(name=f"{task_type}-agent", task_type=task_type)
    session.add(agent)
    session.commit()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        model_binding_json={"model": model},
        system_prompt=preset["system_prompt"] if preset else "",
        context_slots_json=preset["context_slots"] if preset else [],
        output_schema_json=preset["output_schema"] if preset else None,
    )
    session.add(version)
    session.commit()
    agent.current_version_id = version.id
    session.commit()
    return agent


def _node(task_type="idea_parse", **kwargs):
    return PipelineRunNode(run_id="run", seq=0, name="节点", task_type=task_type, **kwargs)


def _patch_llm(monkeypatch, payload):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps(payload, ensure_ascii=False)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    monkeypatch.setattr(
        runtime_service.RuntimeService,
        "_resolve_client",
        lambda self, timeout: HttpxChatClient(transport=httpx.MockTransport(handler)),
    )


def test_unknown_task_type_has_no_executor():
    assert get_executor("polish") is None
    assert set(EXECUTORS) == {
        "idea_parse",
        "architecture",
        "worldbuilding",
        "chapter_plan",
        "scene_plan",
    }


# ---- 灵感解析 ----

def test_idea_parse_blocks_without_an_idea(session):
    project = _project(session)
    reason = EXECUTORS["idea_parse"].check(session, project, _node())

    assert reason and "灵感与解析" in reason


def test_idea_parse_writes_the_parsed_card(session, monkeypatch):
    project = _project(session)
    _provider(session)
    _agent(session, "idea_parse")
    idea = Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官")
    session.add(idea)
    session.commit()
    _patch_llm(
        monkeypatch,
        {
            "genre": "悬疑",
            "premise": "验尸官能听见死者遗言",
            "protagonist_desire": "查清母亲之死",
            "conflict_source": "警局隐瞒",
            "open_questions": ["遗言有没有说谎的可能？"],
        },
    )

    assert EXECUTORS["idea_parse"].check(session, project, _node()) is None
    outcome = EXECUTORS["idea_parse"].run(session, project, _node())

    assert outcome.generation_run_id
    assert outcome.summary["structured"] is True
    assert outcome.summary["open_questions"] == 1
    assert outcome.summary["review_path"] == "/idea"
    session.refresh(idea)
    assert idea.parsed_json["genre"] == "悬疑"
    # 作者原话一字不动（D-04）
    assert idea.raw_text == "能听见死者遗言的验尸官"


# ---- 架构推荐 ----

def test_architecture_blocks_without_a_parsed_idea(session):
    project = _project(session)
    reason = EXECUTORS["architecture"].check(session, project, _node())

    assert reason and "灵感解析" in reason


def test_architecture_does_not_write_the_architecture_table(session, monkeypatch):
    project = _project(session)
    _provider(session)
    _agent(session, "architecture")
    session.add(Idea(project_id=project.id, raw_text="x", parsed_json={"genre": "悬疑"}))
    session.commit()
    _patch_llm(
        monkeypatch,
        {
            "options": [
                {"tool": "三幕", "reason": "合适", "fit_score": 0.9, "risks": []},
                {"tool": "起承转合", "reason": "也行", "fit_score": 0.8, "risks": ["节奏平"]},
            ],
            "story_bible_v0": {"logline": "一句话"},
        },
    )

    assert EXECUTORS["architecture"].check(session, project, _node("architecture")) is None
    outcome = EXECUTORS["architecture"].run(session, project, _node("architecture"))

    assert outcome.summary["options"] == 2
    assert outcome.summary["has_story_bible"] is True
    assert outcome.summary["review_path"] == "/architecture"
    # 作者要自己去拍板，管线不替他采纳（D-03）
    assert session.query(Architecture).count() == 0


# ---- 世界观 ----

def test_worldbuilding_blocks_without_an_adopted_bible(session):
    project = _project(session)
    reason = EXECUTORS["worldbuilding"].check(session, project, _node("worldbuilding"))

    assert reason and "架构推荐" in reason


def test_worldbuilding_counts_candidates(session, monkeypatch):
    project = _project(session)
    _provider(session)
    _agent(session, "worldbuilding")
    arch = Architecture(project_id=project.id, logline="一句话")
    session.add(arch)
    session.add(Idea(project_id=project.id, raw_text="x", parsed_json={"genre": "悬疑"}))
    session.commit()
    _patch_llm(
        monkeypatch,
        {
            "entries": [
                {"name": "南滨旧城", "type": "地点", "summary": "海边小城"},
                {"name": "沈砚", "type": "人物", "summary": "验尸官"},
                {"name": "静档原则", "type": "规则", "summary": "记忆不得回溯"},
            ],
            "open_questions": [],
        },
    )

    outcome = EXECUTORS["worldbuilding"].run(session, project, _node("worldbuilding"))

    assert outcome.summary["candidates"] == 3
    assert outcome.summary["review_path"] == "/world"


# ---- 章纲 ----

def test_chapter_plan_blocks_without_acts(session):
    project = _project(session)
    reason = EXECUTORS["chapter_plan"].check(session, project, _node("chapter_plan"))

    assert reason and "幕骨架" in reason


def test_chapter_plan_counts_volumes_and_chapters(session, monkeypatch):
    project = _project(session)
    _provider(session)
    _agent(session, "chapter_plan")
    arch = Architecture(project_id=project.id, logline="一句话")
    session.add(arch)
    session.add(Idea(project_id=project.id, raw_text="x", parsed_json={"genre": "悬疑"}))
    session.commit()
    session.add(Act(architecture_id=arch.id, seq=1, name="第一幕"))
    session.add(SettingEntry(project_id=project.id, type="place", name="南滨旧城", summary="海边小城"))
    session.commit()
    _patch_llm(
        monkeypatch,
        {
            "volumes": [
                {
                    "name": "第一卷",
                    "act_seq": 1,
                    "chapters": [{"title": "开端"}, {"title": "转折"}],
                }
            ],
            "open_questions": [],
        },
    )

    outcome = EXECUTORS["chapter_plan"].run(session, project, _node("chapter_plan"))

    assert outcome.summary["volumes"] == 1
    assert outcome.summary["chapters"] == 2


# ---- 场景卡 ----

def test_scene_plan_blocks_without_a_chapter(session):
    project = _project(session)
    reason = EXECUTORS["scene_plan"].check(session, project, _node("scene_plan"))

    assert reason and "章节设计" in reason


def test_scene_plan_uses_the_first_chapter(session, monkeypatch):
    project = _project(session)
    _provider(session)
    _agent(session, "scene_plan")
    session.add(Architecture(project_id=project.id, logline="一句话"))
    session.add(Idea(project_id=project.id, raw_text="x", parsed_json={"genre": "悬疑"}))
    session.add(SettingEntry(project_id=project.id, type="place", name="南滨旧城", summary="海边小城"))
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    _patch_llm(
        monkeypatch,
        {
            "scenes": [
                {
                    "goal": "找到录音带",
                    "conflict": "档案室有人",
                    "turn": "录音带里是自己的声音",
                    "characters": [],
                }
            ],
            "open_questions": [],
        },
    )

    assert EXECUTORS["scene_plan"].check(session, project, _node("scene_plan")) is None
    outcome = EXECUTORS["scene_plan"].run(session, project, _node("scene_plan"))

    assert outcome.summary["chapter_id"] == chapter.id
    assert outcome.summary["scenes"] == 1
    # 管线不写场景表：作者要去「章节设计」确认
    assert session.query(Scene).count() == 0


def test_bound_agent_wins_over_task_type_lookup(session, monkeypatch):
    project = _project(session)
    _provider(session)
    default_agent = _agent(session, "idea_parse", model="default-model")
    chosen = _agent(session, "idea_parse", model="chosen-model")
    session.add(Idea(project_id=project.id, raw_text="x"))
    session.commit()
    captured = {}

    def handler(request):
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"genre": "悬疑"})}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    monkeypatch.setattr(
        runtime_service.RuntimeService,
        "_resolve_client",
        lambda self, timeout: HttpxChatClient(transport=httpx.MockTransport(handler)),
    )
    node = _node(agent_id=chosen.id)

    EXECUTORS["idea_parse"].run(session, project, node)

    assert captured["model"] == "chosen-model"
    assert default_agent.id != chosen.id


def test_missing_context_is_a_failure_not_an_empty_success(session, monkeypatch):
    """缺上下文槽位时模型根本没被调用 —— 执行器必须报错，不能返回空摘要。

    否则管线会显示「完成」，作者以为生成过了。
    """
    project = _project(session)
    _provider(session)
    _agent(session, "worldbuilding")
    session.add(Architecture(project_id=project.id, logline="一句话"))
    session.add(Idea(project_id=project.id, raw_text="x"))  # 没有 parsed_json
    session.commit()

    with pytest.raises(ValueError, match="parsed_idea"):
        EXECUTORS["worldbuilding"].run(session, project, _node("worldbuilding"))


def test_scene_plan_tolerates_an_empty_timeline(session, monkeypatch):
    """timeline 在空项目里天然为空；场景策划必须照样能跑。"""
    project = _project(session)
    _provider(session)
    _agent(session, "scene_plan")
    session.add(Architecture(project_id=project.id, logline="一句话"))
    session.add(Idea(project_id=project.id, raw_text="x", parsed_json={"genre": "悬疑"}))
    session.add(SettingEntry(project_id=project.id, type="place", name="南滨旧城", summary="海边小城"))
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    session.add(Chapter(volume_id=volume.id, seq=0, title="第一章"))
    session.commit()
    _patch_llm(
        monkeypatch,
        {
            "scenes": [{"goal": "g", "conflict": "c", "turn": "t"}],
            "open_questions": [],
        },
    )

    outcome = EXECUTORS["scene_plan"].run(session, project, _node("scene_plan"))

    assert outcome.summary["scenes"] == 1
