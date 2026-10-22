"""伏笔生命周期：状态词表、派生规则与回收率。"""

import pytest

from app.db.models import Chapter, Foreshadow, Project, Scene, Volume
from app.foreshadow_types import effective_status, is_legacy, normalize_status
from app.services import export_service, foreshadow_service


def _row(**fields) -> Foreshadow:
    return Foreshadow(project_id="p", name="录音带", **fields)


def test_normalize_accepts_keys_and_labels():
    assert normalize_status("planted") == "planted"
    assert normalize_status("已收") == "paid"
    assert normalize_status("") == "planned"
    assert normalize_status(None) == "planned"


def test_normalize_rejects_unknown_values():
    with pytest.raises(ValueError, match="未知的伏笔状态"):
        normalize_status("finished")


def test_legacy_confirmed_is_normalized_but_flagged():
    assert normalize_status("confirmed") == "planned"
    assert is_legacy("confirmed") is True
    assert is_legacy("planned") is False


def test_planned_with_an_actual_pay_becomes_paid():
    assert effective_status(_row(status="planned", actual_pay_scene_id="s2")) == "paid"


def test_planned_with_a_plant_becomes_planted():
    assert effective_status(_row(status="planned", plant_scene_id="s1")) == "planted"


def test_planned_with_no_positions_stays_planned():
    assert effective_status(_row(status="planned")) == "planned"


def test_paid_wins_over_planted_when_both_positions_exist():
    row = _row(status="planned", plant_scene_id="s1", actual_pay_scene_id="s2")

    assert effective_status(row) == "paid"


def test_an_actual_pay_upgrades_an_explicit_planted():
    """回写助手经作者确认记下了实际回收，状态列还显示「已埋」会与同一行的
    「实际回收位置」互相打架 —— 事实赢。"""
    row = _row(status="planted", actual_pay_scene_id="s2")

    assert effective_status(row) == "paid"


def test_dropped_is_the_only_judgment_that_beats_the_facts():
    row = _row(status="dropped", plant_scene_id="s1", actual_pay_scene_id="s2")

    assert effective_status(row) == "dropped"


def test_explicit_paid_and_planted_survive_without_positions():
    assert effective_status(_row(status="paid")) == "paid"
    assert effective_status(_row(status="planted")) == "planted"


def test_is_unrecovered_is_the_shared_definition():
    """账本、成品报告、影响面三处共用这一个口径，避免同一个词各自漂移。"""
    assert foreshadow_service.is_unrecovered(_row(status="planned", plant_scene_id="s1"))
    assert foreshadow_service.is_unrecovered(_row(status="planned", plan_pay_scene_id="s2"))
    # 已收、已弃都不算未回收
    assert not foreshadow_service.is_unrecovered(
        _row(status="planned", actual_pay_scene_id="s2")
    )
    assert not foreshadow_service.is_unrecovered(_row(status="dropped", plant_scene_id="s1"))
    # 还没安排过的也没什么可收
    assert not foreshadow_service.is_unrecovered(_row(status="planned"))


def test_a_dropped_foreshadow_leaves_the_report_and_the_impact(session):
    """作者放弃的伏笔不该在成品报告里继续报「未回收」。"""
    project, scene = _seed(session)
    session.add_all(
        [
            Foreshadow(project_id=project.id, name="还在收", plant_scene_id=scene.id),
            Foreshadow(
                project_id=project.id,
                name="不收了",
                status="dropped",
                plant_scene_id=scene.id,
            ),
        ]
    )
    session.commit()

    report = export_service.build_report(session, project.id)

    assert [row["name"] for row in report["unrecovered_foreshadows"]] == ["还在收"]


def _seed(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="开场")
    session.add(scene)
    session.commit()
    return project, scene


def test_ledger_counts_and_rate(session):
    project, scene = _seed(session)
    session.add_all(
        [
            Foreshadow(project_id=project.id, name="已收", actual_pay_scene_id=scene.id),
            Foreshadow(project_id=project.id, name="已埋", plant_scene_id=scene.id),
            Foreshadow(project_id=project.id, name="规划中"),
            Foreshadow(project_id=project.id, name="放弃", status="dropped"),
        ]
    )
    session.commit()

    summary = foreshadow_service.ledger_summary(session, project.id)

    assert summary["total"] == 4
    assert summary["paid"] == 1
    assert summary["planted"] == 1
    assert summary["planned"] == 1
    assert summary["dropped"] == 1
    # dropped 不进分母：1 / (1 + 1 + 1) = 0.333
    assert summary["rate"] == 0.333


def test_dropped_does_not_drag_the_rate_down(session):
    project, scene = _seed(session)
    session.add(Foreshadow(project_id=project.id, name="已收", actual_pay_scene_id=scene.id))
    session.add_all(
        [
            Foreshadow(project_id=project.id, name=f"放弃{i}", status="dropped")
            for i in range(5)
        ]
    )
    session.commit()

    assert foreshadow_service.ledger_summary(session, project.id)["rate"] == 1.0


def test_an_empty_ledger_has_a_zero_rate(session):
    project, _scene = _seed(session)

    summary = foreshadow_service.ledger_summary(session, project.id)

    assert summary["total"] == 0
    assert summary["rate"] == 0.0


def test_status_can_be_set_through_the_service(session):
    project, _scene = _seed(session)
    row = foreshadow_service.create_foreshadow(
        session, project.id, name="录音带", status="planted"
    )

    updated = foreshadow_service.update_foreshadow(session, row.id, status="dropped")

    assert updated.status == "dropped"
