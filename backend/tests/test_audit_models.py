from app.db.models import (
    AuditIssue,
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SettingEntry,
    Volume,
)
from app.db.session import SessionLocal


def _scene(session) -> tuple[Project, Scene]:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="找到录音带")
    session.add(scene)
    session.commit()
    return project, scene


def _issue(session, project, scene, **overrides) -> AuditIssue:
    values = {
        "project_id": project.id,
        "scene_id": scene.id,
        "source": "rule",
        "kind": "repetition",
        "severity": "major",
        "quote": "他把门推开。",
        "rule_ref": "repetition.sentence",
        "explanation": "同一句在相邻段落重复。",
        "reader_impact": "读者会觉得卡住。",
        "options_json": ["删掉后一句", "改写前一句"],
        "fingerprint": "scene:1:repetition:abc",
    }
    values.update(overrides)
    issue = AuditIssue(**values)
    session.add(issue)
    session.commit()
    return issue


def test_audit_issue_roundtrip_keeps_fields_and_defaults(session):
    project, scene = _scene(session)
    issue = _issue(session, project, scene)

    with SessionLocal() as fresh:
        stored = fresh.get(AuditIssue, issue.id)
        assert stored is not None
        assert stored.project_id == project.id
        assert stored.scene_id == scene.id
        assert stored.source == "rule"
        assert stored.kind == "repetition"
        assert stored.severity == "major"
        assert stored.quote == "他把门推开。"
        assert stored.rule_ref == "repetition.sentence"
        assert stored.explanation == "同一句在相邻段落重复。"
        assert stored.reader_impact == "读者会觉得卡住。"
        assert stored.options_json == ["删掉后一句", "改写前一句"]
        assert stored.fingerprint == "scene:1:repetition:abc"
        assert stored.status == "open"
        assert stored.resolution is None
        assert stored.target_entry_id is None
        assert stored.run_id is None
        assert stored.created_at is not None
        assert stored.updated_at is not None


def test_options_json_defaults_to_empty_list(session):
    project, scene = _scene(session)
    issue = _issue(session, project, scene, options_json=[])

    with SessionLocal() as fresh:
        assert fresh.get(AuditIssue, issue.id).options_json == []

    bare = AuditIssue(
        project_id=project.id,
        scene_id=scene.id,
        source="llm",
        kind="other",
        severity="minor",
        fingerprint="fp-bare",
    )
    session.add(bare)
    session.commit()
    with SessionLocal() as fresh:
        assert fresh.get(AuditIssue, bare.id).options_json == []


def test_deleting_scene_cascades_to_issues(session):
    project, scene = _scene(session)
    issue = _issue(session, project, scene)

    session.delete(scene)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.get(AuditIssue, issue.id) is None


def test_deleting_target_entry_keeps_issue_and_nulls_target(session):
    project, scene = _scene(session)
    entry = SettingEntry(project_id=project.id, type="character", name="陈默")
    session.add(entry)
    session.commit()
    issue = _issue(session, project, scene, target_entry_id=entry.id)
    issue_id = issue.id

    session.delete(entry)
    session.commit()

    with SessionLocal() as fresh:
        stored = fresh.get(AuditIssue, issue_id)
        assert stored is not None
        assert stored.target_entry_id is None


def test_deleting_run_keeps_issue_and_nulls_run_id(session):
    project, scene = _scene(session)
    run = GenerationRun(project_id=project.id, model="test-model")
    session.add(run)
    session.commit()
    issue = _issue(session, project, scene, run_id=run.id, source="llm")
    issue_id = issue.id

    session.delete(run)
    session.commit()

    with SessionLocal() as fresh:
        stored = fresh.get(AuditIssue, issue_id)
        assert stored is not None
        assert stored.run_id is None


def test_audit_issue_indexes_cover_scene_status_and_fingerprint():
    indexes = {index.name: index for index in AuditIssue.__table__.indexes}

    assert "ix_audit_issue_scene_status" in indexes
    assert [column.name for column in indexes["ix_audit_issue_scene_status"].columns] == [
        "scene_id",
        "status",
    ]
    assert "ix_audit_issue_fingerprint" in indexes
    assert [column.name for column in indexes["ix_audit_issue_fingerprint"].columns] == [
        "fingerprint"
    ]
