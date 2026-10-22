"""影响面分析：五种目标的下游分组、锁定计数与只读性。"""

import pytest

from app.db.models import (
    Act,
    Architecture,
    AuditIssue,
    Chapter,
    EntryRelation,
    Foreshadow,
    Project,
    Scene,
    SettingEntry,
    Volume,
)
from app.services import impact_service


def _seed(session):
    project = Project(name="雾港")
    session.add(project)
    session.commit()

    arch = Architecture(project_id=project.id, logline="旧故事")
    session.add(arch)
    session.commit()
    session.add_all(
        [
            Act(architecture_id=arch.id, seq=1, name="建置"),
            Act(architecture_id=arch.id, seq=2, name="对抗"),
        ]
    )
    volume = Volume(project_id=project.id, seq=0, name="第一卷", act_seq=1)
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()

    shen = SettingEntry(project_id=project.id, type="character", name="沈砚")
    city = SettingEntry(project_id=project.id, type="place", name="南滨旧城")
    session.add_all([shen, city])
    session.commit()

    first = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="开场",
        characters_json=[shen.id],
        location_id=city.id,
    )
    second = Scene(chapter_id=chapter.id, seq=1, goal="转折", body="沈砚走进雨里。")
    session.add_all([first, second])
    session.commit()

    foreshadow = Foreshadow(
        project_id=project.id, name="失忆的录音带", plant_scene_id=first.id
    )
    session.add(foreshadow)
    issue = AuditIssue(
        project_id=project.id,
        scene_id=first.id,
        source="rule",
        kind="alias",
        severity="major",
        fingerprint="fp",
    )
    relation = EntryRelation(
        project_id=project.id, from_id=shen.id, to_id=city.id, kind="居住于"
    )
    session.add_all([issue, relation])
    session.commit()
    return project, arch, volume, chapter, first, second, shen, city


def test_architecture_impact_lists_the_whole_downstream(session):
    project, arch, _volume, _chapter, first, _second, _shen, _city = _seed(session)

    body = impact_service.analyze(session, project.id, "architecture", arch.id)

    groups = {group["key"]: group for group in body["groups"]}
    assert groups["acts"]["total"] == 2
    assert groups["volumes"]["total"] == 1
    assert groups["chapters"]["total"] == 1
    assert [item["id"] for item in groups["scenes"]["items"]] == [
        first.id,
        groups["scenes"]["items"][1]["id"],
    ]
    assert groups["unrecovered_foreshadows"]["total"] == 1
    assert body["target"]["type"] == "architecture"


def test_a_volume_whose_act_vanished_is_called_out(session):
    project, arch, volume, _chapter, _first, _second, _shen, _city = _seed(session)
    volume.act_seq = 9
    session.commit()

    body = impact_service.analyze(session, project.id, "architecture", arch.id)

    groups = {group["key"]: group for group in body["groups"]}
    assert [item["id"] for item in groups["orphan_volumes"]["items"]] == [volume.id]
    assert groups["volumes"]["total"] == 0


def test_entry_impact_counts_locked_scenes(session):
    project, _arch, _volume, _chapter, first, _second, shen, _city = _seed(session)
    first.locked = True
    session.commit()

    body = impact_service.analyze(session, project.id, "entry", shen.id)

    scenes = next(group for group in body["groups"] if group["key"] == "scenes")
    assert scenes["total"] == 1
    assert scenes["locked"] == 1
    assert scenes["items"][0]["locked_by"]


def test_entry_impact_finds_scenes_that_mention_it_in_the_body(session):
    project, _arch, _volume, _chapter, _first, _second, shen, _city = _seed(session)

    body = impact_service.analyze(session, project.id, "entry", shen.id)

    mentions = next(group for group in body["groups"] if group["key"] == "mentions")
    assert _second.id in [item["id"] for item in mentions["items"]]
    assert "全文检索" in mentions["note"]


def test_entry_impact_includes_relations_and_open_issues(session):
    project, _arch, _volume, _chapter, _first, _second, shen, _city = _seed(session)

    body = impact_service.analyze(session, project.id, "entry", shen.id)

    groups = {group["key"]: group for group in body["groups"]}
    assert groups["relations"]["total"] == 1
    assert "居住于" in groups["relations"]["items"][0]["label"]
    assert groups["issues"]["total"] == 1


def test_volume_impact_lists_its_chapters_scenes_and_foreshadows(session):
    project, _arch, volume, _chapter, _first, _second, _shen, _city = _seed(session)

    body = impact_service.analyze(session, project.id, "volume", volume.id)

    groups = {group["key"]: group for group in body["groups"]}
    assert groups["chapters"]["total"] == 1
    assert groups["scenes"]["total"] == 2
    assert groups["foreshadows"]["total"] == 1


def test_chapter_impact_uses_the_volume_lock(session):
    project, _arch, volume, chapter, _first, _second, _shen, _city = _seed(session)
    volume.locked = True
    session.commit()

    body = impact_service.analyze(session, project.id, "chapter", chapter.id)

    assert body["target"]["locked"] is True
    scenes = next(group for group in body["groups"] if group["key"] == "scenes")
    assert scenes["locked"] == 2


def test_scene_impact_lists_foreshadows_and_issues(session):
    project, _arch, _volume, _chapter, first, _second, _shen, _city = _seed(session)

    body = impact_service.analyze(session, project.id, "scene", first.id)

    groups = {group["key"]: group for group in body["groups"]}
    assert groups["foreshadows"]["total"] == 1
    assert groups["issues"]["total"] == 1


def test_analysis_does_not_change_any_rows(session):
    project, arch, _volume, _chapter, _first, _second, shen, _city = _seed(session)
    before = {
        table: session.query(table).count()
        for table in (Scene, Chapter, Volume, SettingEntry, Foreshadow, AuditIssue)
    }

    for kind, target_id in (
        ("architecture", arch.id),
        ("entry", shen.id),
        ("volume", _volume.id),
        ("chapter", _chapter.id),
        ("scene", _first.id),
    ):
        impact_service.analyze(session, project.id, kind, target_id)

    after = {
        table: session.query(table).count()
        for table in (Scene, Chapter, Volume, SettingEntry, Foreshadow, AuditIssue)
    }
    assert before == after


def test_unknown_target_type_is_rejected(session):
    project, _arch, _volume, _chapter, _first, _second, _shen, _city = _seed(session)

    with pytest.raises(ValueError, match="未知的锁定目标类型"):
        impact_service.analyze(session, project.id, "chapterr", "x")


def test_a_missing_target_is_reported(session):
    project, _arch, _volume, _chapter, _first, _second, _shen, _city = _seed(session)

    with pytest.raises(ValueError, match="场景不存在"):
        impact_service.analyze(session, project.id, "scene", "nope")


def test_an_entry_from_another_project_is_reported(session):
    project, _arch, _volume, _chapter, _first, _second, _shen, _city = _seed(session)
    other = Project(name="另一个项目")
    session.add(other)
    session.commit()
    foreign = SettingEntry(project_id=other.id, type="character", name="外人")
    session.add(foreign)
    session.commit()

    with pytest.raises(ValueError, match="设定条目不存在"):
        impact_service.analyze(session, project.id, "entry", foreign.id)


def test_totals_aggregate_every_group(session):
    project, arch, _volume, _chapter, _first, _second, _shen, _city = _seed(session)

    body = impact_service.analyze(session, project.id, "architecture", arch.id)

    assert body["totals"]["all"] == sum(group["total"] for group in body["groups"])
    assert body["totals"]["locked"] == sum(group["locked"] for group in body["groups"])


def test_drafts_and_revisions_are_not_counted_as_locked(session):
    """草稿与修订不是可锁目标，不该混进 totals.locked。"""
    project, _arch, _volume, _chapter, first, _second, _shen, _city = _seed(session)
    first.locked = True
    session.commit()

    body = impact_service.analyze(session, project.id, "scene", first.id)

    drafts = next(group for group in body["groups"] if group["key"] == "drafts")
    assert drafts["locked"] == 0
