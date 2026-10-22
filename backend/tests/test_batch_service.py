import pytest

from app.db.models import (
    Agent,
    BatchJob,
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SceneDraft,
    Volume,
)
from app.runtime.execute import RunResult
from app.services import batch_service, text_service


def _seed(session):
    project = Project(name="批量项目")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    first = Scene(chapter_id=chapter.id, seq=0, goal="第一场")
    written = Scene(chapter_id=chapter.id, seq=1, goal="已有正文", body="旧正文")
    drafted = Scene(chapter_id=chapter.id, seq=2, goal="已有草稿")
    session.add_all([first, written, drafted])
    session.commit()
    session.add(SceneDraft(scene_id=drafted.id, content="草稿"))
    session.add(Agent(name="执笔", task_type="write", enabled=True))
    session.commit()
    return project, volume, chapter, first, written, drafted


def _result(content="新生成的正文。", *, status="ok", error=None):
    return RunResult(
        rendered_prompt="",
        raw_output=content,
        parsed=None,
        structured=False,
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
        # 批量服务必须把槽位字典传下去，而不是 scene_extra 返回的整个元组。
        assert isinstance(extra, dict)
        return run, result

    monkeypatch.setattr(batch_service.RuntimeService, "execute", fake_execute)
    return run


def _run(job_id):
    return batch_service.start_job(job_id)


def test_create_chapter_job_filters_written_and_drafted(session):
    project, _volume, chapter, first, _written, _drafted = _seed(session)

    job = batch_service.create_job(session, project.id, "chapter", chapter.id)

    assert job.status == "paused"
    assert job.scene_ids_json == [first.id]
    assert job.cursor == 0
    assert batch_service.serialize_job(job)["total"] == 1


def test_create_volume_job_keeps_order(session):
    project, volume, _chapter, first, _written, _drafted = _seed(session)
    extra_chapter = Chapter(volume_id=volume.id, seq=1, title="第二章")
    session.add(extra_chapter)
    session.commit()
    late = Scene(chapter_id=extra_chapter.id, seq=0, goal="第二章场景")
    session.add(late)
    session.commit()

    job = batch_service.create_job(session, project.id, "volume", volume.id)

    assert job.scene_ids_json == [first.id, late.id]


def test_create_without_available_scenes(session):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    first.body = "也已经写了"
    session.commit()

    with pytest.raises(ValueError, match="没有需要生成的场景"):
        batch_service.create_job(session, project.id, "chapter", chapter.id)


def test_create_rejects_foreign_scope_and_unknown_type(session):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    other = Project(name="另一个")
    session.add(other)
    session.commit()
    foreign_volume = Volume(project_id=other.id, seq=0, name="别的卷")
    session.add(foreign_volume)
    session.commit()

    with pytest.raises(ValueError, match="不属于这个项目"):
        batch_service.create_job(session, project.id, "volume", foreign_volume.id)
    with pytest.raises(ValueError, match="未知的批量范围"):
        batch_service.create_job(session, project.id, "book", chapter.id)


def test_create_rejects_when_another_job_is_running(session):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    session.add(
        BatchJob(
            project_id=project.id,
            scope_type="chapter",
            scope_id=chapter.id,
            scene_ids_json=[],
            status="running",
        )
    )
    session.commit()

    with pytest.raises(ValueError, match="进行中的批量任务"):
        batch_service.create_job(session, project.id, "chapter", chapter.id)


def test_advance_generates_a_draft_and_finishes(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "running"
    session.commit()
    run = _patch_execute(monkeypatch, session, project, _result())

    assert batch_service.advance_job(session, job.id) == "ok"
    session.refresh(job)
    assert job.cursor == 1
    draft = session.query(SceneDraft).filter_by(scene_id=first.id).one()
    assert draft.content == "新生成的正文。"
    assert draft.run_id == run.id

    assert batch_service.advance_job(session, job.id) == "completed"
    assert job.status == "completed"


def test_advance_records_model_failure(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "running"
    session.commit()
    _patch_execute(
        monkeypatch,
        session,
        project,
        _result("", status="error", error={"kind": "network", "message": "连接失败"}),
    )

    assert batch_service.advance_job(session, job.id) == "failed"
    session.refresh(job)
    assert job.cursor == 1
    assert job.failures_json[0]["scene_id"] == first.id
    assert "连接失败" in job.failures_json[0]["message"]


def test_advance_stops_job_when_runtime_is_unusable(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "running"
    session.commit()

    def fake_execute(self, project_id, agent_id, extra=None, allow_missing=None):
        raise ValueError("没有可用的服务商")

    monkeypatch.setattr(batch_service.RuntimeService, "execute", fake_execute)

    assert batch_service.advance_job(session, job.id) == "failed_job"
    session.refresh(job)
    assert job.status == "failed"
    assert job.cursor == 0
    assert "没有可用的服务商" in job.failures_json[0]["message"]


def test_advance_skips_a_scene_written_after_job_creation(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "running"
    first.body = "作者刚写的"
    session.commit()

    assert batch_service.advance_job(session, job.id) == "skipped"
    session.refresh(job)
    assert job.cursor == 1


def test_pause_resume_cancel_state_machine(session, monkeypatch):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    spawned: list[str] = []
    monkeypatch.setattr(batch_service, "_spawn", spawned.append)

    assert batch_service.start_job(job.id)["status"] == "running"
    assert spawned == [job.id]

    assert batch_service.pause_job(job.id)["status"] == "paused"
    assert batch_service.resume_job(job.id)["status"] == "running"
    assert batch_service.cancel_job(job.id)["status"] == "cancelled"

    with pytest.raises(ValueError, match="任务已结束"):
        batch_service.resume_job(job.id)


def test_retry_failed_only_reruns_failed_scenes(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "failed"
    job.cursor = 1
    job.failures_json = [{"scene_id": first.id, "message": "超时"}]
    session.commit()
    spawned: list[str] = []
    monkeypatch.setattr(batch_service, "_spawn", spawned.append)

    result = batch_service.retry_failed(job.id)

    assert result["status"] == "running"
    assert result["total"] == 1
    assert result["cursor"] == 0
    assert result["failures"] == []
    assert spawned == [job.id]


def test_retry_failed_keeps_unprocessed_scenes(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    extra = Scene(chapter_id=chapter.id, seq=3, goal="还没跑到的场景")
    session.add(extra)
    session.commit()
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    assert job.scene_ids_json == [first.id, extra.id]
    job.status = "failed"
    job.cursor = 0
    job.failures_json = [{"scene_id": first.id, "message": "没有服务商"}]
    session.commit()
    spawned: list[str] = []
    monkeypatch.setattr(batch_service, "_spawn", spawned.append)

    result = batch_service.retry_failed(job.id)

    assert result["total"] == 2
    assert result["cursor"] == 0
    assert spawned == [job.id]


def test_resume_rejects_another_running_job(session, monkeypatch):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    first_job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    first_job.status = "paused"
    session.commit()
    second_job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    second_job.status = "running"
    session.commit()
    monkeypatch.setattr(batch_service, "_spawn", lambda _job_id: None)

    with pytest.raises(ValueError, match="进行中的批量任务"):
        batch_service.resume_job(first_job.id)


def test_resume_at_the_end_marks_completed(session, monkeypatch):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "paused"
    job.cursor = len(job.scene_ids_json)
    session.commit()
    spawned: list[str] = []
    monkeypatch.setattr(batch_service, "_spawn", spawned.append)

    result = batch_service.resume_job(job.id)

    assert result["status"] == "completed"
    assert spawned == []


def test_retry_failed_requires_failures(session):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)

    with pytest.raises(ValueError, match="没有失败场景"):
        batch_service.retry_failed(job.id)


def test_recover_jobs_pauses_running_jobs(session):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    running = BatchJob(
        project_id=project.id,
        scope_type="chapter",
        scope_id=chapter.id,
        scene_ids_json=[],
        status="running",
    )
    paused = BatchJob(
        project_id=project.id,
        scope_type="chapter",
        scope_id=chapter.id,
        scene_ids_json=[],
        status="paused",
    )
    session.add_all([running, paused])
    session.commit()

    assert batch_service.recover_jobs() >= 1
    session.refresh(running)
    assert running.status == "paused"


def test_latest_job_returns_the_newest(session):
    project, _volume, chapter, _first, _written, _drafted = _seed(session)
    first_job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    first_job.status = "completed"
    session.commit()
    second_job = batch_service.create_job(session, project.id, "chapter", chapter.id)

    latest = batch_service.latest_job(session, project.id)

    assert latest["id"] == second_job.id
    assert batch_service.latest_job(session, "nope") is None


def test_save_generated_draft_refuses_to_overwrite(session):
    project, _volume, chapter, first, written, drafted = _seed(session)

    assert text_service.save_generated_draft(session, first.id, "草稿") is True
    assert text_service.save_generated_draft(session, first.id, "覆盖") is False
    assert text_service.save_generated_draft(session, written.id, "覆盖") is False
    assert text_service.save_generated_draft(session, drafted.id, "覆盖") is False
    assert session.query(SceneDraft).filter_by(scene_id=first.id).one().content == "草稿"


# ---- 锁定（P4a）----

def test_create_job_excludes_locked_scenes(session):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    first.locked = True
    session.commit()

    with pytest.raises(ValueError, match="没有需要生成的场景"):
        batch_service.create_job(session, project.id, "chapter", chapter.id)


def test_create_job_reports_the_locked_count(session):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    second = Scene(chapter_id=chapter.id, seq=3, goal="第二场")
    session.add(second)
    session.commit()
    second.locked = True
    session.commit()

    job = batch_service.create_job(session, project.id, "chapter", chapter.id)

    assert job.scene_ids_json == [first.id]
    assert batch_service.skipped_locked(session, job) == 1


def test_a_scene_locked_mid_run_is_skipped(session):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "running"
    session.commit()
    first.locked = True
    session.commit()

    assert batch_service.advance_job(session, job.id) == "skipped"

    session.expire_all()
    assert session.get(Scene, first.id).body is None
    assert session.get(BatchJob, job.id).cursor == 1


def test_an_unlocked_scene_still_generates(session, monkeypatch):
    project, _volume, chapter, first, _written, _drafted = _seed(session)
    _patch_execute(monkeypatch, session, project, _result())
    job = batch_service.create_job(session, project.id, "chapter", chapter.id)
    job.status = "running"
    session.commit()

    assert batch_service.advance_job(session, job.id) == "ok"
