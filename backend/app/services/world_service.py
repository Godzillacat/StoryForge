"""世界观聚合的业务：设定条目、条目之间的关联、术语投影。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Chapter,
    EntryRelation,
    Scene,
    SettingEntry,
    TimelineEvent,
    Volume,
)
from app.world_types import CHARACTER_FIELDS, normalize_hardness, normalize_type

# 服务层说领域名（aliases / tags），存储层的 *_json 后缀不往上传 ——
# 与 idea_service.create_idea(..., tags) 的既有约定一致。
# type 与 hardness 不在此列：它们要归一化，单独处理。
_FIELD_TO_COLUMN = {
    "name": "name",
    "aliases": "aliases_json",
    "tags": "tags_json",
    "summary": "summary",
    "description": "description",
    "source_run_id": "source_run_id",
}

# 人物八项的列名就等于键名 —— 从唯一真相派生，不手抄第二份。
_FIELD_TO_COLUMN.update({key: key for key in CHARACTER_FIELDS})


def _apply_entry_fields(entry: SettingEntry, fields: dict) -> None:
    """把外部字段落到条目上，途中的类型与硬度一律归一化。"""
    if fields.get("type") is not None:
        entry.type = normalize_type(fields["type"])
    if "hardness" in fields:
        entry.hardness = normalize_hardness(fields.get("hardness"))
    for name, column in _FIELD_TO_COLUMN.items():
        value = fields.get(name)
        if value is not None:
            setattr(entry, column, value)
    # 类型不是规则类时，硬度没有意义 —— 留着会让界面显示一个不存在的概念。
    # 这条在 update 路径上同样生效：把一条规则改成「势力」会清掉它的硬度。
    if entry.type != "rule":
        entry.hardness = None


def list_entries(
    session: Session, project_id: str, type: str | None = None
) -> list[SettingEntry]:
    query = select(SettingEntry).where(SettingEntry.project_id == project_id)
    if type:
        query = query.where(SettingEntry.type == normalize_type(type))
    return list(session.scalars(query.order_by(SettingEntry.created_at)))


def get_entry(session: Session, entry_id: str) -> SettingEntry | None:
    return session.get(SettingEntry, entry_id)


def create_entry(session: Session, project_id: str, **fields) -> SettingEntry:
    entry = SettingEntry(project_id=project_id, type="concept", name="")
    _apply_entry_fields(entry, fields)
    if not entry.name.strip():
        raise ValueError("设定条目必须有名称")
    name = entry.name
    session.add(entry)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        # 唯一约束在数据库上，但作者要看到中文原因而不是堆栈
        raise ValueError(f"这个项目里已经有叫「{name}」的条目了") from exc
    return entry


def update_entry(session: Session, entry_id: str, **fields) -> SettingEntry:
    entry = session.get(SettingEntry, entry_id)
    if entry is None:
        raise ValueError(f"设定条目不存在：{entry_id}")
    _apply_entry_fields(entry, fields)
    # 与 create 对称：Pydantic 的 min_length=1 只挡空串，挡不住纯空白
    if not entry.name.strip():
        # 先回滚再抛：apply 已把空名写进内存里的这条，不回滚的话它会留在
        # session 里（autoflush 关着，读回来就是那个空白名），调用方若接着
        # 提交就会把空白名落库 —— 与下面 IntegrityError 分支同一处理。
        session.rollback()
        raise ValueError("设定条目必须有名称")
    # 先把名字取出来再提交：rollback 会让实例 expire，之后再读 entry.name
    # 会重新查库拿回改动前的旧名字，报错就会指着正在编辑的那条说「已经有它了」。
    name = entry.name
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError(f"这个项目里已经有叫「{name}」的条目了") from exc
    return entry


def delete_entry(session: Session, entry_id: str) -> None:
    entry = session.get(SettingEntry, entry_id)
    if entry is None:
        raise ValueError(f"设定条目不存在：{entry_id}")
    # 时间线的参与者与场景的出场人物都是 JSON 列表，外键管不到 —— 显式剔除。
    # JSON 列必须 **赋新列表**再提交，原地 mutate 不会被 SQLAlchemy 跟踪。
    # 地点由 FK 的 ON DELETE SET NULL 处理。
    events = session.scalars(
        select(TimelineEvent).where(TimelineEvent.project_id == entry.project_id)
    ).all()
    for event in events:
        participants = list(event.participants_json or [])
        if entry_id in participants:
            event.participants_json = [pid for pid in participants if pid != entry_id]
    scenes = session.scalars(
        select(Scene)
        .join(Chapter, Scene.chapter_id == Chapter.id)
        .join(Volume, Chapter.volume_id == Volume.id)
        .where(Volume.project_id == entry.project_id)
    ).all()
    for scene in scenes:
        character_ids = list(scene.characters_json or [])
        if entry_id in character_ids:
            scene.characters_json = [
                cid for cid in character_ids if cid != entry_id
            ]
    session.delete(entry)
    session.commit()


def list_relations(session: Session, project_id: str) -> list[EntryRelation]:
    return list(
        session.scalars(
            select(EntryRelation)
            .where(EntryRelation.project_id == project_id)
            .order_by(EntryRelation.created_at)
        )
    )


def normalize_strength(value: int | None) -> int | None:
    """关系强度只收 1–5 的整数；None 表示未评。

    服务层再校验一次，不只依赖 Pydantic：服务层是纯逻辑、会被直接调用，
    而 router 的 422 只保护 HTTP 边界。bool 是 int 的子类，必须显式排除。
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError("关系强度必须是 1–5 的整数")
    return value


def get_relation(session: Session, relation_id: str) -> EntryRelation | None:
    return session.get(EntryRelation, relation_id)


def _validate_relation_endpoints(
    session: Session, project_id: str, from_id: str, to_id: str
) -> None:
    if from_id == to_id:
        raise ValueError("关联的起点与终点不能是同一条目")
    for label, entry_id in (("起点", from_id), ("终点", to_id)):
        entry = session.get(SettingEntry, entry_id)
        if entry is None:
            raise ValueError(f"关联的{label}条目不存在：{entry_id}")
        # 跨项目的关联会让「这个项目有哪些关联」失去意义
        if entry.project_id != project_id:
            raise ValueError(f"关联的{label}条目不属于这个项目：{entry_id}")


def create_relation(
    session: Session, project_id: str, create_reverse: bool = False, **fields
) -> EntryRelation:
    """收 **fields 而不是显式签名：路由用 model_dump 展开，schema 一加字段
    显式签名就会变成运行期 TypeError。create_reverse 是显式参数，不进库。"""
    from_id = fields.get("from_id")
    to_id = fields.get("to_id")
    kind = (fields.get("kind") or "").strip()
    if not kind:
        raise ValueError("关联必须写明是什么关系")
    strength = normalize_strength(fields.get("strength"))
    note = fields.get("note") or ""
    _validate_relation_endpoints(session, project_id, from_id, to_id)

    relation = EntryRelation(
        project_id=project_id,
        from_id=from_id,
        to_id=to_id,
        kind=kind,
        strength=strength,
        note=note,
    )
    session.add(relation)
    if create_reverse:
        session.add(
            EntryRelation(
                project_id=project_id,
                from_id=to_id,
                to_id=from_id,
                kind=kind,
                strength=strength,
                note=note,
            )
        )
    session.commit()
    return relation


def update_relation(session: Session, relation_id: str, **fields) -> EntryRelation:
    """只改 kind / strength / note；端点不可改（要换端点就删了重建）。"""
    relation = session.get(EntryRelation, relation_id)
    if relation is None:
        raise ValueError(f"关联不存在：{relation_id}")
    # 先把每个要给的值算完、验完，再落到对象上 —— 任何一项校验失败时，
    # 对象必须保持原样。边验边改的话，直接调用方捕获异常后若继续提交这个
    # session，会把「kind 已改、strength 没改」的半截改动落库；HTTP 路径只是
    # 靠请求结束时 session.close() 的回滚才没暴露这个洞。
    if "kind" in fields:
        kind = (fields.get("kind") or "").strip()
        if not kind:
            raise ValueError("关联必须写明是什么关系")
    if "strength" in fields:
        strength = normalize_strength(fields.get("strength"))
    if "note" in fields:
        note = fields.get("note") or ""
    # 全部校验通过后才动对象。
    if "kind" in fields:
        relation.kind = kind
    if "strength" in fields:
        relation.strength = strength
    if "note" in fields:
        relation.note = note
    session.commit()
    return relation


def delete_relation(session: Session, relation_id: str) -> None:
    relation = session.get(EntryRelation, relation_id)
    if relation is None:
        raise ValueError(f"关联不存在：{relation_id}")
    session.delete(relation)
    session.commit()


def list_terms(session: Session, project_id: str) -> list[dict]:
    """术语表是一个投影，不是第二张表。

    每个条目的名字与别名本来就是「专有名词的标准写法」；只有名字的裸术语
    （type == "term"）也是其中的一行。P2 的「正文出现表外新词时提醒」要查
    的就是这份白名单。
    """
    terms: list[dict] = []
    for entry in list_entries(session, project_id):
        terms.append(
            {
                "entry_id": entry.id,
                "entry_name": entry.name,
                "type": entry.type,
                "form": entry.name,
                "is_primary": True,
            }
        )
        for alias in entry.aliases_json or []:
            if not alias.strip() or alias == entry.name:
                continue
            terms.append(
                {
                    "entry_id": entry.id,
                    "entry_name": entry.name,
                    "type": entry.type,
                    "form": alias,
                    "is_primary": False,
                }
            )
    terms.sort(key=lambda t: t["form"])
    return terms
