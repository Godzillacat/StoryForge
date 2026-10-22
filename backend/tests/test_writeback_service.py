import pytest

from app.db.models import (
    Agent,
    Chapter,
    Foreshadow,
    GenerationRun,
    Project,
    Scene,
    SettingEntry,
    Volume,
)
from app.runtime.execute import RunResult
from app.services import writeback_service


def _seed(session, *, body: str = "陈默把录音带收进怀里，雨停了。"):
    project = Project(name="回写项目")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章", summary="旧摘要")
    session.add(chapter)
    session.commit()
    scene = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="找到录音带",
        body=body,
        characters_json=[],
    )
    session.add(scene)
    session.commit()
    character = SettingEntry(
        project_id=project.id,
        type="character",
        name="陈默",
        aliases_json=["阿默"],
        current_state="仍在找录音带",
    )
    foreshadow = Foreshadow(project_id=project.id, name="失忆的录音带")
    session.add_all([character, foreshadow])
    session.commit()
    return project, scene, character, foreshadow


def _add_writer(session) -> Agent:
    agent = Agent(name="回写助手", task_type="writeback", enabled=True)
    session.add(agent)
    session.commit()
    return agent


def _result(parsed=None, *, structured=True, status="ok", error=None):
    return RunResult(
        rendered_prompt="",
        raw_output="",
        parsed=parsed,
        structured=structured,
        parse_error=None,
        prompt_tokens=1,
        completion_tokens=1,
        cost_estimate=0.0,
        duration_ms=1,
        status=status,
        error=error,
        trimmed={},
    )


def _patch(monkeypatch, session, project, result):
    run = GenerationRun(project_id=project.id, status="ok")
    session.add(run)
    session.commit()

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        return run, result

    monkeypatch.setattr(writeback_service.RuntimeService, "execute", fake_execute)
    return run


def test_suggest_requires_body(session):
    project, scene, _character, _foreshadow = _seed(session, body="   ")
    with pytest.raises(ValueError, match="还没有已采纳正文"):
        writeback_service.suggest(session, scene.id)


def test_suggest_without_agent_is_skipped(session):
    project, scene, _character, _foreshadow = _seed(session)

    result = writeback_service.suggest(session, scene.id)

    assert result["llm_status"] == "skipped"
    assert "找不到回写助手" in result["warning"]
    assert result["character_updates"] == []


def test_suggest_matches_names_and_reports_unknowns(session, monkeypatch):
    project, scene, character, foreshadow = _seed(session)
    _add_writer(session)
    run = _patch(
        monkeypatch,
        session,
        project,
        _result(
            {
                "chapter_summary": "陈默拿到了录音带，雨停了。",
                "character_updates": [
                    {
                        "character": "阿默",
                        "current_state": "拿到了录音带",
                        "evidence": "陈默把录音带收进怀里。",
                    },
                    {
                        "character": "不存在的人",
                        "current_state": "失踪",
                    },
                ],
                "foreshadow_pays": [
                    {"name": "失忆的录音带", "evidence": "把录音带收进怀里。"},
                    {"name": "不存在的伏笔"},
                ],
                "open_questions": ["录音带里是谁的声音？"],
            }
        ),
    )

    result = writeback_service.suggest(session, scene.id)

    assert result["llm_status"] == "ok"
    assert result["run_id"] == run.id
    assert result["chapter_summary"] == "陈默拿到了录音带，雨停了。"
    assert result["character_updates"] == [
        {
            "entry_id": character.id,
            "name": "陈默",
            "current_state": "拿到了录音带",
            "evidence": "陈默把录音带收进怀里。",
        }
    ]
    assert result["foreshadow_pays"][0]["foreshadow_id"] == foreshadow.id
    assert any("不存在的人" in warning for warning in result["warnings"])
    assert any("不存在的伏笔" in warning for warning in result["warnings"])
    assert result["open_questions"] == ["录音带里是谁的声音？"]


def test_suggest_unstructured_and_errors(session, monkeypatch):
    project, scene, _character, _foreshadow = _seed(session)
    _add_writer(session)

    _patch(monkeypatch, session, project, _result(None, structured=False))
    unstructured = writeback_service.suggest(session, scene.id)
    assert unstructured["llm_status"] == "unstructured"
    assert unstructured["run_id"] is not None

    _patch(
        monkeypatch,
        session,
        project,
        _result(status="error", error={"kind": "network", "message": "连接失败"}),
    )
    error = writeback_service.suggest(session, scene.id)
    assert error["llm_status"] == "error"
    assert "连接失败" in error["warning"]

    def fake_raise(self, project_id, agent_id, extra=None, allow_missing=None):
        raise RuntimeError("凭据无法解密")

    monkeypatch.setattr(writeback_service.RuntimeService, "execute", fake_raise)
    unexpected = writeback_service.suggest(session, scene.id)
    assert unexpected["llm_status"] == "error"
    assert "凭据无法解密" in unexpected["warning"]


def test_open_questions_must_be_a_list(session, monkeypatch):
    project, scene, _character, _foreshadow = _seed(session)
    _add_writer(session)
    _patch(
        monkeypatch,
        session,
        project,
        _result(
            {
                "chapter_summary": "摘要",
                "character_updates": [],
                "foreshadow_pays": [],
                # 字符串不能被逐字符拆成一堆「问题」
                "open_questions": "只有一个问题",
            }
        ),
    )

    result = writeback_service.suggest(session, scene.id)

    assert result["open_questions"] == []


def test_apply_updates_only_selected_targets(session):
    project, scene, character, foreshadow = _seed(session)

    result = writeback_service.apply(
        session,
        scene.id,
        {
            "chapter_summary": "陈默拿到了录音带。",
            "character_updates": [
                {"entry_id": character.id, "current_state": "拿到了录音带"}
            ],
            "foreshadow_pays": [{"foreshadow_id": foreshadow.id}],
        },
    )

    assert result["chapter_summary"] == "陈默拿到了录音带。"
    session.refresh(character)
    session.refresh(foreshadow)
    chapter = session.get(Chapter, scene.chapter_id)
    assert chapter.summary == "陈默拿到了录音带。"
    assert character.current_state == "拿到了录音带"
    assert foreshadow.actual_pay_scene_id == scene.id


def test_apply_empty_payload_changes_nothing(session):
    project, scene, character, foreshadow = _seed(session)
    chapter = session.get(Chapter, scene.chapter_id)

    result = writeback_service.apply(session, scene.id, {})

    assert result == {
        "chapter_summary": chapter.summary,
        "character_updates": [],
        "foreshadow_pays": [],
        "skipped": [],
    }
    assert chapter.summary == "旧摘要"
    assert character.current_state == "仍在找录音带"
    assert foreshadow.actual_pay_scene_id is None


def test_apply_rejects_entries_from_another_project(session):
    project, scene, _character, foreshadow = _seed(session)
    other = Project(name="另一个项目")
    session.add(other)
    session.commit()
    foreign = SettingEntry(project_id=other.id, type="character", name="外人")
    session.add(foreign)
    session.commit()

    with pytest.raises(ValueError, match="不属于这个项目"):
        writeback_service.apply(
            session,
            scene.id,
            {"character_updates": [{"entry_id": foreign.id, "current_state": "在场"}]},
        )


def test_apply_rejects_non_character_entries(session):
    project, scene, _character, _foreshadow = _seed(session)
    place = SettingEntry(project_id=project.id, type="place", name="旧城")
    session.add(place)
    session.commit()

    with pytest.raises(ValueError, match="不是人物条目"):
        writeback_service.apply(
            session,
            scene.id,
            {"character_updates": [{"entry_id": place.id, "current_state": "下雨"}]},
        )


def test_apply_rejects_unknown_ids(session):
    project, scene, _character, _foreshadow = _seed(session)

    with pytest.raises(ValueError, match="人物不存在"):
        writeback_service.apply(
            session,
            scene.id,
            {"character_updates": [{"entry_id": "nope", "current_state": "在场"}]},
        )

    with pytest.raises(ValueError, match="伏笔不存在"):
        writeback_service.apply(
            session,
            scene.id,
            {"foreshadow_pays": [{"foreshadow_id": "nope"}]},
        )


def test_missing_scene(session):
    with pytest.raises(ValueError, match="场景不存在"):
        writeback_service.suggest(session, "nope")


# ---- 锁定（P4a）----

def test_apply_skips_a_locked_character_and_applies_the_rest(session):
    project, scene, character, foreshadow = _seed(session)
    character.locked = True
    session.commit()

    result = writeback_service.apply(
        session,
        scene.id,
        {
            "chapter_summary": "陈默拿到了录音带。",
            "character_updates": [
                {"entry_id": character.id, "current_state": "拿到了录音带"}
            ],
            "foreshadow_pays": [{"foreshadow_id": foreshadow.id}],
        },
    )

    session.refresh(character)
    session.refresh(foreshadow)
    chapter = session.get(Chapter, scene.chapter_id)
    assert chapter.summary == "陈默拿到了录音带。"
    assert character.current_state == "仍在找录音带"
    assert foreshadow.actual_pay_scene_id == scene.id
    assert result["character_updates"] == []
    assert result["skipped"] == [
        {"type": "character", "name": "陈默", "reason": "设定条目已锁定"}
    ]


def test_apply_skips_the_chapter_summary_when_the_chapter_is_locked(session):
    project, scene, character, foreshadow = _seed(session)
    chapter = session.get(Chapter, scene.chapter_id)
    chapter.locked = True
    session.commit()

    result = writeback_service.apply(
        session, scene.id, {"chapter_summary": "陈默拿到了录音带。"}
    )

    session.refresh(chapter)
    assert chapter.summary == "旧摘要"
    assert result["skipped"][0]["type"] == "chapter_summary"


def test_apply_does_not_skip_a_locked_scene(session):
    """回写改的是章节摘要 / 人物状态 / 伏笔，不碰正文 —— 场景锁不该挡住它。"""
    project, scene, character, foreshadow = _seed(session)
    scene.locked = True
    character.locked = False
    session.commit()

    result = writeback_service.apply(
        session,
        scene.id,
        {"character_updates": [{"entry_id": character.id, "current_state": "拿到了录音带"}]},
    )

    session.refresh(character)
    assert character.current_state == "拿到了录音带"
    assert result["skipped"] == []
