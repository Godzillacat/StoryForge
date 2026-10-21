from types import SimpleNamespace

import pytest

from app.db.models import (
    Agent,
    AuditIssue,
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SceneDraft,
    SettingEntry,
    Volume,
)
from app.runtime.execute import RunResult
from app.services import audit_service, text_service

REPEATED = (
    "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
    "雨落在旧城的铁皮屋顶上，声音像有人在数硬币。"
)


def _seed_scene(session, body: str = REPEATED) -> tuple[Project, Scene]:
    project = Project(name="审计项目")
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


def _add_auditor(session) -> Agent:
    agent = Agent(name="审校", task_type="continuity", enabled=True)
    session.add(agent)
    session.commit()
    return agent


def _result(
    parsed=None,
    *,
    structured: bool = False,
    status: str = "ok",
    error: dict | None = None,
) -> RunResult:
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

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        return run, result

    monkeypatch.setattr(audit_service.RuntimeService, "execute", fake_execute)
    return run


def _patch_execute_error(monkeypatch, message: str):
    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise ValueError(message)

    monkeypatch.setattr(audit_service.RuntimeService, "execute", fake_execute)


def test_run_audit_requires_adopted_body(session):
    project, scene = _seed_scene(session, body="   ")
    with pytest.raises(ValueError, match="还没有已采纳正文"):
        audit_service.run_audit(session, scene.id)


def test_run_audit_missing_scene(session):
    with pytest.raises(ValueError, match="场景不存在"):
        audit_service.run_audit(session, "nope")


def test_rule_layer_runs_without_auditor(session):
    project, scene = _seed_scene(session)

    result = audit_service.run_audit(session, scene.id)

    assert result["llm_status"] == "skipped"
    assert result["run_id"] is None
    assert "找不到审校智能体" in result["warning"]
    assert [issue["kind"] for issue in result["issues"]] == ["repetition"]
    assert result["issues"][0]["source"] == "rule"
    assert result["issues"][0]["severity"] == "major"


def test_llm_issues_are_merged_and_persisted(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_auditor(session)
    entry = SettingEntry(project_id=project.id, type="rule", name="死者不能复活")
    session.add(entry)
    session.commit()

    parsed = {
        "issues": [
            {
                "kind": "设定",
                "severity": "严重",
                "quote": "死者开口说话。",
                "rule_ref": "死者不能复活",
                "explanation": "与硬规则冲突。",
                "reader_impact": "读者会怀疑规则失效。",
                "options": ["改故事", "改设定"],
            }
        ]
    }
    run = _patch_execute(monkeypatch, session, project, _result(parsed, structured=True))

    result = audit_service.run_audit(session, scene.id)

    assert result["llm_status"] == "ok"
    assert result["run_id"] == run.id
    llm = [issue for issue in result["issues"] if issue["source"] == "llm"]
    assert len(llm) == 1
    assert llm[0]["kind"] == "setting"
    assert llm[0]["kind_label"] == "设定"
    assert llm[0]["severity"] == "major"
    assert llm[0]["severity_label"] == "严重"
    assert llm[0]["target_entry_id"] == entry.id
    assert llm[0]["target_entry_name"] == "死者不能复活"

    row = session.get(AuditIssue, llm[0]["id"])
    assert row.run_id == run.id
    assert row.source == "llm"


def test_llm_normalization_and_target_mapping(session, monkeypatch):
    project, scene = _seed_scene(session, body="档案室的门在自己身后合上。")
    _add_auditor(session)
    first = SettingEntry(project_id=project.id, type="character", name="陈默", aliases_json=["老师"])
    second = SettingEntry(project_id=project.id, type="character", name="沈砚", aliases_json=["老师"])
    session.add_all([first, second])
    session.commit()

    parsed = {
        "issues": [
            {
                "kind": "人物",
                "severity": "提示",
                "quote": "老师没有回头。",
                "rule_ref": "老师",
                "explanation": "称呼有歧义。",
            },
            {
                "kind": "说不清",
                "severity": "巨大",
                "quote": "门关上了。",
                "rule_ref": "",
                "explanation": "未知分类应兜底。",
                # 字符串不是数组：不能按字符拆成三条修正方向
                "options": "改故事",
            },
            {
                "kind": "设定",
                "severity": "致命",
                "quote": "",
                "rule_ref": "死者不能复活",
                "explanation": "没有原句的问题应丢弃。",
            },
        ]
    }
    _patch_execute(monkeypatch, session, project, _result(parsed, structured=True))

    result = audit_service.run_audit(session, scene.id)

    issues = result["issues"]
    assert len(issues) == 2
    assert issues[0]["kind"] == "character" and issues[0]["severity"] == "minor"
    assert issues[0]["target_entry_id"] is None  # 两个条目共用别名，不猜
    assert issues[1]["kind"] == "other" and issues[1]["severity"] == "minor"
    assert issues[1]["options"] == []


def test_llm_issue_cap_and_severity_order(session, monkeypatch):
    project, scene = _seed_scene(session, body="档案室的门在自己身后合上。")
    _add_auditor(session)

    raw = [
        {
            "kind": "设定",
            "severity": "提示",
            "quote": f"第{index}句正文，用来测试上限。",
            "rule_ref": "",
            "explanation": "测试。",
        }
        for index in range(35)
    ]
    raw.append(
        {
            "kind": "设定",
            "severity": "致命",
            "quote": "最严重的一句。",
            "rule_ref": "",
            "explanation": "测试排序。",
        }
    )
    _patch_execute(
        monkeypatch, session, project, _result({"issues": raw}, structured=True)
    )

    result = audit_service.run_audit(session, scene.id)

    assert len(result["issues"]) == 30
    assert result["issues"][0]["severity"] == "critical"


def test_llm_audit_allows_empty_context_slots(session, monkeypatch):
    """审校的时间线 / 出场人物 / 检索结果天然可能为空，不能因此拒绝出结果。"""
    project, scene = _seed_scene(session, body="档案室的门在自己身后合上。")
    _add_auditor(session)
    run = GenerationRun(project_id=project.id, status="ok")
    session.add(run)
    session.commit()
    seen: dict = {}

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        seen["allow_missing"] = allow_missing
        return run, _result({"issues": []}, structured=True)

    monkeypatch.setattr(audit_service.RuntimeService, "execute", fake_execute)

    result = audit_service.run_audit(session, scene.id)

    assert seen["allow_missing"] is True
    assert result["llm_status"] == "ok"


def test_llm_unexpected_error_falls_back_to_rules(session, monkeypatch):
    """密钥解密失败、服务商返回结构异常等非 ValueError 也不该打穿整次审校。"""
    project, scene = _seed_scene(session)
    _add_auditor(session)

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise RuntimeError("凭据无法解密")

    monkeypatch.setattr(audit_service.RuntimeService, "execute", fake_execute)

    result = audit_service.run_audit(session, scene.id)

    assert result["llm_status"] == "error"
    assert "凭据无法解密" in result["warning"]
    assert [issue["kind"] for issue in result["issues"]] == ["repetition"]


def test_duplicate_exception_fingerprints_count_once(session):
    from app.audit_rules import RuleIssue

    project, scene = _seed_scene(session)
    issue = RuleIssue(
        kind="repetition",
        severity="minor",
        quote="重复的句子",
        rule_ref="重复句",
        explanation="测试",
        reader_impact="测试",
        options=[],
        fingerprint="rule:repetition:abc",
    )

    inserted, suppressed = audit_service._insert_issues(
        session,
        project_id=project.id,
        scene_id=scene.id,
        issues=[issue, issue],
        source="rule",
        run_id=None,
        exceptions={"rule:repetition:abc"},
    )

    assert inserted == []
    assert suppressed == 1


def test_saving_body_supersedes_open_issues(session):
    project, scene = _seed_scene(session)
    result = audit_service.run_audit(session, scene.id)
    issue_id = result["issues"][0]["id"]

    text_service.save_body(session, scene.id, "换了一份全新的正文。")

    assert session.get(AuditIssue, issue_id).status == "superseded"
    assert audit_service.list_audit(session, scene.id)["issues"] == []


def test_adopting_draft_supersedes_open_issues(session):
    project, scene = _seed_scene(session)
    result = audit_service.run_audit(session, scene.id)
    issue_id = result["issues"][0]["id"]
    session.add(SceneDraft(scene_id=scene.id, content="采纳后的新正文，旧问题应失效。"))
    session.commit()

    text_service.adopt_draft(session, scene.id)

    assert session.get(AuditIssue, issue_id).status == "superseded"


def test_last_audited_at_is_scene_scoped(session):
    project, first = _seed_scene(session)
    second = Scene(chapter_id=first.chapter_id, seq=1, goal="第二场", body=REPEATED)
    session.add(second)
    session.commit()

    audit_service.run_audit(session, first.id)
    before = audit_service.list_audit(session, first.id)["last_audited_at"]
    audit_service.run_audit(session, second.id)
    after = audit_service.list_audit(session, first.id)["last_audited_at"]

    assert before is not None
    assert after == before


def test_llm_unstructured_falls_back_to_rules(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_auditor(session)
    _patch_execute(monkeypatch, session, project, _result(None, structured=False))

    result = audit_service.run_audit(session, scene.id)

    assert result["llm_status"] == "unstructured"
    assert "未返回结构化问题" in result["warning"]
    assert result["run_id"] is not None
    assert [issue["kind"] for issue in result["issues"]] == ["repetition"]


def test_llm_error_falls_back_to_rules(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_auditor(session)
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result(status="error", error={"kind": "network", "message": "连接失败"}),
    )

    result = audit_service.run_audit(session, scene.id)

    assert result["llm_status"] == "error"
    assert "连接失败" in result["warning"]
    assert [issue["kind"] for issue in result["issues"]] == ["repetition"]


def test_llm_skipped_when_model_unavailable(session, monkeypatch):
    project, scene = _seed_scene(session)
    _add_auditor(session)
    _patch_execute_error(monkeypatch, "没有可用的服务商，请先配置一家")

    result = audit_service.run_audit(session, scene.id)

    assert result["llm_status"] == "skipped"
    assert "没有可用的服务商" in result["warning"]
    assert [issue["kind"] for issue in result["issues"]] == ["repetition"]


def test_new_audit_supersedes_previous_open_issues(session):
    project, scene = _seed_scene(session)

    first = audit_service.run_audit(session, scene.id)
    first_id = first["issues"][0]["id"]
    second = audit_service.run_audit(session, scene.id)

    assert session.get(AuditIssue, first_id).status == "superseded"
    assert second["issues"][0]["id"] != first_id
    assert second["issues"][0]["status"] == "open"


def test_exception_suppresses_repeat_report(session):
    project, scene = _seed_scene(session)
    first = audit_service.run_audit(session, scene.id)

    audit_service.resolve_issue(session, first["issues"][0]["id"], "exception")
    second = audit_service.run_audit(session, scene.id)

    assert second["suppressed"] == 1
    assert second["issues"] == []


def test_resolve_issue_records_status_and_resolution(session):
    project, scene = _seed_scene(session)
    result = audit_service.run_audit(session, scene.id)
    issue_id = result["issues"][0]["id"]

    resolved = audit_service.resolve_issue(session, issue_id, "story")
    assert resolved["status"] == "resolved"
    assert resolved["resolution"] == "story"

    row = session.get(AuditIssue, issue_id)
    row.status = "open"
    row.resolution = None
    session.commit()
    by_setting = audit_service.resolve_issue(session, issue_id, "setting")
    assert by_setting["status"] == "resolved"
    assert by_setting["resolution"] == "setting"

    row.status = "open"
    row.resolution = None
    session.commit()
    by_character = audit_service.resolve_issue(session, issue_id, "character")
    assert by_character["status"] == "resolved"
    assert by_character["resolution"] == "character"


def test_resolve_issue_rejects_invalid_resolution(session):
    project, scene = _seed_scene(session)
    result = audit_service.run_audit(session, scene.id)

    with pytest.raises(ValueError, match="不支持的处理方式"):
        audit_service.resolve_issue(session, result["issues"][0]["id"], "ignore")


def test_resolve_issue_missing(session):
    with pytest.raises(ValueError, match="审计问题不存在"):
        audit_service.resolve_issue(session, "nope", "story")


def test_list_audit_returns_open_issues_and_last_time(session):
    project, scene = _seed_scene(session)

    empty = audit_service.list_audit(session, scene.id)
    assert empty == {"issues": [], "last_audited_at": None}

    result = audit_service.run_audit(session, scene.id)
    view = audit_service.list_audit(session, scene.id)

    assert [issue["id"] for issue in view["issues"]] == [result["issues"][0]["id"]]
    assert view["last_audited_at"]

    audit_service.resolve_issue(session, result["issues"][0]["id"], "exception")
    assert audit_service.list_audit(session, scene.id)["issues"] == []


def test_list_audit_missing_scene(session):
    with pytest.raises(ValueError, match="场景不存在"):
        audit_service.list_audit(session, "nope")
