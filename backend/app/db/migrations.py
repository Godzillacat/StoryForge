"""数据迁移的步骤表。

**迁移只做 create_all 做不到的事：改已有的表。** 新表仍由模型负责 ——
create_all 只建缺失的表，本来就够用。两套机制职责不重叠，就不会互相打架。

版本号从 1 开始、严格递增；baseline 记为 0（见 session.init_db 对存量库的盖章）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.world_types import CHARACTER_FIELDS


@dataclass(frozen=True)
class Migration:
    version: int
    note: str
    statements: tuple[str, ...]  # 原始 SQL，按序执行


# 第一条真实迁移：给 setting_entry 加人物八列。
# 只加可空列 —— 原地操作，作者的存量数据不受影响。
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        note="setting_entry 加人物八列",
        statements=tuple(
            f"ALTER TABLE setting_entry ADD COLUMN {key} TEXT" for key in CHARACTER_FIELDS
        ),
    ),
)

BASELINE_VERSION = 0


def latest_version() -> int:
    """当前 schema 版本 —— 取**最大值**，不是列表末位。

    **是函数不是常量。** 常量在导入时就算好了，而测试要注入临时步骤只能
    monkeypatch `MIGRATIONS`，常量不会跟着变 —— 于是任何依赖它的代码路径
    都永远测不到（`init_db` 正是用它给全新库盖章，那是最该被测到的一步）。
    取 max 而非 `[-1]`：`pending()` 刻意容忍列表乱序，两者口径必须一致。
    """
    return max((m.version for m in MIGRATIONS), default=BASELINE_VERSION)


def pending(applied: int) -> tuple[Migration, ...]:
    """版本号大于 applied 的步骤，按版本号升序。**运行时现读**，不要缓存。"""
    return tuple(sorted((m for m in MIGRATIONS if m.version > applied), key=lambda m: m.version))
