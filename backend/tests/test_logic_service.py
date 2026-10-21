import pytest

from app.db.models import (
    Agent,
    AuditIssue,
    Chapter,
    GenerationRun,
    Project,
    Scene,
    Volume,
)
from app.runtime.execute import RunResult
from app.services import audit_service, logic_service, text_service


def _seed_scene(
    session, *, body: str = "档案室的门在身后合上。", level: str = "loose"
) -> tuple[Project, Scene]:
    project = Project(name="逻辑项目", logic_check_level=level)
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="找到录音带", body=body)
    session.add(scene)
    session.commit()
    return project, scene


def _add_checker(session) -> Agent:
    agent = Agent(name="逻辑审查官", task_type="logic_check", enabled=True)
    session.add(agent)
    session.commit()
    return agent


def _result(parsed=None, *, structured: bool = False, status: str = "ok", error=None):
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


def _patch_execute(monkeypatch, session, project, result):
    run = GenerationRun(project_id=project.id, status="ok")
    session.add(run)
    session.commit()
    seen: dict = {}

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        seen["extra"] = extra
        seen["allow_missing"] = allow_missing
        return run, result

    monkeypatch.setattr(logic_service.RuntimeService, "execute", fake_execute)
    return run, seen


def _issue_payload(**overrides):
    value = {
        "layer": "因果链",
        "severity": "严重",
        "quote": "他前一刻还在城南，下一刻已经站在城北。",
        "rule_ref": "故事内时间线：同一天傍晚",
        "explanation": "中间没有交代移动，因果链断裂。",
        "reader_impact": "读者会觉得场景跳了。",
        "options": ["补一段移动", "改地点"],
    }
    value.update(overrides)
    return value


def test_text_stage_requires_body(session):
    project, scene = _seed_scene(session, body="  ")
    with pytest.raises(ValueError, match="还没有已采纳正文"):
        logic_service.run_logic_check(session, scene.id, "text")


def test_invalid_stage_rejected(session):
    project, scene = _seed_scene(session)
    with pytest.raises(ValueError, match="未知的逻辑自检时机"):
        logic_service.run_logic_check(session, scene.id, "draft")


def test_plan_stage_skips_the_adopted_body(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    run, seen = _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )

    result = logic_service.run_logic_check(session, scene.id, "plan")

    assert result["llm_status"] == "ok"
    assert result["run_id"] == run.id
    assert seen["extra"]["skip_scene_text"] is True
    assert seen["allow_missing"] is True
    assert result["issues"][0]["check_type"] == "logic"
    assert result["issues"][0]["layer"] == "causality"
    assert result["issues"][0]["layer_label"] == "因果链"
    assert result["issues"][0]["stage"] == "plan"


def test_text_stage_does_not_skip_body(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _run, seen = _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert result["llm_status"] == "ok"
    assert not seen["extra"].get("skip_scene_text")


def test_loose_level_drops_minor_issues(session, monkeypatch):
    project, scene = _seed_scene(session, level="loose")
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result(
            {
                "issues": [
                    _issue_payload(severity="致命"),
                    _issue_payload(quote="另一句。", severity="严重"),
                    _issue_payload(quote="第三句。", severity="提示"),
                ]
            },
            structured=True,
        ),
    )

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert [issue["severity"] for issue in result["issues"]] == ["critical", "major"]


def test_standard_level_keeps_minor_issues(session, monkeypatch):
    project, scene = _seed_scene(session, level="standard")
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result(
            {"issues": [_issue_payload(severity="提示")]},
            structured=True,
        ),
    )

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert [issue["severity"] for issue in result["issues"]] == ["minor"]


def test_normalization_drops_empty_quotes_and_unknown_layers(session, monkeypatch):
    project, scene = _seed_scene(session, level="standard")
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result(
            {
                "issues": [
                    _issue_payload(layer="不存在的层", quote="句子一。"),
                    _issue_payload(quote=""),
                    _issue_payload(quote="句子二。", options="改故事"),
                ]
            },
            structured=True,
        ),
    )

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert len(result["issues"]) == 2
    assert result["issues"][0]["layer"] == "other"
    assert result["issues"][1]["options"] == []


def test_new_check_supersedes_same_stage_only(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )

    plan_first = logic_service.run_logic_check(session, scene.id, "plan")
    plan_issue_id = plan_first["issues"][0]["id"]
    text_result = logic_service.run_logic_check(session, scene.id, "text")
    plan_second = logic_service.run_logic_check(session, scene.id, "plan")

    # text 不影响 plan 的 open 问题
    assert text_result["issues"][0]["stage"] == "text"
    assert session.get(AuditIssue, plan_issue_id).status == "superseded"
    assert plan_second["issues"][0]["id"] != plan_issue_id
    assert plan_second["issues"][0]["stage"] == "plan"


def test_exception_suppresses_same_stage(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )

    first = logic_service.run_logic_check(session, scene.id, "text")
    audit_service.resolve_issue(session, first["issues"][0]["id"], "exception")

    # plan 阶段同句不受 text 的例外影响
    plan = logic_service.run_logic_check(session, scene.id, "plan")
    text = logic_service.run_logic_check(session, scene.id, "text")

    assert len(plan["issues"]) == 1
    assert text["suppressed"] == 1
    assert text["issues"] == []


def test_missing_checker_is_a_warning(session):
    project, scene = _seed_scene(session)

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert result["llm_status"] == "skipped"
    assert "找不到逻辑审查官" in result["warning"]
    assert result["issues"] == []


def test_model_unavailable_is_skipped(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise ValueError("没有可用的服务商")

    monkeypatch.setattr(logic_service.RuntimeService, "execute", fake_execute)

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert result["llm_status"] == "skipped"
    assert "没有可用的服务商" in result["warning"]


def test_unexpected_error_degrades(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise RuntimeError("凭据无法解密")

    monkeypatch.setattr(logic_service.RuntimeService, "execute", fake_execute)

    result = logic_service.run_logic_check(session, scene.id, "text")

    assert result["llm_status"] == "error"
    assert "凭据无法解密" in result["warning"]


def test_run_error_and_unstructured_degrade(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result(status="error", error={"kind": "network", "message": "连接失败"}),
    )
    error = logic_service.run_logic_check(session, scene.id, "text")
    assert error["llm_status"] == "error"
    assert "连接失败" in error["warning"]

    _patch_execute(monkeypatch, session, project, _result(None, structured=False))
    unstructured = logic_service.run_logic_check(session, scene.id, "text")
    assert unstructured["llm_status"] == "unstructured"


def test_list_is_stage_scoped(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )

    empty = logic_service.list_logic_check(session, scene.id, "plan")
    assert empty["issues"] == [] and empty["last_checked_at"] is None

    logic_service.run_logic_check(session, scene.id, "plan")
    plan = logic_service.list_logic_check(session, scene.id, "plan")
    text = logic_service.list_logic_check(session, scene.id, "text")

    assert len(plan["issues"]) == 1
    assert plan["last_checked_at"]
    assert text["issues"] == []
    assert text["last_checked_at"] is None


def test_fingerprints_are_stage_isolated(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )

    logic_service.run_logic_check(session, scene.id, "plan")
    logic_service.run_logic_check(session, scene.id, "text")

    fingerprints = [
        row.fingerprint
        for row in session.query(AuditIssue).order_by(AuditIssue.created_at).all()
    ]
    assert fingerprints[0].startswith("logic:plan:")
    assert fingerprints[1].startswith("logic:text:")
    assert fingerprints[0] != fingerprints[1]


def test_body_change_supersedes_text_but_keeps_plan_issues(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )
    plan = logic_service.run_logic_check(session, scene.id, "plan")
    text = logic_service.run_logic_check(session, scene.id, "text")

    text_service.save_body(session, scene.id, "换了一份正文。")

    assert session.get(AuditIssue, plan["issues"][0]["id"]).status == "open"
    assert session.get(AuditIssue, text["issues"][0]["id"]).status == "superseded"


def test_failed_recheck_keeps_previous_open_issues(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )
    first = logic_service.run_logic_check(session, scene.id, "text")
    issue_id = first["issues"][0]["id"]

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise ValueError("没有可用的服务商")

    monkeypatch.setattr(logic_service.RuntimeService, "execute", fake_execute)
    second = logic_service.run_logic_check(session, scene.id, "text")

    assert second["llm_status"] == "skipped"
    assert [issue["id"] for issue in second["issues"]] == [issue_id]
    assert session.get(AuditIssue, issue_id).status == "open"


def test_audit_and_logic_do_not_supersede_each_other(session, monkeypatch):
    project, scene = _seed_scene(
        session,
        body=(
            "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
            "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
        ),
    )
    _add_checker(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result({"issues": [_issue_payload()]}, structured=True),
    )
    logic_first = logic_service.run_logic_check(session, scene.id, "text")
    logic_issue_id = logic_first["issues"][0]["id"]

    # 没有审校智能体时，一致性审计只跑规则层；它不该碰逻辑问题。
    audit = audit_service.run_audit(session, scene.id)
    assert audit["issues"]
    assert session.get(AuditIssue, logic_issue_id).status == "open"
    assert all(issue["check_type"] == "consistency" for issue in audit["issues"])
    assert all(
        issue["check_type"] == "logic"
        for issue in logic_service.list_logic_check(session, scene.id, "text")["issues"]
    )

    # 逻辑自检重跑也只取代逻辑问题；审校的规则问题保持 open。
    audit_issue_ids = [issue["id"] for issue in audit["issues"]]
    logic_service.run_logic_check(session, scene.id, "text")
    for issue_id in audit_issue_ids:
        assert session.get(AuditIssue, issue_id).status == "open"


def test_missing_scene(session):
    with pytest.raises(ValueError, match="场景不存在"):
        logic_service.run_logic_check(session, "nope", "text")
