"""数据迁移的步骤表。

**迁移只做 create_all 做不到的事：改已有的表。** 新表仍由模型负责 ——
create_all 只建缺失的表，本来就够用。两套机制职责不重叠，就不会互相打架。

版本号从 1 开始、严格递增；baseline 记为 0（见 session.init_db 对存量库的盖章）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    note: str
    statements: tuple[str, ...]  # 原始 SQL，按序执行


# 今天是空的：当下没有需要改的已有表。第一次真正使用是 P1b-2 给 setting_entry 加列。
MIGRATIONS: tuple[Migration, ...] = ()

BASELINE_VERSION = 0
LATEST_VERSION = MIGRATIONS[-1].version if MIGRATIONS else BASELINE_VERSION


def pending(applied: int) -> tuple[Migration, ...]:
    """版本号大于 applied 的步骤，按版本号升序。

    runner 一律走这里读迁移列表，**不引用 `LATEST_VERSION`** —— 后者是导入时
    算出的常量，测试注入临时步骤（monkeypatch `MIGRATIONS`）时它不会跟着变，
    那条执行路径就永远测不到。`LATEST_VERSION` 只用于展示与版本号唯一性检查。
    """
    return tuple(sorted((m for m in MIGRATIONS if m.version > applied), key=lambda m: m.version))
