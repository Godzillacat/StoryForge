"""场景正文分支：同一场戏的多种写法并行推进。

**只分支正文。** 场景卡（目标 / 冲突 / 转折 / 人物 / 地点）是共享的 ——
A、B 两案写的是同一场戏的不同写法，不是两场不同的戏。

锁定与段落锁的语义与主版**完全相同**：分支里的 AI 也是 AI。作者手工
保存一律不受限。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import literal_column, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BranchRevision, Scene, SceneBranch, SceneDraft, SceneRevision
from app.services import change_service, lock_service, search_service
from app.text_stats import count_words


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _branch(session: Session, branch_id: str) -> SceneBranch:
    row = session.get(SceneBranch, branch_id)
    if row is None:
        raise ValueError(f"分支不存在：{branch_id}")
    return row


def _clean_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("分支名称不能为空")
    return name


def _find_by_name(session: Session, scene_id: str, name: str) -> SceneBranch | None:
    return session.scalars(
        select(SceneBranch).where(
            SceneBranch.scene_id == scene_id, SceneBranch.name == name
        )
    ).first()


def _unique_name(session: Session, scene_id: str, base: str) -> str:
    """同场景重名时追加 ` 2`、` 3`…，而不是报错。

    **跨全部分支查名**（别的 A/B 组、作者手建的分支都算）：库级唯一索引
    `(scene_id, name)` 不允许重名，而保留前缀只负责让名字一眼可辨，并不
    提供唯一性 —— 所以这里不加 `ab_group` 过滤。
    """
    name = base
    suffix = 2
    while _find_by_name(session, scene_id, name) is not None:
        name = f"{base} {suffix}"
        suffix += 1
    return name


def _label(session: Session, scene: Scene) -> str:
    """与写作台一致的场景标签。延迟导入避免与 text_service 的循环。"""
    from app.services.text_service import _scene_label

    return _scene_label(session, scene)


def _depth_map(session: Session, scene_id: str) -> dict[str, int]:
    """全场景分支的深度表：根 = 1，子 = 父 + 1。

    **一次取全场景、在内存里沿父链算** —— 列表一次要几十条，逐条回库就是
    N+1；深度只取决于同一场景内的派生关系。

    **成环保护**：正常接口建不出环，但手工改库能。碰到环时把整条未定链
    一律当根（深度 1）—— 脏数据不该让列表接口转不出来，也不该让某条分支
    拿到无穷大或负数。指向别的场景 / 已删分支的父同样按根处理（父不在
    这张表里，链自然断掉）。
    """
    rows = session.execute(
        select(SceneBranch.id, SceneBranch.parent_branch_id).where(
            SceneBranch.scene_id == scene_id
        )
    ).all()
    parent_of = {branch_id: parent_id for branch_id, parent_id in rows}
    depths: dict[str, int] = {}

    def _resolve(start: str) -> int:
        if start in depths:
            return depths[start]
        chain = [start]
        seen = {start}
        node = parent_of.get(start)
        while node is not None and node not in depths and node not in seen:
            seen.add(node)
            chain.append(node)
            node = parent_of.get(node)
        if node is not None and node not in depths:
            # 成环：链上没有合法的根，整条链按根处理。
            for item in chain:
                depths[item] = 1
            return 1
        base = depths[node] if node is not None else 0
        for item in reversed(chain):
            base += 1
            depths[item] = base
        return depths[start]

    return {branch_id: _resolve(branch_id) for branch_id in parent_of}


def _parent_branch(
    session: Session, scene_id: str, parent_id: str | None
) -> SceneBranch | None:
    """派生起点。`None` 表示从主版起一条根分支。

    跨场景与不存在同一口径（都报「分支不存在」）：不告诉调用方「那个 id
    确实存在，只是不归你」。A/B 临时分支采纳或丢弃后即删，不能当父。
    """
    if parent_id is None or parent_id == "":
        return None
    parent = session.get(SceneBranch, parent_id)
    if parent is None or parent.scene_id != scene_id:
        raise ValueError(f"分支不存在：{parent_id}")
    if parent.ab_group is not None:
        raise ValueError("A/B 分支不能作为派生起点")
    if _depth_map(session, scene_id).get(parent.id, 1) >= 3:
        raise ValueError("最多三层分支")
    return parent


def create_branch(
    session: Session,
    scene_id: str,
    name: str,
    note: str = "",
    parent_id: str | None = None,
    commit: bool = True,
) -> SceneBranch:
    """开一条分支。`commit=False` 把提交时机交给调用方（A/B 要一次提交）。

    `parent_id` 给定时是**派生**：新分支复制父分支的正文作为起点，挂在父
    下面，树的深度最多三层。不给时仍从主版正文起步（原有行为）。
    """
    scene = _scene(session, scene_id)
    clean = _clean_name(name)
    parent = _parent_branch(session, scene_id, parent_id)
    if _find_by_name(session, scene_id, clean) is not None:
        raise ValueError(f"这个场景里已经有叫「{clean}」的分支了")
    if parent is not None:
        # 派生是「在这一版的基础上再试一版」，所以复制的是**父分支正文**，
        # 不是主版正文。父没有正文时从空开始，与主版为空的既有行为一致。
        content = parent.content or ""
        note_text = (note or "").strip() or f"派生自 {parent.name}"
    else:
        # 从主版正文起步：作者的典型路径是「主版写得差不多了，想试另一版」。
        content = scene.body or ""
        note_text = (note or "").strip()
    row = SceneBranch(
        scene_id=scene_id,
        name=clean,
        content=content,
        note=note_text,
        parent_branch_id=parent.id if parent is not None else None,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError(f"这个场景里已经有叫「{clean}」的分支了") from exc
    change_service.record(
        session,
        _project_id(session, scene),
        target_type="scene",
        target_id=scene_id,
        target_label=_label(session, scene),
        action="create",
        source="author",
        summary=f"开分支「{clean}」",
    )
    if commit:
        session.commit()
    return row


def _project_id(session: Session, scene: Scene) -> str:
    from app.services.chapter_service import get_project_for_chapter

    return get_project_for_chapter(session, scene.chapter_id).id


def serialize_branch(
    row: SceneBranch, depths: dict[str, int] | None = None
) -> dict:
    """`depths` 是 `_depth_map` 的产物：列表一次算全场景，不逐条回库。

    没传时按根（1）返回；单条路径应当传（见 `_detail`），否则派生分支的
    `depth` 会被报成 1。
    """
    return {
        "id": row.id,
        "scene_id": row.scene_id,
        "name": row.name,
        "parent_id": row.parent_branch_id,
        "depth": (depths or {}).get(row.id, 1),
        "note": row.note,
        "chars": count_words(row.content),
        "has_draft": bool((row.draft_content or "").strip()),
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


def serialize_branch_detail(
    row: SceneBranch, depths: dict[str, int] | None = None
) -> dict:
    return {
        **serialize_branch(row, depths),
        "content": row.content,
        "draft": (
            {"content": row.draft_content, "run_id": row.draft_run_id}
            if (row.draft_content or "").strip()
            else None
        ),
    }


def _detail(session: Session, row: SceneBranch) -> dict:
    """单条分支的完整序列化：深度也要对（写作台会拿它渲染树）。"""
    return serialize_branch_detail(row, _depth_map(session, row.scene_id))


def list_branches(session: Session, scene_id: str) -> list[dict]:
    """作者手工维护的分支列表。**不含 A/B 分支** —— 它们是同一场戏试两种
    写法的临时产物，采纳或丢弃后即删，混进来会把列表变成一次性的实验记录。"""
    _scene(session, scene_id)
    rows = session.scalars(
        select(SceneBranch)
        .where(SceneBranch.scene_id == scene_id, SceneBranch.ab_group.is_(None))
        .order_by(SceneBranch.created_at, SceneBranch.id)
    ).all()
    # 深度一次算全场景（含 A/B 行，脏数据里它们也可能被挂上子分支）。
    depths = _depth_map(session, scene_id)
    return [serialize_branch(row, depths) for row in rows]


def get_branch(session: Session, branch_id: str) -> dict:
    return _detail(session, _branch(session, branch_id))


def update_branch(
    session: Session, branch_id: str, *, name: str | None = None, note: str | None = None
) -> dict:
    row = _branch(session, branch_id)
    try:
        if name is not None:
            clean = _clean_name(name)
            other = _find_by_name(session, row.scene_id, clean)
            if other is not None and other.id != row.id:
                raise ValueError(f"这个场景里已经有叫「{clean}」的分支了")
            row.name = clean
        if note is not None:
            row.note = note.strip()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _detail(session, row)


def save_branch_body(session: Session, branch_id: str, content: str) -> dict:
    """作者手工保存：**不受锁限制** —— 锁只约束 AI。"""
    row = _branch(session, branch_id)
    new_content = content or ""
    if (row.content or "") != new_content:
        _add_revision(session, row, new_content, "author")
        row.content = new_content
        session.commit()
    return _detail(session, row)


def _add_revision(
    session: Session, row: SceneBranch, content: str, source: str
) -> BranchRevision:
    revision = BranchRevision(
        branch_id=row.id, content=content or "", source=source
    )
    session.add(revision)
    return revision


def list_branch_revisions(session: Session, branch_id: str) -> list[dict]:
    row = _branch(session, branch_id)
    rows = session.scalars(
        select(BranchRevision)
        .where(BranchRevision.branch_id == row.id)
        .order_by(BranchRevision.created_at.desc(), BranchRevision.id.desc())
    ).all()
    return [
        {
            "id": item.id,
            "source": item.source,
            "note": item.note,
            "chars": count_words(item.content),
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "preview": (
                item.content
                if len(item.content) <= 80
                else item.content[:80] + "…"
            ),
        }
        for item in rows
    ]


def save_branch_draft(session: Session, branch_id: str, content: str) -> dict:
    row = _branch(session, branch_id)
    row.draft_content = content or ""
    session.commit()
    return _detail(session, row)


def _reject_if_locked(session: Session, scene: Scene) -> None:
    """分支里的 AI 也是 AI：与主版走同一条判定。"""
    from app.services.text_service import _reject_locked

    _reject_locked(session, scene)


def _reject_missing_paragraphs(scene: Scene, content: str) -> None:
    from app.services.text_service import _reject_missing_paragraphs as check

    check(scene, content)


def adopt_branch_draft(session: Session, branch_id: str, commit: bool = True) -> dict:
    """把分支草稿变成分支正文。`commit=False` 交给调用方（A/B 要一次提交）。"""
    row = _branch(session, branch_id)
    scene = _scene(session, row.scene_id)
    _reject_if_locked(session, scene)
    content = row.draft_content or ""
    if not content.strip():
        raise ValueError("分支没有可采纳的草稿")
    _reject_missing_paragraphs(scene, content)
    if (row.content or "") != content:
        _add_revision(session, row, content, "ai")
    row.content = content
    row.draft_content = ""
    row.draft_run_id = None
    if commit:
        session.commit()
    return _detail(session, row)


def merge_branch(session: Session, branch_id: str, commit: bool = True) -> dict:
    """把分支正文合入主版。**分支保留** —— 合并是选它作主版，不是作废其余。

    `commit=False` 把提交时机交给调用方（A/B 采纳要和删两条分支一起提交）。
    """
    row = _branch(session, branch_id)
    scene = _scene(session, row.scene_id)
    _reject_if_locked(session, scene)
    content = row.content or ""
    if not content.strip():
        raise ValueError("分支正文为空，不能合入主版")
    _reject_missing_paragraphs(scene, content)

    from app.services.text_service import _supersede_audit

    project_id = _project_id(session, scene)
    old = scene.body or ""
    if old.strip():
        session.add(
            SceneRevision(
                scene_id=scene.id,
                content=old,
                source="branch",
                note=f"合并分支「{row.name}」前的主版",
            )
        )
    scene.body = content
    # 主版正文刚被整份替换，旧草稿是「针对旧正文生成、还没采纳」的材料。
    # 留着它，作者下次点「采纳为正文」就会把刚合入的正文顶掉 —— 那不是
    # 他此刻的意图。合并本身就意味着「这一版我定了」。
    stale = session.scalars(
        select(SceneDraft).where(SceneDraft.scene_id == scene.id)
    ).first()
    if stale is not None:
        session.delete(stale)
    search_service.mark_dirty(session, project_id)
    _supersede_audit(session, scene.id)
    change_service.record(
        session,
        project_id,
        target_type="scene",
        target_id=scene.id,
        target_label=_label(session, scene),
        action="adopt",
        source="author",
        summary=f"合并分支「{row.name}」（{count_words(content)} 字）",
    )
    if commit:
        session.commit()
    return {
        "branch": _detail(session, row),
        "scene_id": scene.id,
        "body": scene.body,
        "chars": count_words(scene.body),
    }


def discard_branch(session: Session, branch_id: str) -> None:
    """丢弃一条分支。**子分支不跟着死** —— 它们是作者写过的正文。

    删父之前先把指向它的 `parent_branch_id` 置空，子分支提升为根（深度
    变回 1，正文与草稿一个字不动）。**不用 FK 的 ON DELETE SET NULL**：
    这条语义由服务层显式表达，改表时才不会藏着一层看不见的级联。
    """
    row = _branch(session, branch_id)
    scene = _scene(session, row.scene_id)
    project_id = _project_id(session, scene)
    name = row.name
    session.execute(
        update(SceneBranch)
        .where(SceneBranch.parent_branch_id == row.id)
        .values(parent_branch_id=None)
    )
    session.delete(row)
    change_service.record(
        session,
        project_id,
        target_type="scene",
        target_id=scene.id,
        target_label=_label(session, scene),
        action="delete",
        source="author",
        summary=f"丢弃分支「{name}」",
    )
    session.commit()


# ---- A/B 并排生成 ----

# 保留前缀：A/B 分支在库里必须和作者手建的分支一眼分得开。名字里带 `/`
# 与 `·` 是刻意的 —— 正常命名几乎不会撞上，而重名由 `_unique_name` 兜底。
_AB_NAME_PREFIX = "A/B · "
_AB_SIDES = ("A", "B")


def _ab_side(name: str, index: int) -> str:
    """从库名解析侧别；作者改过名或格式不符时按位置兜底。

    名字形如 `A/B · A`，同场景已有同名分支时会变成 `A/B · A 2` —— 序号
    只负责让名字唯一，不改变它是 A 版。
    """
    if name.startswith(_AB_NAME_PREFIX):
        head = name[len(_AB_NAME_PREFIX) :].split(" ", 1)[0]
        if head in _AB_SIDES:
            return head
    return _AB_SIDES[index] if index < len(_AB_SIDES) else str(index + 1)


def _ab_branch(
    session: Session, scene_id: str, branch_id: str
) -> tuple[SceneBranch, str]:
    """取一条属于该场景的 A/B 分支，同时校验归属与种类。"""
    row = _branch(session, branch_id)
    if row.scene_id != scene_id:
        raise ValueError("分支不属于这个场景")
    if row.ab_group is None:
        raise ValueError("这不是 A/B 分支")
    return row, row.ab_group


def _ab_group_rows(session: Session, group: str) -> list[SceneBranch]:
    """同组分支，按名字排序 —— 保留前缀让「A 版」永远排在「B 版」前面。

    不用 `created_at` 排序：两条分支在同一个事务里建出，时间戳可能落在同一
    微秒上，同毫秒内的次序只能靠随机 uuid 兜底，`discarded` 的返回顺序会飘。
    """
    return list(
        session.scalars(
            select(SceneBranch)
            .where(SceneBranch.ab_group == group)
            .order_by(SceneBranch.name)
        )
    )


def ab_create(session: Session, scene_id: str) -> dict:
    """为一场戏开一对 A/B 分支：**一次提交**，任一条失败整体回滚。

    两条都从主版正文起步，正文在采纳之前一律不动 —— 生成覆盖的只是各分支
    自己的草稿。名字用保留前缀 `A/B · A`、`A/B · B`，重名时追加序号。

    **一场戏同时只允许一组 A/B。** 旧组未处理完时明确拒绝，而不是静默删掉
    它：普通分支列表过滤 A/B，而 `ab_current` 只回最近一组，旧组一旦被新组
    盖住就会变成刷新后找不回的残留行。
    """
    scene = _scene(session, scene_id)
    if lock_service.effective_scene_lock(session, scene)["locked"]:
        raise ValueError("这一场已锁定，不能并排生成")
    pending = session.scalars(
        select(SceneBranch).where(
            SceneBranch.scene_id == scene_id,
            SceneBranch.ab_group.is_not(None),
        )
    ).first()
    if pending is not None:
        raise ValueError("这一场还有未处理的 A/B，先采纳或丢弃它们")

    group = uuid4().hex
    branches: list[dict] = []
    try:
        for side in _AB_SIDES:
            name = _unique_name(session, scene_id, f"{_AB_NAME_PREFIX}{side}")
            row = create_branch(session, scene_id, name, commit=False)
            row.ab_group = group
            # `label` 与 GET 一致用库名，`side` 才是并排面板的两栏。
            branches.append({"id": row.id, "label": row.name, "side": side})
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"group": group, "branches": branches}


def ab_adopt(session: Session, scene_id: str, branch_id: str) -> dict:
    """采纳一版：adopt 草稿 → merge 进正文 → 删同组**全部**分支，一次提交。

    `ab_create` 保证同场景只有一组，所以「同组」就是「这一组」。
    """
    scene = _scene(session, scene_id)
    row, group = _ab_branch(session, scene_id, branch_id)
    # 还没生成是作者可重试的状态：400，不走普通分支 adopt 的 409 文案。
    if not (row.draft_content or "").strip():
        raise ValueError("这一版还没有生成内容")
    # merge 只在旧主版非空时写修订 —— 与它自己的判定保持同一口径。
    revision_created = bool((scene.body or "").strip())
    try:
        adopt_branch_draft(session, row.id, commit=False)
        merged = merge_branch(session, row.id, commit=False)
        group_rows = _ab_group_rows(session, group)
        discarded = [item.name for item in group_rows]
        for item in group_rows:
            session.delete(item)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {
        "revision_created": revision_created,
        "body": merged["body"],
        "chars": merged["chars"],
        "discarded": discarded,
    }


def ab_discard(session: Session, scene_id: str, branch_id: str) -> dict:
    """丢弃一版。**同组另一条保留** —— 才能继续采纳或再丢弃它。

    A/B 组固定两条，所以删掉一条后另一条就是「未完成的那一版」；界面上的
    「两版都不要」是连点两次，而不是一步删两条。
    """
    scene = _scene(session, scene_id)
    row, _group = _ab_branch(session, scene_id, branch_id)
    name = row.name
    try:
        session.delete(row)
        change_service.record(
            session,
            _project_id(session, scene),
            target_type="scene",
            target_id=scene.id,
            target_label=_label(session, scene),
            action="delete",
            source="author",
            summary=f"丢弃 A/B 分支「{name}」",
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"removed": [name]}


def ab_current(session: Session, scene_id: str) -> dict:
    """该场景**最近一组**未处理的 A/B；没有则 `{"group": None, "branches": []}`。

    「最近一组」按创建顺序倒序的第一条定位组号：同一事务里的两条 `created_at`
    可能落在同一微秒上，SQLite 的 `rowid` 才是真正的写入顺序 —— 只按时间排，
    库里有历史遗留的多组时可能把旧组当成新组。正常路径下 `ab_create` 保证
    同时只有一组。
    """
    _scene(session, scene_id)
    latest = session.scalars(
        select(SceneBranch)
        .where(
            SceneBranch.scene_id == scene_id,
            SceneBranch.ab_group.is_not(None),
        )
        .order_by(
            SceneBranch.created_at.desc(),
            literal_column("scene_branch.rowid").desc(),
        )
    ).first()
    if latest is None:
        return {"group": None, "branches": []}

    rows = _ab_group_rows(session, latest.ab_group or "")
    return {
        "group": latest.ab_group,
        "branches": [
            {
                "id": row.id,
                # 作者看到的标签就是库里的名字（`A/B · A`），不是侧别。
                "label": row.name,
                "side": _ab_side(row.name, index),
                "has_draft": bool((row.draft_content or "").strip()),
                # 面板显示「这一版」的字数：生成先落草稿，所以有草稿看草稿，
                # 没有才回落到分支正文（建组时它从主版继承而来）。
                "chars": count_words(
                    row.draft_content
                    if (row.draft_content or "").strip()
                    else row.content
                ),
            }
            for index, row in enumerate(rows)
        ],
    }

