"""数据迁移的步骤表。

**迁移只做 create_all 做不到的事：改已有的表。** 新表仍由模型负责 ——
create_all 只建缺失的表，本来就够用。两套机制职责不重叠，就不会互相打架。

**一步迁移只在它的目标表已经存在时才真正适用**（见 `Migration.requires`）。
存量库不保证每张表都存在：作者的库可能停在很早的版本，P1c 才加的 scene 表
从未在它里面建出过。此时 ALTER 会撞 `no such table`，让应用拒绝启动；而那张
表随后会被 create_all 用**当前模型**建出来，而当前模型已经包含这条迁移要加的
列。所以 runner 按三种情形处理前置表：

- **全部缺失**：整步跳过（SQL 不执行）、照常盖章为已应用 —— 语义上就是
  「所有迁移都已应用」，因为结构由当前模型直接建成了最新形态；
- **全部存在**：照常执行语句并盖章；
- **只缺一部分**：拒绝执行、拒绝盖章并抛错，应用拒绝启动。create_all 只补建
  缺失的表、绝不给已存在的表加列，跳过会让已存在的表永远缺本步的列，而版本
  表却声称迁移已应用 —— 静默结构分叉。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    note: str
    statements: tuple[str, ...]  # 原始 SQL，按序执行
    # 目标表前置条件（见模块说明）：全部缺失时整步跳过；全部存在时执行；
    # 只缺一部分时拒绝执行、拒绝盖章。
    # 默认空元组，`Migration(version, note, statements)` 的位置构造保持可用。
    requires: tuple[str, ...] = ()


# 第一条真实迁移：给 setting_entry 加人物八列。
# 只加可空列 —— 原地操作，作者的存量数据不受影响。
#
# **八条语句写死成字面量，不从 CHARACTER_FIELDS 派生。** 一份迁移是**历史记录**：
# 它一旦在某个库里跑过，那条路径就再也不会重来（作者的库此刻已盖到 v1）。若从
# 可变常量派生，日后往 CHARACTER_FIELDS 添一项，已迁移的库永远拿不到那一列、
# 新装的库却有 —— 静默分叉，而且测试全跑在新库上、会全绿。新增人物字段的正确
# 做法是**新开一条迁移**，而不是改这一条、也不是改那份常量。
# v2 / v3 同样是冻结历史，日后加列只能新开版本。
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        note="setting_entry 加人物八列",
        requires=("setting_entry",),
        statements=(
            "ALTER TABLE setting_entry ADD COLUMN appearance TEXT",
            "ALTER TABLE setting_entry ADD COLUMN personality TEXT",
            "ALTER TABLE setting_entry ADD COLUMN desire TEXT",
            "ALTER TABLE setting_entry ADD COLUMN fear TEXT",
            "ALTER TABLE setting_entry ADD COLUMN arc_type TEXT",
            "ALTER TABLE setting_entry ADD COLUMN abilities TEXT",
            "ALTER TABLE setting_entry ADD COLUMN speech_style TEXT",
            "ALTER TABLE setting_entry ADD COLUMN current_state TEXT",
        ),
    ),
    Migration(
        version=2,
        note="entry_relation 加关系强度",
        requires=("entry_relation",),
        statements=(
            "ALTER TABLE entry_relation ADD COLUMN strength INTEGER",
        ),
    ),
    # 预置更新要靠两样东西：稳定的预置身份，以及「这个版本来自哪份预置」的指纹。
    # 唯一索引允许多个 NULL，只约束真正被认领的预置角色卡。
    Migration(
        version=3,
        note="agent 加预置身份与版本指纹",
        requires=("agent", "agent_version"),
        statements=(
            "ALTER TABLE agent ADD COLUMN preset_key VARCHAR(60)",
            "ALTER TABLE agent_version ADD COLUMN preset_fingerprint VARCHAR(64)",
            "CREATE UNIQUE INDEX uq_agent_preset_key ON agent(preset_key)",
        ),
    ),
    Migration(
        version=4,
        note="scene 加已采纳正文列",
        requires=("scene",),
        statements=("ALTER TABLE scene ADD COLUMN body TEXT",),
    ),
    # 逻辑自检复用 audit_issue：用 check_type 区分两类检查，layer 记逻辑层，
    # stage 隔离「开写前」与「定稿前」两套问题生命周期。
    # `requires` 只列出本步真正要改的表：从 P2a 直接升级的库还没有 audit_issue，
    # 整步跳过、由 create_all 按当前模型建出（已含这三列）。
    Migration(
        version=5,
        note="audit_issue 加检查类型、逻辑层与时机",
        requires=("audit_issue",),
        statements=(
            "ALTER TABLE audit_issue ADD COLUMN check_type VARCHAR(20) NOT NULL DEFAULT 'consistency'",
            "ALTER TABLE audit_issue ADD COLUMN layer VARCHAR(30)",
            "ALTER TABLE audit_issue ADD COLUMN stage VARCHAR(10) NOT NULL DEFAULT 'text'",
            "CREATE INDEX ix_audit_issue_scene_check ON audit_issue(scene_id, check_type, stage, status)",
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
