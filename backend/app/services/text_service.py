"""正文、AI 草稿与修订快照。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.db.models import (
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SceneDraft,
    SceneRevision,
    Volume,
)
from app.db.session import SessionLocal
from app.runtime.context import SLOT_REGISTRY
from app.runtime.pricing import estimate_tokens
from app.services import (
    agent_service,
    change_service,
    chapter_service,
    lock_service,
    search_service,
)
from app.services.runtime_service import PreparedExecution, RuntimeService
from app.services.slot_source import scene_search_query
from app.text_stats import count_words

_PREVIEW_LIMIT = 80


@dataclass(frozen=True)
class GenerationSpec:
    project_id: str
    scene_id: str
    prepared: PreparedExecution
    # 纯值快照。流生成器在请求会话关闭后才创建运行记录，那时不能再读
    # prepared.agent / version / provider 这些 ORM 属性（属性一旦过期就会
    # DetachedInstanceError），所以落库需要的东西在准备阶段就地抄成平值。
    agent_id: str
    agent_name: str
    version_id: str
    provider_id: str
    model: str
    params: dict
    rendered_prompt: str
    trimmed: dict
    prompt_tokens: int
    prices: dict | None


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _project(session: Session, scene: Scene) -> Project:
    return chapter_service.get_project_for_chapter(session, scene.chapter_id)


def _reject_locked(session: Session, scene: Scene) -> None:
    """锁定只挡 AI 写路径；调用方都是 AI 入口（生成、采纳、批量）。

    必须在**创建运行记录之前**判定 —— 已经花掉的 token 追不回来，而一个
    被锁定拒绝的请求根本不该产生运行记录。
    """
    state = lock_service.effective_scene_lock(session, scene)
    if state["locked"]:
        raise ValueError(
            f"{state['label']}已锁定，AI 不会改动它。要生成请先解锁。"
        )


def _draft(session: Session, scene_id: str) -> SceneDraft | None:
    return session.scalars(
        select(SceneDraft).where(SceneDraft.scene_id == scene_id)
    ).first()


def _draft_out(draft: SceneDraft) -> dict:
    return {
        "id": draft.id,
        "content": draft.content,
        "run_id": draft.run_id,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else "",
    }


def _revision_summary(revision: SceneRevision) -> dict:
    text = revision.content or ""
    preview = text if len(text) <= _PREVIEW_LIMIT else text[:_PREVIEW_LIMIT] + "…"
    return {
        "id": revision.id,
        "source": revision.source,
        "run_id": revision.run_id,
        "note": revision.note,
        "chars": count_words(text),
        "created_at": revision.created_at.isoformat() if revision.created_at else "",
        "preview": preview,
    }


def _revision_detail(revision: SceneRevision) -> dict:
    return {
        "id": revision.id,
        "source": revision.source,
        "run_id": revision.run_id,
        "note": revision.note,
        "content": revision.content,
        "created_at": revision.created_at.isoformat() if revision.created_at else "",
    }


def _state(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    draft = _draft(session, scene_id)
    revisions = session.scalars(
        select(SceneRevision)
        .where(SceneRevision.scene_id == scene_id)
        .order_by(SceneRevision.created_at.desc(), SceneRevision.id.desc())
    ).all()
    return {
        "scene_id": scene.id,
        "body": scene.body,
        "has_body": bool((scene.body or "").strip()),
        "word_count": count_words(scene.body),
        "draft": None if draft is None else _draft_out(draft),
        "revisions": [_revision_summary(row) for row in revisions],
    }


def get_text(session: Session, scene_id: str) -> dict:
    _scene(session, scene_id)
    return _state(session, scene_id)


def save_body(session: Session, scene_id: str, content: str) -> dict:
    scene = _scene(session, scene_id)
    project = _project(session, scene)
    new_content = content or ""
    if (scene.body or "") != new_content:
        scene.body = new_content or None
        session.add(
            SceneRevision(scene_id=scene.id, content=new_content, source="author")
        )
        search_service.mark_dirty(session, project.id)
        _supersede_audit(session, scene.id)
        change_service.record(
            session,
            project.id,
            target_type="scene",
            target_id=scene.id,
            target_label=_scene_label(session, scene),
            action="update",
            source="author",
            summary=f"正文 {count_words(new_content)} 字",
        )
        session.commit()
    return _state(session, scene_id)


def _scene_label(session: Session, scene: Scene) -> str:
    chapter = session.get(Chapter, scene.chapter_id)
    volume = session.get(Volume, chapter.volume_id) if chapter else None
    if chapter is None or volume is None:
        return f"场景{scene.seq + 1}"
    return f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{scene.seq + 1}"


def save_draft(session: Session, scene_id: str, content: str) -> dict:
    _scene(session, scene_id)
    draft = _draft(session, scene_id)
    if draft is None:
        raise ValueError("草稿已被替换或删除，请刷新")
    draft.content = content or ""
    session.commit()
    return _draft_out(draft)


def save_generated_draft(
    session: Session, scene_id: str, content: str, run_id: str | None = None
) -> bool:
    """批量生成把结果落为草稿；已有正文或已有草稿时拒绝覆盖。

    返回是否真的写入 —— 调用方（批量任务）据此区分「生成成功」与「跳过」。
    """
    scene = _scene(session, scene_id)
    if (scene.body or "").strip():
        return False
    if _draft(session, scene_id) is not None:
        return False
    session.add(
        SceneDraft(scene_id=scene.id, content=content or "", run_id=run_id)
    )
    try:
        session.commit()
    except IntegrityError:
        # 两个 worker 同时写同一场时，唯一约束是最后一道防线；输的一方
        # 当作「已有草稿、跳过」，而不是让线程带着异常退出。
        session.rollback()
        return False
    return True


def discard_draft(session: Session, scene_id: str) -> None:
    _scene(session, scene_id)
    draft = _draft(session, scene_id)
    if draft is not None:
        session.delete(draft)
        session.commit()


def adopt_draft(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    _reject_locked(session, scene)
    draft = _draft(session, scene_id)
    if draft is None:
        raise ValueError("当前没有可采纳的草稿")
    content = draft.content or ""
    if not content.strip():
        raise ValueError("草稿为空，不能采纳")
    _reject_missing_paragraphs(scene, content)
    project = _project(session, scene)
    scene.body = content
    session.add(
        SceneRevision(
            scene_id=scene.id, content=content, source="ai", run_id=draft.run_id
        )
    )
    session.delete(draft)
    search_service.mark_dirty(session, project.id)
    _supersede_audit(session, scene.id)
    change_service.record(
        session,
        project.id,
        target_type="scene",
        target_id=scene.id,
        target_label=_scene_label(session, scene),
        action="adopt",
        source="ai",
        summary=f"采纳 AI 草稿 {count_words(content)} 字",
    )
    session.commit()
    return _state(session, scene_id)


def list_revisions(session: Session, scene_id: str) -> list[dict]:
    _scene(session, scene_id)
    rows = session.scalars(
        select(SceneRevision)
        .where(SceneRevision.scene_id == scene_id)
        .order_by(SceneRevision.created_at.desc(), SceneRevision.id.desc())
    ).all()
    return [_revision_summary(row) for row in rows]


def get_revision(session: Session, scene_id: str, revision_id: str) -> dict:
    _scene(session, scene_id)
    revision = session.get(SceneRevision, revision_id)
    if revision is None or revision.scene_id != scene_id:
        raise ValueError("修订不存在")
    return _revision_detail(revision)


def restore_revision(session: Session, scene_id: str, revision_id: str) -> dict:
    scene = _scene(session, scene_id)
    revision = session.get(SceneRevision, revision_id)
    if revision is None or revision.scene_id != scene_id:
        raise ValueError("修订不存在")
    project = _project(session, scene)
    content = revision.content or ""
    scene.body = content or None
    session.add(
        SceneRevision(
            scene_id=scene.id,
            content=content,
            source="restore",
            note=f"恢复自修订 {revision.id}",
        )
    )
    search_service.mark_dirty(session, project.id)
    _supersede_audit(session, scene.id)
    change_service.record(
        session,
        project.id,
        target_type="scene",
        target_id=scene.id,
        target_label=_scene_label(session, scene),
        action="restore",
        source="author",
        summary=f"恢复修订 {revision.id[:8]}（{count_words(content)} 字）",
    )
    session.commit()
    return _state(session, scene_id)


def _reject_missing_paragraphs(scene: Scene, content: str) -> None:
    """段落锁只在**采纳 AI 草稿**时强制：草稿是 AI 的产物，采纳是它进入稿件的
    唯一入口。生成时拒绝没有意义 —— 草稿本来就可以改。
    """
    locks = list(scene.locked_paragraphs_json or [])
    missing = lock_service.missing_locks(content, locks)
    if not missing:
        return
    listed = "；".join(f"「{text}」" for text in missing[:3])
    more = f" 等 {len(missing)} 段" if len(missing) > 3 else ""
    raise ValueError(
        f"草稿缺少已锁定的段落：{listed}{more}。锁定的段落 AI 不得改动，"
        "请先在草稿里把它们原样保留，或先解锁。"
    )


def _supersede_audit(session: Session, scene_id: str) -> None:
    """正文被整份替换后，旧审校问题不再对应当前文本。

    延迟导入避免 text_service ↔ audit_service 的模块级循环。
    """
    from app.services.audit_service import supersede_scene_issues

    supersede_scene_issues(session, scene_id)


def scene_extra(session: Session, scene: Scene) -> tuple[Project, dict]:
    chapter = session.get(Chapter, scene.chapter_id)
    if chapter is None:
        raise ValueError("场景的章节结构已损坏")
    volume = session.get(Volume, chapter.volume_id)
    if volume is None:
        raise ValueError("场景的章节结构已损坏")
    project = session.get(Project, volume.project_id)
    if project is None:
        raise ValueError("场景的章节结构已损坏")
    return project, {
        "scene_id": scene.id,
        "chapter_id": chapter.id,
        "volume_id": volume.id,
        "search_query": scene_search_query(session, project.id, scene),
    }


def context_preview(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    project, extra = scene_extra(session, scene)
    agent = agent_service.find_by_task_type(session, "write")
    if agent is None:
        raise ValueError("找不到执笔智能体，请检查智能体工作室")

    agent, version, prompt = RuntimeService(session).prepare_context(
        project.id, agent.id, extra
    )
    if prompt.error:
        raise ValueError(prompt.error["message"])

    slots: list[dict] = []
    for key in version.context_slots_json or []:
        spec = SLOT_REGISTRY.get(key)
        text = prompt.contents.get(key)
        slots.append(
            {
                "key": key,
                "label": spec.label if spec else key,
                "priority": spec.priority if spec else 0,
                "over_budget": spec.over_budget if spec else "drop",
                "text": text,
                "estimated_tokens": estimate_tokens(text) if text else 0,
            }
        )

    settings = config.load_settings()
    return {
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "version_no": version.version_no,
        },
        "token_budget": int(settings.get("context_token_budget", 8000)),
        "estimated_tokens": sum(slot["estimated_tokens"] for slot in slots),
        "over_budget": prompt.over_budget,
        "slots": slots,
        "trimmed": prompt.trimmed,
    }


def prepare_generation(session: Session, scene_id: str) -> GenerationSpec:
    scene = _scene(session, scene_id)
    _reject_locked(session, scene)
    project, extra = scene_extra(session, scene)
    agent = agent_service.find_by_task_type(session, "write")
    if agent is None:
        raise ValueError("找不到执笔智能体，请检查智能体工作室")
    prepared = RuntimeService(session).prepare(project.id, agent.id, extra)
    # 在会话仍然可用时把所有 ORM 属性读成平值 —— 见 GenerationSpec 的注释。
    return GenerationSpec(
        project_id=project.id,
        scene_id=scene.id,
        prepared=prepared,
        agent_id=prepared.agent.id,
        agent_name=prepared.agent.name,
        version_id=prepared.version.id,
        provider_id=prepared.provider.id,
        model=prepared.model,
        params=dict(prepared.params),
        rendered_prompt=prepared.prompt.rendered_prompt,
        trimmed=dict(prepared.prompt.trimmed),
        prompt_tokens=prepared.prompt.prompt_tokens,
        prices=prepared.prices,
    )


def create_run(spec: GenerationSpec) -> str:
    with SessionLocal() as session:
        run = GenerationRun(
            project_id=spec.project_id,
            agent_id=spec.agent_id,
            agent_version_id=spec.version_id,
            provider_id=spec.provider_id,
            model=spec.model,
            params_json=spec.params,
            rendered_prompt=spec.rendered_prompt,
            trimmed_json=spec.trimmed,
            status="running",
        )
        session.add(run)
        session.commit()
        return run.id


def finalize_run(
    run_id: str,
    scene_id: str,
    *,
    content: str,
    status: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_estimate: float,
    duration_ms: int,
    error: dict | None,
    usage_source: str = "estimated",
    branch_id: str | None = None,
) -> str | None:
    """幂等收尾：只有 running 的运行会更新；成功后覆盖草稿，失败只补空缺。

    `branch_id` 非空时结果写进**分支的草稿**，不碰主版 —— 分支与主版各有
    自己的一条草稿槽位，混写会让「采纳」与「合并」两个动作打架。
    """
    with SessionLocal() as session:
        run = session.get(GenerationRun, run_id)
        if run is None or run.status != "running":
            return None

        run.raw_output = content
        run.prompt_tokens = prompt_tokens
        run.completion_tokens = completion_tokens
        run.cost_estimate = cost_estimate
        run.usage_source = usage_source
        run.duration_ms = duration_ms
        run.status = status
        run.error_json = error

        draft_id: str | None = None
        if branch_id is not None:
            from app.db.models import SceneBranch

            branch = session.get(SceneBranch, branch_id)
            if branch is not None and content.strip():
                if status == "ok" or not (branch.draft_content or "").strip():
                    branch.draft_content = content
                    branch.draft_run_id = run_id
                    draft_id = branch.id
            session.commit()
            return draft_id

        if content.strip():
            draft = session.scalars(
                select(SceneDraft).where(SceneDraft.scene_id == scene_id)
            ).first()
            if status == "ok" or draft is None:
                if draft is None:
                    draft = SceneDraft(
                        scene_id=scene_id, run_id=run_id, content=content
                    )
                    session.add(draft)
                    session.flush()
                else:
                    draft.content = content
                    draft.run_id = run_id
                draft_id = draft.id
        session.commit()
        return draft_id
