"""世界观聚合的业务：设定条目、条目之间的关联、术语投影。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import EntryRelation, SettingEntry
from app.world_types import normalize_hardness, normalize_type

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
    session.delete(entry)
    session.commit()
