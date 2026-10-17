# P1b-2a 人物（含称呼表）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让作者能立人物 —— 人物是设定条目的一种类型，带八个专属字段；称呼并入别名，称呼表复用术语投影。

**Architecture:** 人物走 `setting_entry`（加八个可空列），不新建实体；八个字段的键与中文标签在 `world_types.py` 定义**一次**，契约、存储映射、接口下发三处派生；世界观构建师的契约里人物八项**从同一份定义生成**，提示词不手写字段清单（P1b-1 的教训）。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.x / SQLite；React + TypeScript + Vite；uv（`CLAUDE.md` §6）。

**Spec:** `docs/superpowers/specs/2026-10-17-p1b2a-characters-design.md`

## Global Constraints

- **分层硬约束**：`api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` **不依赖 FastAPI**（`CLAUDE.md` §5）。
- **标识符与代码用英文；注释、界面文案、提示词用中文**（`CLAUDE.md` §9）。注释密度跟随周围代码，只在「为什么」不明显处写注释。
- **唯一真相**：类型词表与人物字段清单只在 `app/world_types.py` 定义一次，其余处一律派生（先例：`SLOT_REGISTRY`、`ENTRY_TYPES`）。
- **提示词里不许出现英文字段键**——既有护栏 `test_preset_prompts_do_not_hand_list_field_keys` 会拦。**新增的提示词文字必须是纯中文**（连 POV 这类缩写都不行，它会被当成英文键）。
- **迁移永不建表**：新表归 `create_all`，迁移只改已有的表。迁移的语句逐条手写、按序执行。
- **纯逻辑必须测（pytest）；UI 不写自动化测试**（`CLAUDE.md` §9）。测试命令在 `backend/` 下：`uv run pytest`。
- 数据目录：`%LOCALAPPDATA%\StoryForge\`，测试里由 `conftest.py` 的 `STORYFORGE_DATA_DIR` 指向临时目录。
- **当前测试基线 232 条全绿**，每步之后都不许变红。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/world_types.py` | 词表与人物字段清单的**唯一真相** | 改 |
| `backend/app/db/models/world.py` | `SettingEntry` 加八列 | 改 |
| `backend/app/db/migrations.py` | 第一条真实迁移（加八列） | 改 |
| `backend/app/services/world_service.py` | `_FIELD_TO_COLUMN` 派生八条 | 改 |
| `backend/app/api/schemas.py` | `EntryCreate` / `EntryUpdate` 加八字段 | 改 |
| `backend/app/api/world.py` | `_entry_out` 加八键；`/entry-types` 下发字段清单 | 改 |
| `backend/app/agents/roster.py` | 契约从清单生成人物八项；提示词加一节 | 改 |
| `frontend/src/api/client.ts` | `EntryTypesResponse` / `SettingEntry` 加字段 | 改 |
| `frontend/src/components/EntryEditor.tsx` | 草稿带类型专属字段、按类型渲染 | 改 |
| `frontend/src/components/CandidateList.tsx` | 候选草稿同样带上八项 | 改 |
| `frontend/src/pages/World.tsx` | 草稿构造与提交带上八项 | 改 |
| `frontend/src/pages/Terms.tsx` | 加类型筛选（称呼表） | 改 |
| `backend/tests/test_world_types.py` | 词表断言加一类 | 改（既有断言会红） |
| `backend/tests/test_migrations.py` | 空列表断言改为「有且只有一条 v1」 | 改（既有断言会红） |
| `backend/tests/test_roster.py` | 契约属性集合断言加八项 | 改（既有断言会红） |
| `backend/tests/test_migration_runner.py` | 第一条真实迁移在旧结构库上的用例 | 改 |
| `backend/tests/test_world_service.py` | 八字段落库读回、类型改动不清空 | 改 |
| `backend/tests/test_world_api.py` | 接口下发与字段往返 | 改 |
| `CLAUDE.md` | §7 阶段记录与 §8 变更记录 | 改 |

---

### Task 1: 词表的唯一真相与接口下发

**Files:**
- Modify: `backend/app/world_types.py`
- Modify: `backend/app/api/world.py:21-27`（`list_entry_types`）
- Test: `backend/tests/test_world_types.py`、`backend/tests/test_world_api.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `CHARACTER_FIELDS: dict[str, tuple[str, bool]]` —— 键 → (中文标签, 是否多行)，八项，**有序**
  - `ENTRY_TYPES` 增加 `"character": "人物"`
  - `GET /api/entry-types` 响应增加 `character_fields: [{"key", "label", "multiline"}]`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_world_types.py`：把 `test_type_vocabulary_matches_the_spec` 的集合断言改成含 `character`，并新增一条。

```python
def test_type_vocabulary_matches_the_spec():
    assert set(ENTRY_TYPES) == {
        "place",
        "faction",
        "organization",
        "rule",
        "event",
        "item",
        "concept",
        "term",
        "character",
    }
    assert ENTRY_TYPES["rule"] == "规则体系"
    assert ENTRY_TYPES["character"] == "人物"
    assert set(HARDNESS_LEVELS) == {"hard", "soft", "atmosphere"}


def test_character_fields_are_the_eight_documented_ones():
    """八项来自上位文档 §4.4：姓名走 name、称呼走 aliases，其余八项在这里。"""
    assert list(CHARACTER_FIELDS) == [
        "appearance",
        "personality",
        "desire",
        "fear",
        "arc_type",
        "abilities",
        "speech_style",
        "current_state",
    ]
    assert CHARACTER_FIELDS["appearance"] == ("外貌", True)
    assert CHARACTER_FIELDS["arc_type"] == ("弧光类型", False)


def test_character_is_normalized_from_its_chinese_label():
    """归一化查的就是 ENTRY_TYPES —— 新增一类不需要动归一化函数本身。"""
    assert normalize_type("人物") == "character"
    assert normalize_type("character") == "character"
```

文件顶部的 import 加上 `CHARACTER_FIELDS`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_world_types.py -v`
Expected: FAIL —— `ImportError: cannot import name 'CHARACTER_FIELDS'`，以及集合断言差一个 `character`

- [ ] **Step 3: 实现**

`backend/app/world_types.py`：`ENTRY_TYPES` 增加一行（放在 `term` 之前，人物是实体不是术语），并在其下新增：

```python
# 人物（type == "character"）的类型专属字段：键 → (中文标签, 是否多行)。
# 定义**一次**：角色卡契约、存储映射（world_service）、接口下发（api/world）
# 三处都从这里派生。多一份就会漂移 —— 与 ENTRY_TYPES、SLOT_REGISTRY 同一条教训。
CHARACTER_FIELDS: dict[str, tuple[str, bool]] = {
    "appearance": ("外貌", True),
    "personality": ("性格", True),
    "desire": ("欲望", True),
    "fear": ("恐惧", True),
    "arc_type": ("弧光类型", False),
    "abilities": ("能力边界", True),
    "speech_style": ("说话风格样本", True),
    "current_state": ("当前状态", True),
}
```

`backend/app/api/world.py` 的 `list_entry_types`：import 加 `CHARACTER_FIELDS`，返回体增加一段：

```python
        "character_fields": [
            {"key": key, "label": label, "multiline": multiline}
            for key, (label, multiline) in CHARACTER_FIELDS.items()
        ],
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_world_types.py tests/test_world_api.py -v`
Expected: PASS（`test_world_api.py::test_entry_types_projection` 比的是 `ENTRY_TYPES` 派生值，自动跟上）

在 `backend/tests/test_world_api.py` 追加一条接口断言：

```python
def test_entry_types_lists_character_fields(client):
    payload = client.get("/api/entry-types").json()

    assert [f["key"] for f in payload["character_fields"]] == list(CHARACTER_FIELDS)
    assert payload["character_fields"][0] == {
        "key": "appearance",
        "label": "外貌",
        "multiline": True,
    }
```

（顶部 import 加 `CHARACTER_FIELDS`。）

- [ ] **Step 5: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 全绿（既有测试里有几处断言了「类型只有八类」，若变红说明漏改，回头补）

```bash
git add backend/app/world_types.py backend/app/api/world.py backend/tests/test_world_types.py backend/tests/test_world_api.py
git commit -m "feat(world): 人物入类型词表，人物字段清单定义一次并经接口下发"
```

---

### Task 2: 八个可空列与第一条真实迁移

**Files:**
- Modify: `backend/app/db/models/world.py`（`SettingEntry`）
- Modify: `backend/app/db/migrations.py`（`MIGRATIONS` 由空变一条）
- Test: `backend/tests/test_migrations.py`、`backend/tests/test_migration_runner.py`

**Interfaces:**
- Consumes: `CHARACTER_FIELDS`（Task 1）
- Produces: `SettingEntry` 上八个可空列，列名等于 `CHARACTER_FIELDS` 的键；`MIGRATIONS` 含 `version=1` 的一条，note 为 `setting_entry 加人物八列`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_migrations.py`：把 `test_today_the_list_is_empty_and_that_is_fine` 整条替换掉（它的注释原话就是「框架的第一次真正使用是 P1b-2 给 setting_entry 加列」—— 现在正是那一刻）：

```python
def test_the_first_real_migration_adds_the_character_columns():
    """框架自建好以来 MIGRATIONS 一直是空的 —— 这是它的第一条。

    只加可空列：SQLite 的 ALTER TABLE ADD COLUMN 对可空列是原地操作，
    作者的存量数据不受影响，也不触发改列类型所需的 12 步重建。"""
    assert [m.version for m in migrations.MIGRATIONS] == [1]

    step = migrations.MIGRATIONS[0]
    assert set(CHARACTER_FIELDS) == {
        statement.split("ADD COLUMN ")[1].split()[0] for statement in step.statements
    }
    assert all(statement.startswith("ALTER TABLE setting_entry ADD COLUMN ") for statement in step.statements)
    assert migrations.latest_version() == 1


def test_schema_migration_baseline_still_zero():
    assert migrations.BASELINE_VERSION == 0
```

（顶部 import 加 `from app.world_types import CHARACTER_FIELDS`。）

`backend/tests/test_migration_runner.py` 追加**最要紧的一条**：在**旧结构**的库上跑真实迁移。

```python
def test_the_character_columns_are_added_to_a_pre_existing_database(clean_db):
    """在**旧结构**的库上跑一次 —— 这才是迁移存在的意义。

    用原始 SQL 建一张没有那八列的表（模拟迁移框架引入之前建的库），再走
    init_db()，断言八列出现、且原有数据一行不少。
    """
    with clean_db.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE project (id VARCHAR(36) PRIMARY KEY, name VARCHAR(200) NOT NULL,"
            " genre VARCHAR(60) NOT NULL DEFAULT '', created_at DATETIME NOT NULL,"
            " updated_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE setting_entry (id VARCHAR(36) PRIMARY KEY,"
            " project_id VARCHAR(36) NOT NULL, type VARCHAR(30) NOT NULL,"
            " name VARCHAR(200) NOT NULL, aliases_json JSON, tags_json JSON,"
            " summary TEXT, description TEXT, hardness VARCHAR(20),"
            " source_run_id VARCHAR(36))"
        )
        conn.exec_driver_sql(
            "INSERT INTO setting_entry (id, project_id, type, name, summary)"
            " VALUES ('e1', 'p1', 'place', '南滨旧城', '小城')"
        )

    db_session.init_db()

    columns = {column["name"] for column in inspect(clean_db).get_columns("setting_entry")}
    assert set(CHARACTER_FIELDS) <= columns
    with clean_db.connect() as conn:
        rows = conn.exec_driver_sql("SELECT name, summary FROM setting_entry").fetchall()
        assert rows == [("南滨旧城", "小城")]
        # 迁移表里记下了这一步，且盖的是 v1 不是基线 0
        assert conn.exec_driver_sql("SELECT version FROM schema_migration").fetchall() == [(1,)]
```

（顶部已有 `inspect`、`Base`、`migrations`、`db_session`；补 `from app.world_types import CHARACTER_FIELDS`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_migrations.py tests/test_migration_runner.py -v`
Expected: FAIL —— `MIGRATIONS` 仍是空元组；八列还不存在

- [ ] **Step 3: 实现**

`backend/app/db/models/world.py` 的 `SettingEntry` 末尾（`source_run_id` 之后）加八列：

```python
    # 人物（type == "character"）的类型专属字段，其余类型一律 NULL。
    # 刻意**不**像 hardness 那样在类型改变时清空：这些是作者手写的长文本，
    # 误点一次类型就静默丢掉太重。代价是表里可能留下不显示的隐形数据。
    appearance: Mapped[str | None] = mapped_column(Text, default=None)
    personality: Mapped[str | None] = mapped_column(Text, default=None)
    desire: Mapped[str | None] = mapped_column(Text, default=None)
    fear: Mapped[str | None] = mapped_column(Text, default=None)
    arc_type: Mapped[str | None] = mapped_column(Text, default=None)
    abilities: Mapped[str | None] = mapped_column(Text, default=None)
    speech_style: Mapped[str | None] = mapped_column(Text, default=None)
    current_state: Mapped[str | None] = mapped_column(Text, default=None)
```

`backend/app/db/migrations.py`：import `CHARACTER_FIELDS`，把 `MIGRATIONS` 换成

```python
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
```

同时**改掉该文件顶部 `MIGRATIONS` 上方那句「今天是空的」的注释**（它已经不成立）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_migrations.py tests/test_migration_runner.py -v`
Expected: PASS

- [ ] **Step 5: 跑完整套件**

Run: `cd backend && uv run pytest -q`
Expected: 全绿

- [ ] **Step 6: 在作者的存量库上真实启动一次**

这是迁移框架交付以来**第一次真正执行改表路径**。跑之前先手工把库复制一份备用（框架自己的「有步骤才备份」这次会真的触发，但独立保险更稳）：

```bash
cp "%LOCALAPPDATA%/StoryForge/storyforge.db" "%LOCALAPPDATA%/StoryForge/backup-pre-character-columns.db"
```

然后起服务：`cd backend && uv run uvicorn app.main:app --port 8756`

核对（另开终端）：

```bash
cd backend && uv run python -c "
import sqlite3, os
p = os.path.join(os.environ['LOCALAPPDATA'], 'StoryForge', 'storyforge.db')
c = sqlite3.connect(p)
print('迁移记录:', c.execute('select version, note from schema_migration').fetchall())
cols = [r[1] for r in c.execute('pragma table_info(setting_entry)')]
print('人物八列都在:', {'appearance','personality','desire','fear','arc_type','abilities','speech_style','current_state'} <= set(cols))
print('设定条目数:', c.execute('select count(*) from setting_entry').fetchone()[0])
print('服务商数:', c.execute('select count(*) from provider').fetchone()[0])
"
```

Expected: 迁移记录为 `[(1, 'setting_entry 加人物八列')]`；八列都在；设定条目数与改前一致（改前为 4）；服务商仍为 1。**数据目录里应出现框架自己的 `backups/pre-migration-v1-*/`**（这次真有步骤要执行）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/db/models/world.py backend/app/db/migrations.py backend/tests/test_migrations.py backend/tests/test_migration_runner.py
git commit -m "feat(db): setting_entry 加人物八列，附第一条真实迁移"
```

---

### Task 3: 服务层与 API 接线

**Files:**
- Modify: `backend/app/services/world_service.py:15-24`（`_FIELD_TO_COLUMN`）
- Modify: `backend/app/api/schemas.py:101-120`（`EntryCreate` / `EntryUpdate`）
- Modify: `backend/app/api/world.py:111-125`（`_entry_out`）
- Test: `backend/tests/test_world_service.py`、`backend/tests/test_world_api.py`

**Interfaces:**
- Consumes: `CHARACTER_FIELDS`（Task 1）、八列（Task 2）
- Produces: 服务层与接口层都能读写这八个字段；`_entry_out` 输出这八个键

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_world_service.py` 追加两条（该文件已有 `session` 夹具与 `_project(session)` 助手，直接用）：

```python
def test_character_fields_round_trip(session):
    project = _project(session)

    entry = world_service.create_entry(
        session,
        project.id,
        type="人物",  # 中文名，顺便验归一化
        name="陈默",
        aliases=["阿默", "老陈"],
        appearance="瘦高，左眉有疤",
        personality="寡言，认死理",
        desire="找回被抹去的记忆",
        fear="想起自己做过的事",
        arc_type="幻灭",
        abilities="能读取他人记忆，但每读一次忘掉自己一件事",
        speech_style="「你先说。」「不必。」",
        current_state="暂居南滨，身份未暴露",
    )

    assert entry.type == "character"
    again = world_service.get_entry(session, entry.id)
    assert again.appearance == "瘦高，左眉有疤"
    assert again.arc_type == "幻灭"
    assert again.speech_style == "「你先说。」「不必。」"
    assert again.current_state == "暂居南滨，身份未暴露"


def test_character_fields_survive_a_type_change_but_hardness_does_not(session):
    """人物八项在类型改变时**保留**（长文本误删太重）；hardness 仍按老规矩清空。"""
    project = _project(session)

    character = world_service.create_entry(
        session, project.id, type="人物", name="陈默", appearance="瘦高"
    )
    updated = world_service.update_entry(session, character.id, type="势力")

    assert updated.type == "faction"
    assert updated.appearance == "瘦高"

    rule = world_service.create_entry(
        session, project.id, type="规则体系", name="记忆不可复活", hardness="硬规则"
    )
    changed = world_service.update_entry(session, rule.id, type="势力")

    assert changed.hardness is None
```

`backend/tests/test_world_api.py` 追加一条接口往返（该文件已有 `client` 夹具，项目靠 POST 现建）：

```python
def test_character_fields_round_trip_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "人物", "name": "陈默", "appearance": "瘦高", "arc_type": "幻灭"},
    ).json()

    assert created["type"] == "character"  # 中文「人物」在边界归一化
    assert created["appearance"] == "瘦高"
    assert created["arc_type"] == "幻灭"
    assert created["personality"] is None  # 没填的就是空

    listed = client.get(f"/api/projects/{project['id']}/entries").json()
    assert listed[0]["appearance"] == "瘦高"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_world_service.py tests/test_world_api.py -v`
Expected: FAIL —— `create_entry() got an unexpected keyword argument 'appearance'`

- [ ] **Step 3: 实现**

`backend/app/services/world_service.py`：import 加 `CHARACTER_FIELDS`，在 `_FIELD_TO_COLUMN` 之后补：

```python
# 人物八项的列名就等于键名 —— 从唯一真相派生，不手抄第二份。
_FIELD_TO_COLUMN.update({key: key for key in CHARACTER_FIELDS})
```

`backend/app/api/schemas.py`：`EntryCreate` 与 `EntryUpdate` 各加八个可选字段。`EntryCreate` 里默认空串、`EntryUpdate` 里默认 `None`（沿用两个类的既有差异：创建给默认值、更新不传就不覆盖）：

```python
    # 人物专属字段（type == "character" 才有意义），其余类型留空
    appearance: str = ""
    personality: str = ""
    desire: str = ""
    fear: str = ""
    arc_type: str = ""
    abilities: str = ""
    speech_style: str = ""
    current_state: str = ""
```

（`EntryUpdate` 里对应写 `str | None = None`。）

`backend/app/api/world.py` 的 `_entry_out` 增加八键（`"appearance": entry.appearance,` … 八个，逐条列出，与其它字段同格）。

**注意**：`_entry_fields` 用的是 `model_dump(exclude_unset=True)`，而服务层的 `_apply_entry_fields` 是在 `value is not None` 时才落库 —— 所以「把已填的字段清空」这条路径的行为与既有字段完全一致，不要在这里另加特殊处理。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_world_service.py tests/test_world_api.py -v`
Expected: PASS

- [ ] **Step 5: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 全绿

```bash
git add backend/app/services/world_service.py backend/app/api/schemas.py backend/app/api/world.py backend/tests/test_world_service.py backend/tests/test_world_api.py
git commit -m "feat(world): 人物八字段接通服务层与接口"
```

---

### Task 4: 契约与提示词

**Files:**
- Modify: `backend/app/agents/roster.py:103-143`（`WORLDBUILDER_SCHEMA`）、`backend/app/agents/roster.py:145-172`（`WORLDBUILDER_PROMPT`）
- Test: `backend/tests/test_roster.py`

**Interfaces:**
- Consumes: `CHARACTER_FIELDS`（Task 1）
- Produces: 世界观构建师契约的 `entries.items.properties` 含人物八项（均可选，**不进 `required`**）

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_roster.py`：把 `test_worldbuilder_schema_has_entries_and_open_questions` 的属性集合断言改为「通用六项 ∪ 人物八项」，并新增一条：

```python
def test_worldbuilder_schema_has_entries_and_open_questions():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    props = entry["output_schema"]["properties"]
    assert set(props) == {"entries", "open_questions"}
    assert entry["output_schema"]["required"] == ["entries"]
    item = props["entries"]["items"]
    assert set(item["properties"]) == {
        "type",
        "name",
        "aliases",
        "summary",
        "description",
        "hardness",
    } | set(CHARACTER_FIELDS)
    assert item["required"] == ["type", "name", "summary"]


def test_worldbuilder_character_fields_are_optional_and_generated_from_the_vocabulary():
    """人物八项**从唯一真相生成**：键与中文标签都必须与 CHARACTER_FIELDS 一致。

    它们是可选的 —— 非人物候选不填；契约校验器放过的「可选字段为 null」
    正好兜住这类省略。
    """
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "worldbuilder")
    item = entry["output_schema"]["properties"]["entries"]["items"]

    for key, (label, _multiline) in CHARACTER_FIELDS.items():
        assert key not in item["required"]
        assert item["properties"][key]["title"].startswith(label)
        assert item["properties"][key]["type"] == "string"
```

（顶部 import 加 `from app.world_types import CHARACTER_FIELDS`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_roster.py -v`
Expected: FAIL —— 属性集合少八项

- [ ] **Step 3: 实现**

`backend/app/agents/roster.py`：import 加 `CHARACTER_FIELDS`，把 `WORLDBUILDER_SCHEMA` 的 `entries.items.properties` 里 `hardness` 那一段之后补一段生成式：

```python
                    # 人物八项**从 world_types 的唯一真相生成**，不手抄 ——
                    # 中文标签也只写在那里。可选项：非人物候选不填。
                    **{
                        key: {"type": "string", "title": f"{label}（只有人物才填）"}
                        for key, (label, _multiline) in CHARACTER_FIELDS.items()
                    },
```

提示词加一节。**必须是纯中文**（护栏会拦英文字母），且不写任何字段名：

```
7. 只有当材料支持时才给人物候选，不要为了凑数编造人；给了人物，就要把外貌、性格、欲望、恐惧、弧光类型、能力边界、说话风格样本、当前状态里适用于这个人物的项写满——不适用的可以省；人物的全部称呼方式写进别名那一项。
```

（编号接在现有第 6 条之后。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_roster.py -v`
Expected: PASS（含既有的三条护栏：契约说明块覆盖每个字段、每个属性有中文 title、提示词不手写字段键）

- [ ] **Step 5: 跑完整套件并提交**

Run: `cd backend && uv run pytest -q`
Expected: 全绿

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py
git commit -m "feat(agents): 世界观构建师契约含人物八项，提示词加人物要求"
```

---

### Task 5: 前端 —— 编辑器按类型渲染

**Files:**
- Modify: `frontend/src/api/client.ts`（`EntryTypesResponse`、`SettingEntry`、`SuggestedEntry`）
- Modify: `frontend/src/components/EntryEditor.tsx`
- Modify: `frontend/src/components/CandidateList.tsx:5-15`（`draftOf`）
- Modify: `frontend/src/pages/World.tsx:19-28`（`draftOf`）、`:102-115`（`payloadOf`）、`:146-160`（`adoptCandidate`）
- Test: 无自动化测试（项目约定），靠下面的手工走查

**Interfaces:**
- Consumes: `/api/entry-types` 的 `character_fields`（Task 1）、条目输出的八键（Task 3）
- Produces: `EntryDraft` 增加 `fields: Record<string, string>`；导出 `characterFieldsOf(entry)`

- [ ] **Step 1: 接口类型加字段**

`frontend/src/api/client.ts`：

```ts
export interface EntryTypesResponse {
  types: EntryTypeOption[]
  hardness: EntryTypeOption[]
  character_fields: { key: string; label: string; multiline: boolean }[]
}
```

`SettingEntry` 增加八个 `string | null` 字段（`appearance` / `personality` / `desire` / `fear` / `arc_type` / `abilities` / `speech_style` / `current_state`）。

`SuggestedEntry` 也要加**同样八个** `string | null` 可选字段 —— 候选是模型原样返回的，键名就是契约里的英文键（契约开头写着「键名一律用英文」），字段值会一路透传到采纳那一步。

- [ ] **Step 2: 草稿带上类型专属字段**

`EntryEditor.tsx`：

```ts
export interface EntryDraft {
  type: string
  name: string
  aliases: string
  tags: string
  summary: string
  description: string
  hardness: string
  /** 类型专属字段（今天只有人物用），键与值都来自接口下发的清单 */
  fields: Record<string, string>
}

export const EMPTY_DRAFT: EntryDraft = { /* 既有字段照旧 */, fields: {} }

/** 从一条已存条目里取类型专属字段 —— World 页与候选行共用，避免两份。 */
export function characterFieldsOf(entry: {
  appearance?: string | null
  personality?: string | null
  desire?: string | null
  fear?: string | null
  arc_type?: string | null
  abilities?: string | null
  speech_style?: string | null
  current_state?: string | null
}): Record<string, string> {
  return {
    appearance: entry.appearance ?? '',
    personality: entry.personality ?? '',
    desire: entry.desire ?? '',
    fear: entry.fear ?? '',
    arc_type: entry.arc_type ?? '',
    abilities: entry.abilities ?? '',
    speech_style: entry.speech_style ?? '',
    current_state: entry.current_state ?? '',
  }
}
```

编辑器在 `draft.type === 'character'` 时渲染八项（**由 `types?.character_fields` 驱动，不硬编**）：

```tsx
      {draft.type === 'character' &&
        (types?.character_fields ?? []).map((field) => (
          <label className="block" key={field.key}>
            <span className="text-slate-500">{field.label}</span>
            {field.multiline ? (
              <textarea
                className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
                value={draft.fields[field.key] ?? ''}
                onChange={(e) => set({ fields: { ...draft.fields, [field.key]: e.target.value } })}
              />
            ) : (
              <input
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={draft.fields[field.key] ?? ''}
                onChange={(e) => set({ fields: { ...draft.fields, [field.key]: e.target.value } })}
              />
            )}
          </label>
        ))}
```

- [ ] **Step 3: 两处 draftOf 与两处提交带上八项**

- `World.tsx:draftOf`：加 `fields: characterFieldsOf(entry)`（import 自 `EntryEditor`）
- `CandidateList.tsx:draftOf`：加 `fields: characterFieldsOf(candidate)`（候选对象里带这八个键）
- `World.tsx:payloadOf`：返回值里加 `...next.fields`
- `World.tsx:adoptCandidate`：提交体里加 `...next.fields`

- [ ] **Step 4: 构建与类型检查**

Run: `cd frontend && pnpm build`
Expected: 干净（`tsc -b && vite build` 无类型错误）

- [ ] **Step 5: 手工走查**

起前后端（`uv run uvicorn app.main:app --port 8756` 与 `pnpm dev`），在浏览器里逐条核：

1. 世界观页新建一条，类型选「人物」→ 出现八个字段（外貌…当前状态），弧光类型是单行、其余是多行；
2. 填几项保存 → 重新点开该条目，八项**原样回显**；
3. 把它的类型改成「势力」→ 八个字段的输入框消失；再改回「人物」→ **内容还在**；
4. 建一条「规则体系」条目 → 硬度下拉照旧出现；把类型改成「势力」→ 硬度被清空（既有行为不变）；
5. 世界观页左侧树出现「人物」一组；
6. 控制台无错误。

- [ ] **Step 6: 提交**

```bash
git add frontend/src
git commit -m "feat(frontend): 人物八项随类型渲染，草稿与提交带上这些字段"
```

---

### Task 6: 前端 —— 术语表页的类型筛选（称呼表）

**Files:**
- Modify: `frontend/src/pages/Terms.tsx`
- Test: 手工走查

**Interfaces:**
- Consumes: 术语投影（既有 `list_terms`，无需改动）、`/api/entry-types`（取类型中文名）
- Produces: 术语表页多一个类型筛选，筛「人物」即称呼表

- [ ] **Step 1: 实现筛选**

`Terms.tsx`：加一个 `typeFilter` 状态（默认空串=全部），一个下拉（选项 = `types.types`，第一项「全部类型」），并把 `visible` 的过滤改成同时看关键词与类型：

```tsx
  const [typeFilter, setTypeFilter] = useState('')

  const visible = useMemo(() => {
    const needle = keyword.trim()
    return terms.filter(
      (t) => (!typeFilter || t.type === typeFilter) && (!needle || t.form.includes(needle)),
    )
  }, [terms, keyword, typeFilter])
```

下拉放在关键词输入框旁，并在空态文案里区分「没有匹配」与「这一类还没有术语」。

- [ ] **Step 2: 构建**

Run: `cd frontend && pnpm build`
Expected: 干净

- [ ] **Step 3: 手工走查**

1. 建一个人物，姓名「陈默」、称呼写「阿默、老陈」→ 术语表页出现三行，类型都显示「人物」；
2. 类型筛选选「人物」→ 只剩这三行（这就是称呼表）；
3. 关键词输入「老陈」→ 只剩一行；
4. 类型筛选选「地理」→ 若没有地理条目，空态说的是「这一类还没有术语」，而不是「没有匹配」。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Terms.tsx
git commit -m "feat(frontend): 术语表按类型筛选，筛人物即称呼表"
```

---

### Task 7: 真实模型复验

**Files:** 无代码改动（除非发现问题）

**Interfaces:**
- Consumes: 前三到六任务的成果
- Produces: 一份复验结论；发现的问题按常规流程修

- [ ] **Step 1: 确认额度**

**先确认要用的模型在免费额度内**（阿里云百炼，10 个模型各 1M tokens，用完即停）。看服务商配置里世界观构建师绑的是哪个模型。

- [ ] **Step 2: 跑一次**

起真实前后端，世界观页点「让 AI 提候选」，用作者的真实项目跑一次。

- [ ] **Step 3: 逐条核**

1. **候选里出现了人物**（`type` 显示为「人物」），而不是全是地理势力；
2. 人物的八项**填得住** —— 尤其「欲望」「恐惧」「能力边界」「说话风格样本」不该是空话或占位符；
3. **称呼进了别名那一项**；
4. 没有编造（对材料里没有的东西应进 `open_questions`）；
5. 采纳后落库，八项在编辑器里回显正确；
6. 调试台里**渲染后的提示词末尾含【输出契约】块，且块里有那八个字段的中文说明**。

- [ ] **Step 4: 记录结论**

把结果写进 `CLAUDE.md` 的阶段记录（Task 8 会一起做），含：模型名、tokens、耗时、以及「人物候选能不能用」的判断。

---

### Task 8: 同步工作指引

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: 前七个任务
- Produces: 无（文档）

- [ ] **Step 1: §7 路线图**

在「迁移框架与契约容错」与「P1b-2 人物与关系」之间插入一行：

```
| **P1b-2a 人物（含称呼表）** | 人物入设定条目、八个专属字段、称呼并入别名、称呼表复用术语投影 | ✅ 完成（2026-10-17） |
```

并把原「P1b-2 人物与关系」一行改为只剩「关系网、时间线」，标注「未开始（人物已在 P1b-2a 交付）」。

- [ ] **Step 2: §7 阶段记录**

新增一条，说清：为什么 P1b-2 要拆（依赖不依赖模型）、人物为什么走 `setting_entry` 加列而不是 JSON（附「专属字段继续增长就该重新考虑拆表」这条刹车）、**为什么类型改了不清空人物字段**（刻意偏离 hardness）、唯一真相在**新增一类**上第一次不用改代码就生效（归一化查词表）、称谓表为何不需要新结构、以及真实模型复验的结论。

- [ ] **Step 3: §8 变更记录**

至少包括：

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-10-17 | P1b-2 拆两段：**先人物**，关系网与时间线留下一段 | 分界线是「依赖不依赖模型」—— 人物要验模型，关系网与时间线是纯手工维护 |
| 2026-10-17 | 人物走 `setting_entry` **加八个显式列**，不用 `fields_json` | 八项是产品明确列举的固定字段、要能筛选、前端编辑器要稳定；先例是 `hardness` 这条类型专属可空列。**代价记下**：这张表已有九个只对某一类条目有值的列，专属字段若继续增长就该重新考虑拆表或 JSON |
| 2026-10-17 | 类型改成非人物时，人物八项**不清空** | 刻意偏离 `hardness` 的做法：八项是作者手写的长文本，误点一次类型就静默丢掉太重；可恢复比干净值钱 |
| 2026-10-17 | 称呼并入 `aliases_json`，称呼表 = 术语投影按类型筛选 | 契约里 `aliases` 的中文标题本就是「别名与称呼」；不新建结构，且 P2 的白名单与界面看到的是同一份 |
| 2026-10-17 | 人物不新建候选种类，就是 `entries` 里的一类 | 候选链路与归一化全都现成，并行一条只会多一份要维护的一致性 |

- [ ] **Step 4: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: 同步 P1b-2a 人物的阶段记录与变更记录"
```

---

## 附：本计划明确不做的事

- **逐章状态推进** —— 章节要到 P1c 才有，那时才有地方挂；本段只做「当前状态」一个字段。
- **弧光类型枚举化** —— 它不参与任何确定性检查；等 P4 的逻辑自检真要用它比对时再收敛。
- **关系网与时间线** —— 本切片第二段。
- **人物头像、关系图** —— 关系图是二期（D-19）。
