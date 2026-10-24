"""因果链图的后端投影：断点判定、只收未处理因果问题、逻辑自检是否跑过、锁定继承。

投影只读：全部从场景树与 `audit_issue` 派生，不新增任何数据。
"""

import pytest

from app.db.models import AuditIssue, Chapter, Project, Scene, Volume
from app.services import causal_service


def _project_with_chapters(session, titles=("雨夜",)):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapters = []
    for seq, title in enumerate(titles):
        chapter = Chapter(volume_id=volume.id, seq=seq, title=title)
        session.add(chapter)
        session.commit()
        chapters.append(chapter)
    return project, volume, chapters


def _scene(session, chapter, seq, *, goal="目标", turn="转折", locked=False):
    scene = Scene(
        chapter_id=chapter.id, seq=seq, goal=goal, turn=turn, locked=locked
    )
    session.add(scene)
    session.commit()
    return scene


def _issue(session, project, scene, **overrides):
    values = {
        "project_id": project.id,
        "scene_id": scene.id,
        "source": "llm",
        "kind": "other",
        "severity": "major",
        "fingerprint": f"fp-{scene.id}-{len(overrides)}",
        "check_type": "logic",
        "stage": "plan",
        "layer": "causality",
        "status": "open",
        "explanation": "转折没有前置因",
    }
    values.update(overrides)
    issue = AuditIssue(**values)
    session.add(issue)
    session.commit()
    return issue


def test_breaks_are_projected_and_counted(session):
    project, _volume, (chapter,) = _project_with_chapters(session)
    _scene(session, chapter, 0, goal="把信交给掌柜", turn="")
    _scene(session, chapter, 1, goal="追问掌柜", turn="掌柜说了实话")
    third = _scene(session, chapter, 2, goal="收尾", turn="信是假的")
    issue = _issue(session, project, third)

    data = causal_service.build_map(session, project.id)

    assert data["chapters"][0]["label"] == "第1章 雨夜"
    assert data["chapters"][0]["volume_label"] == "第一卷"
    scenes = data["chapters"][0]["scenes"]
    assert [scene["label"] for scene in scenes] == ["场景1", "场景2", "场景3"]
    assert [scene["seq"] for scene in scenes] == [0, 1, 2]
    assert [scene["breaks"] for scene in scenes] == [
        ["missing_turn"],
        [],
        ["causality_issue"],
    ]
    assert scenes[2]["issues"] == [
        {
            "id": issue.id,
            "layer": "causality",
            "layer_label": "因果链",
            "severity": "major",
            "title": "转折没有前置因",
        }
    ]
    assert data["totals"] == {"scenes": 3, "breaks": 2, "chapters": 1}
    assert data["logic_checked"] is True


def test_a_scene_missing_both_goal_and_turn_counts_two_breaks_not_three(session):
    """三项全空也只按「缺目标 + 缺转折 + 因果问题」各记一条，不重复计数。"""
    project, _volume, (chapter,) = _project_with_chapters(session)
    scene = _scene(session, chapter, 0, goal="  ", turn="")
    _issue(session, project, scene)

    data = causal_service.build_map(session, project.id)

    assert data["chapters"][0]["scenes"][0]["breaks"] == [
        "missing_goal",
        "missing_turn",
        "causality_issue",
    ]
    assert data["totals"]["breaks"] == 3


def test_only_open_causality_issues_are_collected(session):
    project, _volume, (chapter,) = _project_with_chapters(session)
    scene = _scene(session, chapter, 0, goal="目标", turn="转折")
    kept = _issue(session, project, scene)
    _issue(session, project, scene, status="resolved")
    _issue(session, project, scene, status="superseded")
    _issue(session, project, scene, status="exception")
    _issue(session, project, scene, layer="motivation")
    _issue(session, project, scene, stage="text")
    _issue(session, project, scene, check_type="consistency", stage="text", layer=None)

    data = causal_service.build_map(session, project.id)

    row = data["chapters"][0]["scenes"][0]
    assert [item["id"] for item in row["issues"]] == [kept.id]
    assert row["breaks"] == ["causality_issue"]
    assert data["totals"]["breaks"] == 1


def test_open_causality_issues_are_sorted_by_severity(session):
    project, _volume, (chapter,) = _project_with_chapters(session)
    scene = _scene(session, chapter, 0, goal="目标", turn="转折")
    minor = _issue(session, project, scene, severity="minor", explanation="小问题")
    critical = _issue(session, project, scene, severity="critical", explanation="大问题")

    data = causal_service.build_map(session, project.id)

    assert [item["id"] for item in data["chapters"][0]["scenes"][0]["issues"]] == [
        critical.id,
        minor.id,
    ]


def test_logic_checked_is_false_when_only_consistency_issues_exist(session):
    project, _volume, (chapter,) = _project_with_chapters(session)
    scene = _scene(session, chapter, 0)
    _issue(session, project, scene, check_type="consistency", stage="text", layer=None)

    data = causal_service.build_map(session, project.id)

    assert data["logic_checked"] is False
    assert data["chapters"][0]["scenes"][0]["issues"] == []


def test_logic_checked_stays_true_after_every_issue_is_handled(session):
    """跑过就是跑过：问题都处理完了也不该退回「未检查」。"""
    project, _volume, (chapter,) = _project_with_chapters(session)
    scene = _scene(session, chapter, 0)
    _issue(session, project, scene, status="resolved")

    data = causal_service.build_map(session, project.id)

    assert data["logic_checked"] is True
    assert data["chapters"][0]["scenes"][0]["issues"] == []


def test_scene_lock_inherits_from_chapter_then_volume(session):
    project, volume, (first, second) = _project_with_chapters(
        session, titles=("雨夜", "天亮")
    )
    _scene(session, first, 0, locked=True)
    _scene(session, first, 1)
    _scene(session, second, 0)
    _scene(session, second, 1)

    data = causal_service.build_map(session, project.id)
    assert [[s["locked"] for s in ch["scenes"]] for ch in data["chapters"]] == [
        [True, False],
        [False, False],
    ]

    first.locked = True
    session.commit()
    data = causal_service.build_map(session, project.id)
    assert [[s["locked"] for s in ch["scenes"]] for ch in data["chapters"]] == [
        [True, True],
        [False, False],
    ]

    volume.locked = True
    session.commit()
    data = causal_service.build_map(session, project.id)
    assert [[s["locked"] for s in ch["scenes"]] for ch in data["chapters"]] == [
        [True, True],
        [True, True],
    ]


def test_another_projects_issues_do_not_leak(session):
    project, _volume, (chapter,) = _project_with_chapters(session)
    _scene(session, chapter, 0)
    other_project, _other_volume, (other_chapter,) = _project_with_chapters(session)
    _issue(session, other_project, _scene(session, other_chapter, 0))

    data = causal_service.build_map(session, project.id)

    assert data["logic_checked"] is False
    assert data["chapters"][0]["scenes"][0]["breaks"] == []


def test_a_project_without_chapters_has_an_empty_map(session):
    project = Project(name="空项目")
    session.add(project)
    session.commit()

    assert causal_service.build_map(session, project.id) == {
        "chapters": [],
        "totals": {"scenes": 0, "breaks": 0, "chapters": 0},
        "logic_checked": False,
    }


def test_unknown_project_raises(session):
    with pytest.raises(ValueError, match="项目不存在"):
        causal_service.build_map(session, "nope")


def test_api_reports_an_unknown_project_as_404(client):
    response = client.get("/api/projects/nope/causal-map")

    assert response.status_code == 404
    assert "项目不存在" in response.json()["detail"]


def test_api_returns_empty_chapters_for_a_new_project(client):
    project = client.post("/api/projects", json={"name": "空项目"}).json()

    body = client.get(f"/api/projects/{project['id']}/causal-map").json()

    assert body == {
        "chapters": [],
        "totals": {"scenes": 0, "breaks": 0, "chapters": 0},
        "logic_checked": False,
    }
