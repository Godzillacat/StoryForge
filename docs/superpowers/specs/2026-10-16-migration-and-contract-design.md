# StoryForge 迁移框架与契约容错 设计文档

> 版本 1.0 · 2026-10-16
>
> 上位依据：`StoryForge-产品设计文档.md` v1.0。本切片不改变其已定决策（§9.1）。
>
> 前序：`2026-10-13-storyforge-p1a-design.md`、`2026-10-14-p1a-hardening-design.md`、`2026-10-16-p1b1-worldbuilding-design.md`。

---

## 1. 阶段定义

### 1.1 为什么单独做这一段

它落在 **P1b-1 与 P1b-2 之间**，做两件都属于「地基」的事，都不产出面向作者的新功能。

**一、数据迁移框架。** `init_db()` 至今是 `Base.metadata.create_all(engine)` 一行（`db/session.py:30-33`），而 `create_all` **只建缺失的表、不改已有的表**。这条欠账已经发作过两次：

- P1a 期间给 `generation_run` 加 `parse_error` 列，你本机的库当场 500，只能删库重建；
- P1b-1 期间预置阵容的契约变了，而 `seed_agents` 幂等（已存在即跳过），旧库里的角色卡不会更新 —— 当时靠定向删表绕过。

它被记为**打包硬前置**，而 **P1b-2 会让它立刻变成硬阻塞**：人物有十个字段，若走同一张 `setting_entry` 表就要加列。

**二、契约校验器对 `null` 的容错。** 模型把可选字段写成 `null`（「这项为空」的常见写法）会让**整份 payload** 校验失败、降级成纯文本 —— 作者拿不到任何候选，只看到「未结构化」。契约里没有 nullable 的表达方式，所以这不是模型的错。P1b-1 的真实模型复验实测**未发作**（当前模型对非规则类返回空串），但它是一颗定时炸弹：换模型或换服务商即可能引爆。

两件事同批做的理由：都要动「地基」，一次动、一次验；分开做要把同一套回归跑两遍。

### 1.2 验收标准

1. 全新数据目录启动 → 由模型建表，迁移表被盖章为 **`LATEST_VERSION`**（不跑历史迁移）；
2. **存量库**（迁移框架引入之前建的）启动 → 被识别为存量、盖章为**基线 0**、跑完所有历史迁移，**不试图重建、不丢数据**；
3. 加一条迁移步骤后启动 → 该步骤执行一次、被记录；再启动 → 不重复执行；
4. 执行迁移之前**自动备份**数据库文件（仅在真有步骤要执行时）；
5. 某条迁移抛错 → 应用**拒绝启动**并给出可读原因，该步骤**不被记为已执行**；
6. 模型对可选字段返回 `null` → 校验通过（不再整批降级）；
7. 模型对**必填**字段返回 `null` → 仍判失败（那不是省略，是真空缺）；
8. 三个智能体的既有通过用例全部保持通过。

### 1.3 明确不做

- **迁移的 downgrade / 回滚。** 单机单人、从不回滚；真需要时手工写一条反向步骤。
- **自动生成迁移。** 手写有序步骤的代价，换取零依赖与「执行过什么」有记录。
- **表格重建的通用助手。** SQLite 改列类型要 12 步重建；等真需要时再写（YAGNI）。
- **SQLite FTS5 检索。** 仍在 P1b-2 之后。
- **`create_all` 的角色变更。** 见 §3.1。

---

## 2. 数据模型

只加一张**基础设施**表，不属于任何业务聚合，因此不进 `db/models/`、不建 ORM 模型 —— 它必须独立于模型存在。

```sql
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER PRIMARY KEY,
    note       TEXT NOT NULL DEFAULT '',
    applied_at TEXT NOT NULL
)
```

- `version`：已执行到的版本号。基线记为 **0**。
- 一个事务执行一条迁移，成功才插入该行 —— 「表里有这一行」就等价于「这一步已生效」。

---

## 3. 迁移框架

### 3.1 关键取舍：迁移永不建表

**新表继续由 `create_all` 按模型建**（它本来就只建缺失的表，够用）。**迁移只做 `create_all` 做不到的事：改已有的表。**

好处是两套机制职责不重叠、不会互相打架，框架因此小很多。代价：新增表时模型与库结构之间没有迁移记录可查 —— 但 `create_all` 本来就没有，这不是退步。

**但全新库要单独走一条路 —— 否则这里是引导问题。** 设想一条迁移是「给 `setting_entry` 加一列」：

- 「先迁移再建表」→ 迁移去改一张还不存在的表 → 报错；
- 「先建表再迁移」→ 表是按**最新模型**建的、那一列已经有了 → 迁移再加一次 → 报错。

两条都走不通。根因是这两种库的性质根本不同：

| | 全新库 | 存量库 |
|---|---|---|
| 它是什么 | 由**当前模型**直接建出来的 | 迁移框架引入之前就存在 |
| 它处在哪 | **天然就是最新结构** | 停在引入时的结构 |
| 该做什么 | 直接建表、**盖最新版本**，不跑历史迁移 | 盖基线、跑所有历史迁移、再建模型新加的表 |

所以 `init_db()` 分两条路，**判据是「库里有没有业务表」**：

```
无业务表（全新库） → create_all() → 盖章为 LATEST_VERSION → 结束
有业务表（存量库） → run_migrations() → create_all()（建模型新加的表）
```

「盖最新版本」不是偷懒：那张表是模型此刻的定义建出来的，它**确实**处于最新结构，把它当成「还没跑过任何迁移」才是错的。

### 3.2 模块

新建 `app/db/migrations.py`（纯数据与纯函数，不碰 engine，便于单测）：

```python
@dataclass(frozen=True)
class Migration:
    version: int
    note: str
    statements: tuple[str, ...]      # 原始 SQL，按序执行

MIGRATIONS: tuple[Migration, ...] = ()   # 今天是空的
BASELINE_VERSION = 0
LATEST_VERSION = MIGRATIONS[-1].version if MIGRATIONS else 0

def pending(applied: int) -> tuple[Migration, ...]: ...
```

**今天 `MIGRATIONS` 是空的**，因为当下没有任何需要改的已有表。框架的第一次真正使用是 P1b-2 给 `setting_entry` 加列。这不影响本切片可验证：**盖章路径（全新库与存量库）在作者的库上真实跑一遍**，而迁移的执行路径由测试覆盖（测试里临时挂一条步骤）。

**runner 一律通过 `pending(applied)` 读迁移列表，不许引用 `LATEST_VERSION`。** 理由：`LATEST_VERSION` 是模块导入时算出的常量，测试要注入一条临时步骤只能 monkeypatch `migrations.MIGRATIONS`，而常量不会跟着变；runner 若依赖常量，那条路径就永远测不到。`LATEST_VERSION` 只用于展示与版本号唯一性的那条测试。

### 3.3 runner 落点

`app/db/session.py` 新增两个函数 —— `is_fresh_database(engine)` 与 `run_migrations(engine)` —— 由 `init_db()` 按 §3.1 的两条路分派：

```
if is_fresh_database(engine):
    Base.metadata.create_all(engine)   # 模型就是最新结构
    stamp(LATEST_VERSION, "全新库")     # 所以不跑历史迁移
    return
run_migrations(engine)                 # 存量库：盖章 → 备份 → 补步骤
Base.metadata.create_all(engine)       # 再建模型新加的表（迁移不建表）
```

`is_fresh_database` 的判据：`sqlite_master` 里**没有业务表**（排除 `sqlite_%` 与 `schema_migration`）。

`run_migrations(engine)` 的算法（只对存量库）：

1. **建迁移表**（`CREATE TABLE IF NOT EXISTS`）。
2. **读已执行版本**（`MAX(version)`）；**没有记录就盖基线 0**，记 `note = "基线（迁移框架引入时的库结构）"`。
3. **有未执行的步骤时先备份**：把 `storyforge.db` 连同 `-wal` / `-shm` 复制到 `%LOCALAPPDATA%\StoryForge\backups\pre-migration-v<目标版本>-<时间戳>\`。**没有步骤要执行就不备份**（空跑不产生垃圾）。
4. **按序执行**，每步一个事务（`engine.begin()`）：执行该步的全部语句，成功后插入 `schema_migration` 行。

### 3.4 失败行为

**抛错即拒绝启动**：`run_migrations` 不吞任何异常，`init_db()` 往上抛，应用起不来。

理由：**半迁移的库比起不来的应用危险得多** —— 前者会让应用带着与模型不符的结构跑，产生难以追查的静默错数据。每步一个事务保证失败的那步不会被记为已执行，下次启动会重试它。

### 3.5 边界情况

| 情况 | 行为 |
|---|---|
| 数据目录不存在 | `config.data_dir()` 已负责创建 |
| 迁移表存在但没有行 | 与「没有记录」同路：盖章 |
| 同样的版本号出现两次 | 主键冲突 → 抛错。迁移列表的版本号必须唯一且递增，由测试钉住 |
| 备份目录已存在同名 | 时间戳精确到秒，碰撞概率可忽略；真要碰撞则 `exist_ok=True` 覆盖同名文件（同一秒内两次启动同一目标版本，内容也一样） |

---

## 4. 契约校验器放宽

### 4.1 问题

`runtime/schema.py:78-82` 的 `_validate_node` 对任何类型不符都报错：

```python
expected = schema.get("type")
if expected and not _check_type(value, expected):
    errors.append(...)
```

而父节点（`:92-94`）对「存在的键」一律递归校验。于是可选字段的 `null` 触发类型错误 → 整份 payload 失败 → 降级纯文本。

契约里没有 nullable 的表达方式（自写子集只有 `type` / `properties` / `required` / `items` / `enum` / `minItems`），所以模型写 `null` 表示「这项为空」是合理的，不该被拒。

### 4.2 改法

改在**父节点的循环**里，不在 `_validate_node` 里 —— 因为「是不是必填」只有父节点知道。

`_validate_node` 的对象分支（`:87-94`）：

```python
if expected == "object" or isinstance(value, dict):
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in value:
            errors.append(f"{path} 缺少必填字段 {key}")
    for key, sub_schema in properties.items():
        if key not in value:
            continue
        # 可选字段的显式 null 视同「没提供」：模型把「这项为空」写成 null 是
        # 常见形态，而契约里没有 nullable 的表达方式。**必填不在此列** ——
        # 那里 null 是真的缺东西，仍要按类型报错。
        if value[key] is None and key not in required:
            continue
        _validate_node(value[key], sub_schema, f"{path}.{key}", errors)
```

（`required` 从下面那行提到前面，循环体由 `for key in schema.get("required", [])` 改为 `for key in required`。）

### 4.3 这条区分是刻意的

| 情形 | 判 |
|---|---|
| 可选字段**缺键** | 通过（既有行为） |
| 可选字段显式 `null` | **通过**（本次新增） |
| 必填字段**缺键** | 失败，报「缺少必填字段」（既有行为） |
| 必填字段显式 `null` | **失败**，报类型错误（保持不变） |

可选字段的 `null` 是省略的另一种写法；必填字段的 `null` 是真空缺。两者不该一视同仁。

### 4.4 影响面

它只让校验**更宽松**，所以三个智能体（灵感解析师、架构师、世界观构建师）现有的通过用例不会因此变红 —— 这一点由回归测试钉住，而不是靠推断。

---

## 5. 测试策略

纯逻辑必须测（pytest），UI 不写自动化测试。

| 层 | 测什么 |
|---|---|
| `migrations.py` | `pending(0)` 返回全部步骤；`pending(N)` 只返回版本号大于 N 的；`LATEST_VERSION` 与空列表时的 0 |
| runner — 全新库 | 数据目录空 → `create_all` 建出全部业务表，迁移表被盖章为 **`LATEST_VERSION`**，且**一条历史迁移都没跑**（用一条会炸的迁移步骤钉住这一点） |
| runner — 存量库 | 先建一个「有业务表但没有迁移表」的库 → 启动后迁移表存在且盖章为基线 0，**业务表数据一行不少** |
| runner — 执行一次 | monkeypatch `migrations.MIGRATIONS` 临时挂一条步骤（如 `CREATE TABLE _probe(x INTEGER)`）→ 执行、记录；再跑一次 → 不重复执行 |
| runner — 失败 | 一条会抛错的步骤（如非法 SQL）→ 异常往上抛、该版本**未被记录**、备份**已产生** |
| runner — 备份 | 有步骤可执行 → 备份目录出现且含 `.db`；无步骤可执行 → **不产生**备份目录 |
| 版本号唯一递增 | 遍历 `MIGRATIONS`，版本号严格递增 |
| 校验器 — 可选 null | 三个智能体各自的契约：把**全部可选字段**置 `null` → `apply_contract` 判为通过 |
| 校验器 — 必填 null | 把某个必填字段置 `null` → 判为失败，且错误信息里含该字段名 |
| 校验器 — 回归 | 既有的合法/非法用例全部保持通过（含 `test_schema.py` 现有断言） |

**没有真实模型参与**：本切片不产出面向模型的行为变化，验收不需要花额度。

---

## 6. 任务拆分

| # | 任务 | 验证方式 |
|---|---|---|
| 1 | `migrations.py`：`Migration` / `MIGRATIONS` / `BASELINE_VERSION` / `LATEST_VERSION` / `pending` | pytest |
| 2 | runner：建表、盖章（全新 vs 存量）、按序执行、每步一个事务、失败即抛 | pytest |
| 3 | 执行前的自动备份（仅在有步骤时） | pytest |
| 4 | `init_db()` 接上 runner，并把「迁移之后才 `create_all`」的顺序钉住 | pytest + 在作者的真实库上启动一次 |
| 5 | 校验器：可选字段的显式 `null` 视同缺省；必填不受影响 | pytest（含三个智能体的契约） |
| 6 | 同步 `CLAUDE.md` §7 阶段记录、§8 变更记录，并把「打包硬前置」里的迁移一条划掉 | 人工核对 |

---

## 7. 与上位文档的一致性核对

| 上位决策 | 本切片 |
|---|---|
| D-01 本机优先 | 是。迁移与备份都在本机数据目录内，不联网 |
| D-16 一期只用 SQLite | 是。迁移是 SQLite 原生的 DDL/事务，不引入迁移工具链 |
| `CLAUDE.md` §9「不用重型依赖」 | 是。手写有序步骤，不加 alembic |
| `CLAUDE.md` §7 把迁移记为打包硬前置 | 是。本切片即兑现该前置，并在任务 6 里把它从欠账里划掉 |
