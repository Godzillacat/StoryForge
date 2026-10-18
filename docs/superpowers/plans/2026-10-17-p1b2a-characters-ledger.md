# P1b-2a 人物（含称呼表）· 实施过程账本（归档）

> 本文件是实施期账本的归档副本，来源是 git-ignored 的工作区（`.superpowers/sdd/2026-10-17-p1b2a-characters/progress.md`）。
> 原文按时间顺序记录，含每个任务的实施/审查结论、控制方裁定、延后 Minor 与最终整支复查的分诊。
> **裁定与延后项以本文件为准**；阶段记录的摘要见 `CLAUDE.md` §7。
>
> Plan: `docs/superpowers/plans/2026-10-17-p1b2a-characters.md` ｜ Spec: `docs/superpowers/specs/2026-10-17-p1b2a-characters-design.md`

- 工作树：`.claude/worktrees/p1b2a-characters`（分支 `worktree-p1b2a-characters`，基点是 `53509bb` = master，master 不动）
- Spec：`docs/superpowers/specs/2026-10-17-p1b2a-characters-design.md`
- 本计划的工作区是新起的一份，**不与前一计划的账本工作区共用**（`.superpowers/sdd/2026-10-16-migration-and-contract/` 属另一份计划，不读不写）
- 上一份计划（迁移框架与契约容错）的经验：**账本必须实时写**，因为上一个会话正是上下文超限中断、没留账本，Task 1–3 的完成记录只能靠 `git log` 追认

## 进度

- Task 1（词表唯一真相与接口下发）：**complete**（`29a2e80`，235 passed，审查 clean，6 条 minor 已分诊）
- Task 2（八列与第一条真实迁移）：实施中
- Task 3（服务层与 API 接线）：未开始
- Task 4（契约与提示词）：未开始
- Task 5（前端编辑器按类型渲染）：未开始
- Task 6（前端术语表类型筛选）：未开始
- Task 7（真实模型复验）：未开始
- Task 8（同步 CLAUDE.md）：未开始

## 派发前扫描

### 任务之间共享文件或接口的行

| 一对任务 | 一方产出 ↔ 另一方消费 | 结论 |
|---|---|---|
| T1 → T2 | `CHARACTER_FIELDS`（键 → 标签/多行）↔ 迁移语句由同一份定义生成 | ✅ 键与列名同源，不可能漂移 |
| T1 → T3 | 同上 ↔ `_FIELD_TO_COLUMN` 派生八条 `{k: k}` | ✅ 列名等于键名，与 T2 建出的列一致 |
| T1 → T4 | 同上 ↔ 契约属性与 T4 测试的 import | ✅ 同一份定义的两次消费 |
| T1 → T5 | `/api/entry-types` 的 `character_fields: [{key,label,multiline}]` ↔ `EntryTypesResponse.character_fields` | ✅ 形状逐字一致 |
| T1 → T3（同文件） | 两者都改 `backend/app/api/world.py`，但改的是不同函数（`list_entry_types` ↔ `_entry_out`） | ✅ 顺序执行，不并行派发 |
| T3 → T5 | `_entry_out` 输出八键 ↔ `SettingEntry` 加八字段 | ✅ |
| T3 → T5（候选路径） | 候选不是走 `_entry_out`，而是模型原样返回的 `parsed.entries` ↔ `SuggestedEntry` | ✅ T5 已含 `SuggestedEntry`（自查时补上的） |
| T4 → T7 | 契约里的人物八项 ↔ 复验要看的就是它 | ✅ |
| T5 / T6（同触前端） | 文件不重叠（EntryEditor/CandidateList/World/client.ts ↔ Terms.tsx） | ✅ 无冲突 |

### 每个任务自身的自洽

| 任务 | 结论 |
|---|---|
| T1 | ✅ 三条测试与实现一致；`test_world_api.py` 里既有的两条断言比的是 `ENTRY_TYPES` 派生值，加一类自动跟上 |
| T2 | ⚠️ **这一格被实施推翻**：当初认可「迁移语句从 `CHARACTER_FIELDS` 派生、测试与它对拍」，实为设计错误（迁移是历史记录，不能跟着可变常量走）—— 见下方 Task 2 记录的裁定。runner 测试用原始 SQL 造旧结构库那部分仍然成立 |
| T3 | ✅ 自查时把两条测试从占位改成真实夹具写法（`_project(session)` / `POST /api/projects`）；服务层 `create_entry` / `update_entry` 内部已 commit，测试不再手写 commit |
| T4 | ✅ 新增的提示词文字是**纯中文**（既有护栏 `test_preset_prompts_do_not_hand_list_field_keys` 会拦英文字母）；契约属性从 `CHARACTER_FIELDS` 生成，与「每个属性要有中文 title」那条护栏相容 |
| T5 / T6 | ✅ 前端，无自动化测试，计划里给了逐条手工走查清单（项目约定：UI 不写自动化测试） |
| T7 / T8 | ✅ 复验与文档，无代码产出的自洽性问题 |
| 计划是否要求了评审规则视为缺陷的东西 | ✅ 无（没有空断言测试，没有逐字重复的逻辑块） |

## 裁定

- Ruling: **Task 2 Step 6 允许在作者的真实库上启动一次**（迁移框架交付以来第一次真正执行改表路径），动手前手工复制一份库文件为保险 — 理由：这是本切片的核心验收（设计 §1.2 第 1 条），且迁移只加可空列、是原地操作，不改既有列、不删数据 — 若判断有误的代价：多一个「数百 KB」的备份文件；且迁移本身已由测试覆盖，真库那一步只是让它在真实数据上走一遍。
- Ruling: **Task 7 真实模型复验前先确认要用的模型在免费额度内** — 理由：既有约定（阿里云百炼，10 个模型各 1M tokens，用完即停），复验要花额度，先确认再跑 — 若判断有误的代价：一次调用被拒，白等一轮。

## Task 1 记录

- Task 1: 实施者报告 DONE，提交 `29a2e80`，`uv run pytest -q` → **235 passed**（232 基线 + 新增 3 条），无既有测试变红
- Task 1: 实施者按控制方要求，RED 分两处实证（`ImportError: cannot import name 'CHARACTER_FIELDS'`；类型集合缺 `character` 被收集期 ImportError 掩盖，另用一行 python 单验）—— 后者是它自己发现并补验的，值得记一笔
- Task 1: 实施者回报「全仓只有一处真会红」的判断成立；并主动搜了一遍「有没有第二份八类清单」，只命中定义处与注释 —— 正是本任务最该防的东西
- Task 1: 顾虑「前端 `EntryTypesResponse` 尚未加 `character_fields`」—— **不构成缺口**，那是 Task 5 的范围（控制方派发时已说明）
- Task 1: 任务审查进行中（覆盖 `53509bb..29a2e80`）
- Task 1: complete (commits 53509bb..29a2e80, review clean)
- Task 1: minor (deferred **→ 挂到 Task 4**): `app/agents/roster.py:164` 的注释写「八类清单由词表派生」，加人物后是九类 —— 该文件在 Task 4 的改动范围内，一并改掉
- Task 1: minor (deferred **→ 挂到 Task 4**): `tests/test_roster.py:183` 的 docstring 写「必须把八类都讲到」，同上；循环本身遍历 values() 是对的，只是散文过期
- Task 1: minor (parked): `world_types.py:24` 的 `dict[str, tuple[str, bool]]` 把布尔值放成无标签的位置参数。brief 逐字规定的形状，审查者明说「不当缺陷」；只提醒第二个消费方（契约）**解构取值而不是下标索引**
- Task 1: minor (parked): `tests/test_world_api.py:15-22` 拿响应与 `CHARACTER_FIELDS` 本身对拍，理论上手抄一份等价清单也能过 —— 与该文件既有那条同一局限，属本仓库既有的「弱但可接受」模式
- Task 1: minor (parked): 类型顺序没有被任何测试钉住（`character` 在 `term` 之前）—— 只影响接口/下拉/契约句子的展示顺序，不影响正确性
- Task 1: minor (parked): 审查者无法从 diff 复现「235 passed, 1 warning」；warning 归因于既有的 Starlette 弃用告警，无新告警证据
- Task 1: 审查者另核过一件跨切面的事：**前端不会因为多出第九类而漏项** —— `EntryTypesResponse` 是 `{types, hardness}`，所有渲染都是遍历 payload，没有穷尽的 `Record<type, …>` 会漏掉新类型

## Task 2 记录

- Task 2: 实施者报告 DONE_WITH_CONCERNS，提交 `8018e8e`，`uv run pytest -q` → **237 passed**（净增 2 条）
- Task 2: 实施者顾虑 1（三个既有 runner 用例被打破）—— **采纳**。根因是它们用 `create_all` 造库（建的是最新结构）再重放真实迁移、必撞 `duplicate column name`；这类库在真实世界不存在（全新库走盖章、存量库缺列），属测试前提问题。实施者只修前提、断言一字未动，分寸对。
- Task 2: 实施者顾虑 2（brief 断言 `== [(1,)]` 不成立）—— **实施者对我错，采纳**。存量库必先盖基线 0 再跑 v1，表里是两行 `[(0,), (1,)]`。这是**控制方的计划缺陷**，已纠正。
- Task 2: 实施者顾虑 3（v1 语句从**可变**的 `CHARACTER_FIELDS` 派生）—— **确认是真隐患，且是控制方的设计错误**。后果：日后加第九个键 → 所有已跑到 v1 的库（含作者的）永远拿不到那一列，新装库有、**测试全绿**，静默分叉。**Ruling: v1 的八条语句写死成字面量**，注释写明「迁移是历史记录、新增字段要新开一条迁移」；并把那条「与 `CHARACTER_FIELDS` 对拍」的测试换成「把冻结内容钉成字面量」—— 前者恰恰是同义反复的陷阱形状 — 理由：迁移一旦在别人的库上执行过就是既成事实，不能跟着一个日后会改的常量走 — 若判断有误的代价：日后加人物字段时要多写一条迁移（而这本来就是正确做法）。
- Task 2: **控制方独立复核真实库（不采信转述）** —— `schema_migration` = `[(0, 基线), (1, setting_entry 加人物八列)]`；人物八列齐全；project 2 / setting_entry 4 / provider 1 / agent 3 / idea 2 **与迁移前逐一相符**；手工备份 `backup-pre-character-columns.db` 在位
- Task 2: **框架的「执行前自动备份」第一次真正触发** —— 数据目录里出现 `backups/pre-migration-v1-20261017-013123/`（含 -wal/-shm）。上一个切片做完时 `MIGRATIONS` 为空，这条路径从未执行过；本任务是它的第一次实战
- Task 2: fix round 1 进行中（v1 语句冻结）
- Task 2: fix round 1 —— `240cf6c` 把 v1 的八条语句冻结为字面量、注释写明「迁移是历史记录」、`CHARACTER_FIELDS` 的 import 一并删掉（顺带消解了「db 层依赖领域词表」这层耦合）；那条同义反复的对拍断言换成 `test_the_first_real_migration_is_frozen_history`。`uv run pytest -q` → **238 passed**
- Task 2: **实施者纠正了控制方给的对照实验设计** —— 控制方建议「改回派生式，冻结那条必须变红」，实施者指出单做无效（今天两者产出的八条逐字相同）；真正的触发条件是「派生式 **＋** `CHARACTER_FIELDS` 真长出一项」。它跑了两组：派生式+第九项 → 冻结用例 RED；冻结式+第九项 → runner 用例 RED。**这两组放一起才是完整证据链**：派生式下隐患是安静的，冻结之后隐患变成响亮的失败。— 这是本次实施里最值得记的一笔：实施者没有照做无效实验，而是把实验改对了
- Task 2: 任务审查进行中（覆盖 `29a2e80..240cf6c` 两个提交）
- Task 2: complete (commits 29a2e80..240cf6c, review clean)。审查者额外检验并**驳回**了两条候选 Important：新夹具没有掏空既有用例（三条使用处的断言与改动前逐字相同，且当时 `MIGRATIONS` 本就为空）；对照实验没有留下残留（工作树干净、`world_types.py` 与 `29a2e80` 一致）
- Task 2: minor (deferred **→ 挂到 Task 8**): `CLAUDE.md:355` 仍写「**`MIGRATIONS` 今天是空的**」—— 现在不成立，Task 8 同步文档时一并改
- Task 2: minor (parked): `tests/test_migrations.py:9-16` 没断言 `note`（`setting_entry 加人物八列` 这个串是作者可见的：会出现在 `RuntimeError` 里）
- Task 2: minor (parked): **八个 ORM 列没有直接覆盖** —— `test_models.py` 只往返既有字段，runner 用 `<=` 是子集断言，所以模型里写错列名（如 `personalty`）能一路全绿。审查者判 Minor 的理由成立：Task 3 的服务层往返会立刻暴露它。便宜护栏是断言 `set(CHARACTER_FIELDS) <= {c.name for c in SettingEntry.__table__.columns}`
- Task 2: minor (parked): runner 用例里用原始 SQL 造的「旧结构表」少建了 `created_at`/`updated_at`，与作者真库的实际形状不faithful（目前无害，因为没人读这两列）
- Task 2: 观察项（无代码影响）：作者数据目录里已有三份 pre-migration 备份

## Task 3 记录

- Task 3: 实施者报告 DONE，提交 `b687c5a`，`uv run pytest -q` → **241 passed**；RED 3 failed → GREEN 36 passed
- Task 3: 实施者**用实验证伪了控制方的一处假设** —— 控制方派发时说「服务层的往返用例会自然覆盖八个 ORM 列」。它故意把列名改错（`personality→personalityX`）实测：**服务层那条仍然绿**（`expire_on_commit=False` + 同一 session 的身份映射，`setattr` 落在未映射属性上、读回来是假的真），只有 API 那条变红。结论：八列确实被覆盖，但承重的是 **API 测试**（跨请求边界、`_entry_out` 读全八键），不是服务层那条。
- Task 3: **Ruling（顾虑 1）**：服务层那条「round_trip」改成真会回库读（`session.expire_all()` 或另开 session），并要求实施者用「改错列名必须变红」再验一次判别力 — 理由：一条在列不存在时还能过的测试，对下一个人是陷阱；评审规则明写「什么都不验的测试」是 Important 级缺陷 — 若判断有误的代价：一条测试多一行 `expire_all`。
- Task 3: **Ruling（顾虑 2）**：`_entry_out` 的八键改为从 `CHARACTER_FIELDS` 派生（`**{key: getattr(entry, key) for key in CHARACTER_FIELDS}`），并加一条「序列化输出键集合覆盖 `CHARACTER_FIELDS`」的守卫测试 — 理由：brief 让逐条列出，那会造出**第二份字段清单**，加第九项时静默漏掉；而「消灭第二份清单」正是本切片的核心约束。项目在同类岔路上选过机制而非人工同步（P1a 收口：提示词手抄字段清单改为渲染层自动注入）— 若判断有误的代价：`_entry_out` 的可读性略降一行 dict 展开。
- Task 3: 顾虑 3（RED 实际失败形态与 brief 预期不同：`create_entry(**fields)` 静默吞掉未知 kwargs）—— brief 预期写错，非缺陷，记录在案
- Task 3: fix round 1 进行中
- Task 3: fix round 1 —— `3273e34`，完整套件 **242 passed**。服务层往返测试改为**另开一个 session** 读（真回库）；`_entry_out` 八键改为 `**{key: getattr(entry, key) for key in CHARACTER_FIELDS}` 派生，并加了一条守卫测试
- Task 3: **实施者第二次纠正控制方** —— 控制方建议的 `session.expire_all()` **实测无效**（拼错列名后测试仍 PASSED）：`setattr` 落在没被 SQLAlchemy 映射的普通属性上，不在其管理范围内、`expire` 清不掉。改用另开 session 才成立。判别力对照：拼错 → `AttributeError` 红，改回 → 绿
- Task 3: 实施者另**诚实提示**：派生实现下「加了第九项却没列进序列化」这条路的红来自 `getattr` 的 `AttributeError`，不是 `<=` 断言本身；`<=` 的牙齿由第二个探针（把派生冻成前八项）单独证明。两个分支都验过
- Task 3: 四个探针（两处列名拼错、`world_types` 加第九项、`world.py` 冻结子集）全部还原，工作树干净
- Task 3: 任务审查进行中（覆盖 `240cf6c..3273e34` 两个提交）
- Task 3: complete (commits 240cf6c..3273e34, review clean)。审查者独立读夹具与引擎接线，确认服务层那条**真的回库读**了；并确认 `_FIELD_TO_COLUMN` 的就地 `update` 无副作用（全仓只有三处引用、无改名冲突、不绕开归一化分支）
- Task 3: minor (parked): `tests/test_world_service.py:256-259` 只断言了 8 项里的 4 项（brief 逐字指定），`personality/desire/fear/abilities` 的映射写错不会让它红 —— 由 API 那条覆盖
- Task 3: minor (parked): `api/world.py:130` 与 `world_service.py:25` 都隐含「列名等于键名」，但表里其它字段并非如此（`aliases → aliases_json`）。将来若有一个人物字段存到不同列名，`setattr` 会落在普通属性上、**静默不落库**。便宜护栏：`assert all(hasattr(SettingEntry, key) for key in CHARACTER_FIELDS)` —— **留给最终整支复查分诊**
- Task 3: minor (parked): 守卫用例在派生实现下的红来自 `getattr` 的 `AttributeError`（500）而非 `<=` 断言；审查者判「可接受、不是假红」（那是真实的生产故障），建议把这一披露留在测试 docstring 里

## Task 4 记录

- Task 4: 实施者报告 DONE，提交 `ec70bc8`，`uv run pytest -q` → **243 passed**（`test_roster.py` 16 passed，含三条既有护栏）；RED 2 failed（契约缺八个键）
- Task 4: 契约人物八项**从 `CHARACTER_FIELDS` 生成**（解构取值，不用下标），提示词新增纯中文第 7 条；顺带修正了 Task 1 挂过来的两处「八类」过期措辞
- Task 4: 任务审查进行中（覆盖 `3273e34..ec70bc8`）
- Task 4: complete 前的一轮修复：审查者揪出**计划的自相矛盾** —— 我写的提示词第 7 条手抄了八个人物字段的**中文标签**，而 `roster.py` 自己的注释就写着「护栏只查英文键、查不出中文值的漂移」，计划里也明写「提示词里一个字段名都不写」。**Ruling: 改派生** —— 仿 `__TYPE_LIST__` 加 `__CHARACTER_FIELD_LIST__`，由 `CHARACTER_FIELDS` 的标签 `join` 注入（替换发生在导入时，护栏扫的是替换后的最终串，所以不触护栏）— 理由：这份中文清单漂开后没有任何东西会报错，正是本切片从头到尾在防的东西 — 若判断有误的代价：提示词多一个占位符。
- Task 4: 同轮顺带把 `startswith(label)` 改成精确相等 —— 否则 title 被改成纯标签时测试仍绿，而契约里再没有信号告诉模型「这些字段只有人物才填」（schema 子集不支持条件约束）
- Task 4: parked：「`**` 展开若与通用六项同名会静默覆盖」（防御性冗余，交最终复查分诊）；「`appearance（外貌（只有人物才填））` 括号嵌套观感」（纯观感）
- Task 4: fix round 1 —— `c642d80`，243 passed。提示词改 `__CHARACTER_FIELD_LIST__` 派生、title 断言改精确；对照证据：改掉一个中文标签后最终提示词跟着变
- Task 4: 定向复评：**All findings addressed, no new Critical/Important breakage**；两项明令不改的未被越界触碰
- Task 4: **complete**（commits 3273e34..c642d80，review clean）
- Task 4: 复评的范围外观察（parked）：派生只解决了「结构性漂移」，**没有一条常驻测试**断言「最终提示词里的标签清单等于 `CHARACTER_FIELDS` 的标签」—— 将来若有人把中文清单重新写死进提示词模板，套件仍全绿（`test_preset_prompts_do_not_hand_list_field_keys` 只查英文键）。实施者的对照实验是一次性的、没落成测试

## Task 5 记录

- Task 5: 实施者报告 DONE，提交 `b0317bf`，`pnpm build` 干净、vitest 8/8；**用 playwright-cli + Edge 在隔离数据目录上完成了 brief Step 5 的全部 6 条浏览器走查**（八项按 `character_fields` 渲染、7 多行 + 弧光单行、创建/编辑回显、切类型隐藏与恢复、规则硬度既有行为、左侧分组、控制台 0 error）—— 前面几个任务里验证最实的一次
- Task 5: 候选采纳路径**未做浏览器走查**（无真实模型、route mock 被工作树守卫拒绝），实施者只列了静态核对行号 —— 如实标注了，控制方不把它当作已验证
- Task 5: **Ruling**：实施者顾虑「`characterFieldsOf` 按 brief 硬编八键」→ **要改**。渲染由接口驱动、草稿初始化却硬编八键，等于把设计 §3.1 明写要堵的那个洞（「后端加了列而前端没跟上时，作者会编辑不到那个字段，且没有任何东西会报错」）在初始化处重新开一个：加第九项时已有条目的那一项在界面上显示为空 — 若判断有误的代价：`characterFieldsOf` 多一个参数。
- Task 5: 要求实施者用「加第九项 → 草稿自动带上初始值」做判别力验证，并清理未跟踪的 `.playwright-cli/` 目录
- Task 5: fix round 1 进行中
- Task 5: fix round 1 —— `436f31b`，`pnpm build` 干净、vitest 8/8。`characterFieldsOf(entry, fields)` 改由接口清单驱动，两处 `draftOf` 共用；**实施者发现调用点实为三个按钮入口**（不是两个），首轮构建被 `TS2554` 拦下后补齐
- Task 5: 判别力验证做得很讲究 —— 它**没有**按控制方原建议去改 `CHARACTER_FIELDS`（那会驱动 `_entry_out` 的 `getattr`、无对应列会 `AttributeError`），改为在 `api/world.py` 的 `/api/entry-types` 与 `_entry_out` 里**进程内临时注入第九项**，起隔离前后端、用 Edge 实际打开页面，快照显示第九项被自动渲染且预填；随后 `git checkout --` 还原、停服务、删临时目录与 `.playwright-cli/`，`git status` 为空
- Task 5: 遗留 —— **候选采纳路径的浏览器级验证仍未做**（无真实模型、route mock 被守卫拒绝），只有静态核对行号；控制方需在后续补做
- Task 5: 任务审查进行中（覆盖 `c642d80..436f31b`）
- Task 5: **complete**（commits c642d80..436f31b，review clean）。审查者独立重跑了 `pnpm build`（干净、53 modules），并全仓 grep 确认**前端没有第二份字段清单或中文标签**（命中只在接口类型声明里）
- Task 5: minor (parked): `World.tsx` 的 `payloadOf` / `adoptCandidate` **无条件** `...next.fields` —— 打开任意非人物条目点保存会把八个空串写进去（NULL → `''`）。UI 无差别，但偏离「默认 NULL」。修法是 `...(next.type === 'character' ? next.fields : {})` —— **交最终复查分诊**
- Task 5: minor (parked): `characterFieldsOf(entry: object, …)` 丢掉编译期约束（传错对象会静默得到全空），可收窄为 `SettingEntry | SuggestedEntry`
- Task 5: minor (parked): `types` 未就绪时点开条目 → `draftOf(entry, [])` → 八项显示为空，直到重新点选（无数据损失：空 `fields` 不会发出任何键）
- Task 5: minor (parked): 报告称「`characterFieldsOf` 不会强转」，实际有 `String(...)` —— 报告措辞与代码不符（代码更安全，不需改）
- Task 5: ⚠️ 审查者**无法复核浏览器走查现场**（两轮走查：六步 + 第九项判别力），静态佐证成立但结论视为未验证 —— **控制方需在最终验收时自己补做浏览器走查**

## Task 6 记录

- Task 6: 实施者报告 DONE，提交 `0a4f9e4`，`pnpm build` 干净（产物哈希与报告一致，审查者独立重跑核对）；用 Playwright + msedge 走查了 brief Step 3 四步
- Task 6: 审查者确认：类型选项来自 `types.types`（未硬编）、关键词与类型是 AND 组合、依赖数组完整、`aria-label` 合理；并跨文件核过「类型是全局枚举、切项目不重置筛选不会产生失效键」
- Task 6: **Ruling**：空态文案在「关键词非空 + 选了一个无词的类型」时**说假话**（「老陈」存在于人物、筛「地理」却说「没有匹配老陈的写法」，而该写法其实存在）。改为按「所选类型是否本身有词」先判 — 理由：这不是措辞打磨，是让作者读到一句不成立的话，而 brief 的 Step 3 恰好落在这个组合里 — 若判断有误的代价：空态三分支多一个 `terms.some(...)`。
- Task 6: 同时要求实施者**如实回答**走查时是否在第 3、4 步之间清空了关键词 —— 这决定 brief 那一步到底达没达成
- Task 6: fix round 1 进行中
- Task 6: fix round 1 —— `a73b26c`，`pnpm build` 干净。空态改为四态（类型无词 / 类型有词但关键词不命中 / 只有关键词 / 全空）
- Task 6: 实施者**如实回答**控制方的追问：第一次走查确实是在第 3、4 步之间**清空了关键词**才选「地理」—— 也就是说 brief 那一步原先只是靠清空达成的，现已覆盖两种走法
- Task 6: 定向复评：**All findings addressed, no new Critical/Important breakage**；复评者独立枚举了全部组合（类型空/有词 × 关键词空/非空）确认没有落错文案，并确认 `typeHasTerms` 用的是**全量** `terms` 而非关键词滤过的集合
- Task 6: **complete**（commits 436f31b..a73b26c，review clean）
- Task 6: minor (parked): 切项目时 `setTerms([])` 后、新数据到达前的窗口里，若已选类型，会短暂显示「这一类还没有术语」—— 既有的「无加载门」模式延续，非本任务引入

## Task 7 记录（真实模型复验，控制方亲自执行）

- 前置确认：世界观构建师绑定 `qwen3.8-flash`（在免费额度内），服务商启用中
- **第一次运行（失败于预置）**：HTTP 200、123.2s、`structured=True`、8 条候选 —— **全是设定类（place/rule/organization/faction/event/item/concept/term），一条人物都没有**
- **根因（关键发现）**：查渲染后的提示词，里面**没有**人物八项的契约说明、也**没有**新加的人物条款 —— 模型跑的是数据库里那份**旧的预置角色卡**。`seed_agents` 按名字判「已存在就跳过」，**代码里预置的任何更新都到不了已有安装**。这不是本切片引入的（CLAUDE.md 的 P1b-1 记录里已记过「预置内容变更对已存在的库不生效」），但本切片的核心交付**恰好依赖它**，所以它从「记录在案的欠账」变成了「本切片的可用性阻塞」
- 处理方式：**用产品自己的版本化接口**（`POST /api/agents/{id}/versions`）把代码里的最新预置装成 v3 并设为当前 —— 不删任何行、不改任何既有版本（旧 v2 原样保留、可回退），模型绑定一并保留。**这是对作者真实库的一次数据变更，需在交付时明示**
- **第二次运行（成功）**：HTTP 200、132.9s、1356+8596 tokens、`structured=True`、`parse_error=None`
  - 8 条候选，**类型分布含 character×1**（其余七类各一条）
  - 人物候选八项**全部填写且是实料**：欲望 35 字、恐惧 43 字、弧光类型 65 字、能力边界 78 字、说话风格样本 33 字（含一句代表台词）
  - **称呼列了 11 种**（含敌对方的贬称、内部自称、以及「主角（作者未定）」），正是设计要的「全部称呼方式」
  - 18 条 `open_questions`，大量采用「候选/待确认」的措辞 —— 与「不编」一致
- 判定：**验收 §1.2 第 5 条达成**（人物候选可以出现，且质量可用）；但**「预置更新到不了已有安装」必须作为本切片的交付阻塞项上报作者**

## Task 8 记录

- Task 8: 实施者报告 DONE，提交 `962f53d`（仅 `CLAUDE.md`，+45/−2）。§7 路线图插入 P1b-2a ✅、原 P1b-2 改为「P1b-2b 关系网与时间线」；§7 新增完整阶段记录（拆分理由、产出、五条裁定含控制方两个错误与实施者两次纠正、真实模型两次运行与根因）；§8 新增 7 行；迁移框架记录里「`MIGRATIONS` 今天是空的」改为历史表述
- Task 8: 遗留里记入**交付阻塞** —— `seed_agents` 幂等导致预置更新到不了已有安装，建议下一段前做薄切片，方向留待作者裁决
- Task 8: 任务审查（`a73b26c..962f53d`）：spec ❌ —— 一条 Important + 一条 Minor；其余事实核对全对（11 个提交、`240cf6c`、243 passed、两次真实运行的数字与 token、作者库 v1 与八列、世界构建师 v3 与版本保留、`seed_agents` 跳过逻辑）
- Task 8: **Ruling**：文档声称「验收 §1.2 第 5 条达成」，但该条有两半 —— 候选侧（已验）与「采纳后落库、编辑器回显」（**未验**：真库无 character 条目，Task 5 报告明说采纳路径没做浏览器走查）。改写为只声称候选侧，并把未验的一半写进遗留 — 理由：阶段记录的价值在于「验了什么、没验什么」，虚报一条会让下一段以为采纳路径已被证明 — 若判断有误的代价：多一句免责说明。
- Task 8: **Ruling**：「八项定义一次 / 唯一真相」过宽 —— 标签与多行形态确实单一来源，但八个键仍在 Pydantic 两个模型与 ORM 里显式声明，且新增字段必须新开迁移。改写为「标签与形态定义一次」，并点名两处编辑面与迁移要求 — 理由：一句「唯一真相」会让下一段以为加第九项只改一处 — 若判断有误的代价：一段说明变长两行。
- Task 8: fix round 1 —— `c474107`（仅 `CLAUDE.md`，+3/−2），243 passed 不变
- Task 8: 定向复评：**both ADDRESSED, no new breakage**；复评者独立确认新措辞没有过度修正（仍保留「标签与形态单一来源」这句真的）
- Task 8: **complete**（commits a73b26c..c474107，review clean after 1 fix round）

## 最终整支复查（`53509bb..c474107`，opus）

- 复查者独立重跑：backend `243 passed`（1 条既有 Starlette 弃用告警）、frontend `pnpm build` 干净（53 modules）
- **结论：可合并（需向作者明示两条）** —— 无 Critical、无 Important **代码**缺陷
- 强项（复查者原话要点）：迁移八条语句**冻结为字面量**是本切片最吃重的决定，做对了；`test_the_first_real_migration_is_frozen_history` 把这条钉住；标签与形态的单一来源是真的（四处派生 + 提示词占位符）；作者数据安全（只加可空列，真库复核 data 一条不少）；往返测试用**新开 session** 强制真回库，修掉了 identity-map 假过；`seed_agents` 阻塞被如实写进阶段记录，没有粉饰
- 唯一 Important：**`seed_agents` 幂等导致预置更新到不了已有安装**。复查者判定：不是本 diff 的代码缺陷（本切片只是把这条既有欠账从「小账」变成「交付阻塞」），已由控制方用版本化接口在真库装 v3 临时解除；**必须在合并时向作者明示，并作为下一段之前的薄切片**
- 延后 Minor 分诊：**8 组全部 can-wait**。其中一条建议顺手做（非必须）：`World.tsx` 的 `payloadOf` / `adoptCandidate` 无条件 `...next.fields`，保存非人物条目会把八个空串写进去（NULL → `''`）。修法一行 `...(next.type === 'character' ? next.fields : {})`
- 其余 Minor（均 can-wait）：`EntryCreate` 的八项默认 `""` 与 ORM 的 `None` 不对称（被 `exclude_unset=True` 变成死默认）；设计文档 §6 把 `_entry_out` 的文件写成了 `_serializers.py`（实际在 `api/world.py`）；`characterFieldsOf` 参数类型是 `object`；序列化「派生」没有独立护栏（缺第九项时靠 `getattr` 的 `AttributeError` 变红）；提示词中文标签清单无常驻一致性测试；迁移 `note` 未断言；术语页切项目有短暂空态窗口
- 未做修复波：无 Critical/Important 代码缺陷；上述 Minor 全部 can-wait，且复查者明说「Ready to merge」

## 收口

- [x] Task 8 审查
- [x] 最终整支复查
- [x] 归档账本到 `docs/superpowers/plans/2026-10-17-p1b2a-characters-ledger.md`，并把 CLAUDE.md 指向归档路径
- [ ] `superpowers:finishing-a-development-branch` 收口；**合并 master 需作者点头**
- [ ] 交付时向作者明示两件事：(1) 我在其真库上装了世界观构建师 v3（旧 v2 保留可回退）；(2) 预置更新缺口
