> 2026-10-16 归档。这份文件是本切片（迁移框架与契约容错）实施期间的工作区账本 —— 按本仓库
> 惯例（先例 `2026-10-14-p1a-hardening-ledger.md`、`2026-10-16-p1b1-worldbuilding-ledger.md`），
> 从 worktree 内被 `.gitignore` 忽略的 `.superpowers/sdd/2026-10-16-migration-and-contract/`
> 逐字复制至此，以免「裁定」与「延后 Minor」随工作区一起消失。**阶段记录见 `CLAUDE.md` §7；
> 设计见 `docs/superpowers/specs/2026-10-16-migration-and-contract-design.md`。**
>
> 内容包括：派发前扫描表、全部控制方裁定（Ruling）、每个任务的完成记录与审查发现、
> 整支复查与修复波复评的结论，以及延后 Minor 的分诊。
>
> **为什么 Task 1–3 标着「追认」：** 完成它们的上一会话**上下文超限中断**，既没留下账本、
> 也没留下评审计录；Task 1–3 的完成记录只能由 `git log` 事后追认。接管会话重建本账本后完成
> Task 4–6。那三个任务未经逐任务审查的代码，由最终整支复查独立覆盖。
>
> **补记（同一会话，稍后同步）：** 归档之后控制方又往工作区账本追加了「归档与收尾」与「切片
> 终态」两节 —— 记的是归档这件事自己的审查与三轮修复。为免这段随工作区消失，已从工作区账本
> 原样续写在本文件正文之后。归档那一刻的原文与后续续写之间没有内容删改。

# SDD ledger — plan: docs/superpowers/plans/2026-10-16-migration-and-contract.md

- 工作树：`.claude/worktrees/migration-contract`（分支 `worktree-migration-contract`，master 未动）
- Spec：`docs/superpowers/specs/2026-10-16-migration-and-contract-design.md`
- 本账本由接管会话于 2026-10-16 建立：**上一会话上下文超限中断，没有留下任何账本**。
  Task 1–3 的完成记录由 `git log` 追认，不是当时写下的，且**没有留下评审计录**。

## 进度

- Task 1（迁移步骤表）：complete（commits e9370fe..648c4eb，追认；评审计录缺失 → 交最终整支复查覆盖）
- Task 2（迁移 runner）：complete（commits 648c4eb..da5e6ef，追认；评审计录缺失。含两次计划修正 6090cea / 7f6a5dc 与一次实现修复 0b2ec1e / da5e6ef）
- Task 3（执行迁移前自动备份）：complete（commits da5e6ef..07dcbc8，追认；评审计录缺失）
- Task 4（`init_db` 按全新库/存量库分派）：**in flight** —— BASE `07dcbc8`，工作区留有上个会话的未提交半成品
- Task 5（契约放过可选字段的 null）：未开始
- Task 6（同步工作指引）：未开始

## 派发前扫描（仅剩任务 4/5/6）

| 检查 | 结论 |
|---|---|
| T4 消费 T2 的 `is_fresh_database` / `run_migrations` | ✅ 两者都已在 `session.py` 实现 |
| T4 消费 T1 的版本号接口 | ❌ **不一致（在途）**：计划已改成函数 `latest_version()`，而 `migrations.py` 与 `test_migrations.py` 仍用导入时算出的常量 `LATEST_VERSION` |
| T4 自身文本自洽 | ✅ 三条测试与实现片段一致（改用 `latest_version()` 后即自洽） |
| T4 Step 5 的副作用 | ⚠️ 会改作者的**真实库** `%LOCALAPPDATA%\StoryForge\storyforge.db` —— 计划明确要求的验收步，见下方裁定 |
| T5 依赖的字段名 | ✅ 已逐字核对：`idea_parser` 必填 5 项、可选 5 项与计划一致；`worldbuilder.entries.items` 必填 `[type,name,summary]`、可选 `aliases/description/hardness`，计划那条测试里非 null 的键全是可选键 |
| T5 与 T1–T4 的文件重叠 | ✅ 无（只动 `runtime/schema.py` 与 `tests/test_schema.py`） |
| T6 与 T4 的措辞 | ✅ 无冲突（变更记录里的 `LATEST_VERSION` 是散文，不指符号） |
| 计划是否要求了评审规则视为缺陷的东西 | ✅ 无（无空断言测试、无逐字重复的逻辑块） |

## 裁定

- Ruling: Task 1 的产物接口由常量 `LATEST_VERSION` 改为函数 `latest_version()`；`test_migrations.py` 与计划 Task 1 的「Produces」行随之更新 — 理由：常量在导入时就算好了，而测试要注入临时步骤只能 monkeypatch `MIGRATIONS`，常量不跟着变 —— `init_db()` 给全新库盖章这条路径将**永远测不到**，而它正是本切片最该被测到的一步 — 若判断有误的代价：已提交的 Task 1 代码与计划文本被改动约 5 行，无下游影响。
- Ruling: `_stamp` 改为 `INSERT OR REPLACE`（幂等） — 理由：`is_fresh_database` 刻意不把 `schema_migration` 算作业务表，于是「业务表被删、迁移表残留」的库被判为全新，二次盖章撞主键 → **应用启动失败**（全套件已实测为 2 条 IntegrityError）。幂等盖章下该状态的语义反而正确：`create_all` 刚把表建成最新结构，「所有迁移已应用」就是事实 — 若判断有误的代价：同一版本被重复盖章时不再报警（该信号无信息量，主键本身就是版本号）。
- Ruling: Task 4 Step 5 允许在本机真实库上启动一次，但**执行前先手工复制一份库文件** — 理由：计划明确要求（设计 §1.2 第 2 条），且该步只新增 `schema_migration` 表与一行基线，不改任何既有表、不删数据；手工备份是框架「有步骤才备份」之外的独立保险 — 若判断有误的代价：多一个数百 KB 的备份目录。

## Task 4 记录

- Task 4: fix round 0 —— 接手时工作区有上个会话的未提交半成品；由新实施者通读、纠正、补测试后收口（commits 07dcbc8..3acd36c）
- Task 4: 实施者报告 224 passed（改前 `1 failed, 220 passed, 2 errors`）；两条裁定各有独立 RED 证据
- Task 4: 控制方独立复核真实库（只读）—— `schema_migration` 恰好一行 `version=0`（note 为基线文案），project 2 / setting_entry 4 / provider 1 / agent 3 / idea 2 与改前相符；手工备份 `backup-pre-migration-framework/` 含 db + wal + shm；数据目录**没有**冒出 `backups/`（无步骤可跑，故不备份，符合设计）
- Task 4: 实施者顾虑「分派与幂等修复必须在同一提交」—— 采纳。理由成立：幂等缺陷只在分派落地后才可达，拆开则第一个提交的全套件当场是红的。无需裁定。
- Task 4: 任务审查进行中

## 追加裁定

- Ruling: 设计文档（spec）里 8 处把 `LATEST_VERSION` 当符号用（含 `§3.2` 的常量定义代码块与「产物」表）需同步为 `latest_version()` 函数，并在该处补一句「为什么是函数不是常量」；**归入 Task 6 一并收口** — 理由：spec 是权威文档，裁定一改了 Task 1 的产物接口后它指向一个不存在的符号；与 CLAUDE.md 的同步同属一批文档收口，不必为此单开一轮派发（先例：e7cc3df 就是一次 `docs(spec):` 修正） — 若判断有误的代价：Task 6 的文档提交范围比 brief 稍宽，审查者若视之为 extra 可由控制方解释（已在本账本留痕）。

## Task 4 收口

- Task 4: complete (commits 07dcbc8..3acd36c, review clean)
- Task 4: minor (deferred): `test_migration_runner.py:230-238` 的 `"_probe" not in ...` 是够不着的断言（迁移串本身就会抛错）—— brief 逐字指定，护栏性质，留着无害
- Task 4: minor (deferred): `session.py:150-153` 的全新库路径里 `create_all` 与盖章分属两个事务，窄窗口内崩溃会留下「表是最新结构、无迁移记录」的库（下次启动盖基线 0，P1b-2 真加迁移时会撞已存在列）—— plan-mandated，SQLite 的 DDL 可事务，日后可收口
- Task 4: minor (deferred): `uv run pytest` 那条 `StarletteDeprecationWarning` warning 改前就在，非本任务引入，最终复查可登记为无关
- Task 4: 审查者的两条 ⚠️ 均由控制方解决，未构成缺口 ——
  (a)「存量库盖基线 0」落在未改动的 `run_migrations` 内，diff 证不了：**控制方已在真实库上只读核对**，`schema_migration` 恰一行 `version=0` 且 note 为基线文案，验收标准达成；
  (b) spec 文档 8 处死符号：**已裁定归入 Task 6**（见上）。

## Task 5 记录

- Task 5: 实施者报告 DONE_WITH_CONCERNS，提交 `c759a27`（契约放过可选字段的 null），`uv run pytest -q` → **228 passed**（224 基线 + 4 新增），既有用例零变红
- Task 5: 实施者发现 **brief 自身的事实性缺陷** —— `worldbuilder.entries` 带 `minItems: 3`，而 brief 第三条测试的 payload 只有 1 条，该测试在改动前后都不可能通过（与本题无关）。修法取最小：第 0 条逐字保留原 payload（三个可选键全置 null），补足 3 条以满足契约的条数下限。**采纳**，判别力保留。（控制方派发前扫描漏了 `minItems`，只核了必填/可选键名 —— 记一笔。）
- Task 5: 实施者申报的第二条顾虑（「改动新开的前端窄路径」）经控制方核实**确认为真缺陷**，已扩展为本任务的一部分，见下。

## 追加裁定（Task 5 收口）

- Ruling: Task 5 放宽校验后，**显式 `null` 会流进按「缺键」写的下游代码**，需在 API 边界把可空的集合/对象型可选字段归一到空值（`api/architecture.py:39` 的 `story_bible_v0`、`api/world.py:102` 的 `open_questions`），**不在前端抄第二份守卫** — 理由：两处都会让前端抛异常（`Architecture.tsx:107` 的 `bible.logline`、`World.tsx:294` 的 `openQuestions.length`）；边界归一是纯逻辑、能被 pytest 覆盖，前端守卫落在「UI 不写自动化测试」的盲区里（先例：P1b-1 的 `_normalized_candidates` 走同一条路数） — 若判断有误的代价：两处响应体从 `null` 变成 `{}` / `[]`，语义等价，无下游影响。
- Ruling: 控制方扫描过其余同形点位并**判定安全、不动** —— `api/architecture.py:38` 的 `options` 与 `api/world.py:101` 的 `entries` 是必填（`null` 仍被判失败，到不了边界）；`normalize_hardness(None)` 内部已 `(value or "")` 归一；`Idea.tsx:137` 已有 `Array.isArray` 守卫；其余可选字符串字段为 `null` 时 React 渲染为空、不抛 — 理由：YAGNI，只修真会炸的两处 — 若判断有误的代价：另有一处漏网的 `null` 消费点，由最终整支复查或真实运行暴露。

## Task 5 收口

- Task 5: fix round 1 —— 按裁定在 API 边界归一（`c759a27` + `9ce12f0`），`uv run pytest -q` → **231 passed**（228 + 3 新增），两个修复点各有 RED（`assert None == []` / `assert None == {}`）→ GREEN；另加一条反向护栏防「一律清空」的过度修正
- Task 5: 实施者新建 `tests/test_architecture_api.py` —— 该接口此前**没有任何测试**；它自带一份 `_patch_runtime` 助手，与既有测试文件里的同形助手构成第三份副本，实施者申报理由是「提进 `conftest.py` 会改动两个既有测试文件，超出裁定范围」。**控制方不预判**，交任务审查定夺。
- Task 5: 任务审查进行中，覆盖 `3acd36c..9ce12f0` 两个提交

## Task 5 完成

- Task 5: complete (commits 3acd36c..9ce12f0, review clean)
- Task 5: minor (deferred): `tests/test_architecture_api.py:47-64` 是 `_patch_runtime` 的第三份逐字副本（与 `test_world_api.py:130-151` 一致）—— 审查者自陈「按字面口径偏 Important，但判为 Minor：测试夹具、不影响产品行为、仓库本就有两份、且控制方裁定范围排除了改既有测试文件」。修法（若要收）是把 `_patch_runtime` 与播种助手提进 `backend/tests/conftest.py`，一次消掉三份
- Task 5: minor (deferred): `test_architecture_api.py:23-45` 的 `_seed_parsed_idea` 与 `test_world_api.py:99-127` 的灵感部分实质重复，与上条同类，可一并收进 conftest
- Task 5: minor (deferred): `api/architecture.py:33-37` 的三行条件表达式与同文件 `:38` 的单行写法不一致（纯风格）
- Task 5: minor (deferred): `tests/test_world_api.py:266-271` 的 `_candidates_with` 定义位置与该文件其它助手不一致（纯风格）
- Task 5: minor (deferred): `runtime/schema.py:112/:118` 的 `validate_json` / `apply_contract` 无 docstring，本次关键语义（可选 null 视同缺键、必填不受影响）只在行内注释里
- Task 5: 审查者的跨切面专项核查**独立确认了控制方的枚举完整** —— 它逐份契约枚举了全部可选集合/对象字段并核对每条消费路径，结论是两个修复点即仅有的可达点；并确认校验器唯一调用点在 `runtime/execute.py:115`（只校验模型产出），放宽不会让作者输入混进坏数据
- Task 5: 审查者的 ⚠️（工作树是否干净、231 passed 是否复现）—— 控制方已从 git 侧确认：`9ce12f0` 已提交且工作树干净；测试数由实施者报告，最终整支复查会重跑

## Task 6 记录

- Task 6: 实施者报告 DONE —— `016ba92`（spec 8 处符号同步）+ `ff98e17`（CLAUDE.md 路线图一行、新增阶段记录、P1a 遗留划为已解决、§8 补 7 行）
- Task 6: 控制方通读 `ff98e17` 的 CLAUDE.md diff —— 阶段记录如实写下了「上一会话上下文超限中断、Task 1–3 无评审计录」，未伪造成「逐任务审查通过」；两条裁定、边界归一、验证数据、真实库核对结果均在
- Task 6: **追加裁定（顾虑 1）**：spec 第 147 行「每步一个事务（`engine.begin()`）」描述的是**已被证明回滚不了**的写法（`0b2ec1e` 的修正），而 P1b-2 写第一条真实迁移的人会照它做 —— **要改**为手写 `BEGIN`/`COMMIT` 并写上理由（第 62 / 153 行的「一个事务执行一条迁移」仍成立，不动） — 理由：spec 是权威，指向错误机制比指向不存在的符号更危险 — 若判断有误的代价：spec 多一段术语更密的实现说明。
- Task 6: **追加裁定（顾虑 2）**：CLAUDE.md 里 P1b-1 阶段的「无迁移框架」遗留要补一句「已于 2026-10-16 解决」的指向，与 P1a 那条的写法一致；**历史事实不改写** — 理由：两处不一致会让读者以为只有一条被解决了 — 若判断有误的代价：一行文档冗余。
- Task 6: 收口进行中（resume 实施者）

## 控制方的独立验证（不是转述实施者）

- 控制方在 HEAD `67af690` 上自己跑了一遍 `uv run pytest -q` → **231 passed, 1 warning**（那条 warning 是既有的 `StarletteDeprecationWarning`，非本切片引入）
- 控制方自查分支全貌：`git diff --stat a17decd..67af690` → 13 个文件、871 插入；**frontend/ 零改动**（本切片落在后端与文档）

## 待办（收尾清单，防止上下文丢失）

- [ ] Task 6 任务审查（覆盖 `9ce12f0..67af690`）
- [ ] **最终整支复查**：`review-package PLAN a17decd HEAD`，派 **opus**（最强模型），并明确告知审查者：**Task 1–3 没有评审计录**（上个会话中断），需一并覆盖；同时把下面的延后 Minor 与裁定清单交给它分诊
- [ ] 最终复查若有发现 → **一次**修复波（一个 fixer 携带全部发现）+ **一次**定向复评；残余按判停规则处理，不再开第二波
- [ ] **把本账本归档进 `docs/superpowers/plans/2026-10-16-migration-and-contract-ledger.md`**（本仓库既有的 `*-ledger.md` 惯例，见 p1a-hardening / p1b1-worldbuilding 两份）—— 注意 `CLAUDE.md` 新阶段记录的「遗留」里现在写的是「列在本切片 worktree 的账本 `.superpowers/sdd/…`（该目录被忽略，不入库）」，**这句话在归档后需要改指归档路径**，否则指向一份会随 worktree 消失的产物
- [ ] 用 `superpowers:finishing-a-development-branch` 收口；**合并 master 属于需要作者点头的动作，不要自行合并**

## Task 6 审查与修复

- Task 6: 任务审查 —— 6 项控制方要求**逐条达成**（含「只动 spec 第 147 行、第 62/153 行未动」的精确核对），且审查者独立核对了代码与数据事实（手写 `BEGIN`/`COMMIT`、`or {}`/`or []`、父节点循环豁免、真实库 0 基线与 2/4/1/3/2 行数）**全部吻合**。判定 **Needs fixes**（两处 Important）
- Task 6: fix round 1 —— 四处：
  (1) `CLAUDE.md:341`「两件都已发作过」与 `:344`「实测未发作」自相矛盾，属失实；
  (2) `CLAUDE.md:302`（P1a 收口遗留）仍以「仍为打包硬前置」结尾 —— 上一轮修的是 `:232`，实施者报告里「302 已加过指向」的前提不成立，导致上轮立意在 302 处落空；
  (3) `CLAUDE.md:376` 点了 spec 里不存在的「「产物」表」（实际是 §5 测试策略表与 §6 任务拆分表），该措辞由 Task 4 报告传给控制方派发、再传进文档；
  (4) `CLAUDE.md:355/:411`「框架因此只有百来行」与实际约 165 行不符。
- Task 6: **追加裁定**：Important 1 的措辞源自 brief Step 2 的原话，但 **brief 与 spec §1.1 冲突，spec 是权威** —— 只有迁移那条真的发作过两次，契约那条是潜在风险，按 spec 口径改写 — 若判断有误的代价：一句话的措辞偏向保守。
- Task 6: **追加裁定**：不加「事务写法」的 §8 行 —— 它不是有权衡的取舍（`engine.begin()` 是坏的，不是另一种做法），且 §7 与 spec §3.3 已完整记述，§8 再列一行是重复 — 若判断有误的代价：§8 少一条实现沿革。

- Task 6: fix round 1/5 —— 四处全部落地（`f16ac13`）：`:341` 按 spec 口径改写、`:302` 补指向、`:376` 改为实际表名、`:355/:411` 改「一百多行」。实施者另申报一处超出字面的改动：`:302` 末句「仍为打包硬前置」→「曾」，控制方**已认可**（它纠正的是一句此刻已不成立的断言，未改写历史事实）
- Task 6: 定向复评进行中，覆盖 `67af690..f16ac13`

- Task 6: complete (commits 9ce12f0..f16ac13, review clean)。定向复评：四条 finding 全部 ADDRESSED、无新破损；复评者另判定 `:302` 的「仍→曾」**不构成历史事实改写**（底层依据 §8 那条未动，`:232` 早已用同款措辞）
- Task 6: 复评者的 Out-of-Scope 观察：spec `:62` / `:153` 仍写「每步一个事务」—— 上一轮已裁定这两处仍成立、不动，非本轮引入

## 全部任务收口

Task 1–3: complete (commits e9370fe..07dcbc8, **评审计录缺失** —— 上个会话中断，交最终整支复查覆盖)
Task 4: complete (commits 07dcbc8..3acd36c, review clean, 3 minors deferred)
Task 5: complete (commits 3acd36c..9ce12f0, review clean, 5 minors deferred)
Task 6: complete (commits 9ce12f0..f16ac13, review clean)

## 最终整支复查（opus，覆盖 a17decd..f16ac13，17 个提交）

- 结论：**Ready to merge? Yes**。无 Critical。Task 1–3 那些没被审过的代码**独立复核未见新缺陷**，已被 231 条测试与真实库启动验收覆盖
- 裁定 1–7 **全部认同**，无异议；它另核对了 `roster.py` 的必填集合、`conftest.py` 的真实夹具序列、`normalize_hardness(None)` 的归一
- **Important #1**：全新库路径 `create_all` 与盖章分属两个事务（`db/session.py` 的 `init_db` 全新库分支）。`create_all` 提交后、盖章前崩溃 → 库里留下「表是最新结构、却没有迁移记录」→ 下次启动判存量、盖基线 0 → **P1b-2 首个迁移落地后**会去对一张已有该列的表执行 `ALTER`，永久失败、应用起不来。今天 `MIGRATIONS` 为空故无害，但正是 P1b-2 落地时才咬人。修法：**把盖章挪到 `create_all` 之前**（`create_all` 中途失败则下次启动判存量、pending 为空、补建缺表，自愈）
- Minor #2（备份未做 checkpoint，`-shm` 是瞬时文件）→ 审查者判「不必改」；Minor #3（缺「真实模型表上的 `ALTER TABLE ADD COLUMN` 端到端」测试）→ 只有 P1b-2 落第一个迁移时才写得出。两条**均延后**
- 延后 Minor 分诊：七条全部「可留待后续」，其中 #2 标注「P1b-2 首个迁移落地时必修」、#7（补 docstring）标注「七条里最值得做的」

### 控制方裁定（最终复查的发现）

- Ruling: **Important #1 本轮就修**（不延后给 P1b-2）—— 理由：它是本次唯一被独立审查判为 Important 的实质缺口；修法是两条语句对调 + 一条能判别的回归测试，成本极低；而延后到 P1b-2 意味着它恰好在「作者的库第一次真正跑迁移」时引爆，且是否被记住全靠文档自觉 —— 若判断有误的代价：一次小改动偏离了 spec/plan 里展示的顺序，需同步改 spec（已一并要求）。
- Ruling: 顺带补 `validate_json` / `apply_contract` 的 docstring（延后 Minor #7）—— 理由：同一批改动里的两行，且这两个正是本切片改动的对外接口，下文 P1b-2 要读 — 若判断有误的代价：两行注释冗余。
- Ruling: 其余延后 Minor 与最终复查的 Minor #2 / #3 **park，不在本轮修** —— 理由：#2 审查者自己判「不必改」；#3 只有 P1b-2 写得出；测试内 DRY 与风格项经两位审查者独立判为可延后 — 若判断有误的代价：`_patch_runtime` 第三份副本继续存在，下次重构测试夹具时一并收。
- Ruling: **plan 文档里的顺序展示不改**（spec §3.3 的伪代码改）—— 理由：plan 是本切片的执行工件、已执行完毕；spec 是比它长寿的权威，改错在权威处最要紧 — 若判断有误的代价：读 plan Task 4 代码块的人会看到旧顺序（已在 spec 与 CLAUDE.md 阶段记录两处写明新顺序）。

## 最终修复波

- 修复波：`bca5464` fix(db)（`init_db()` 全新库分支盖章提到 `create_all` 之前 + `schema.py` 两个 docstring + 回归测试）、`52081ff` docs(spec)（§3.3 伪代码同步顺序）
- 修复波：`uv run pytest -q` → **232 passed**（231 + 1）；新增测试**在旧顺序下确认为红**（`duplicate column name: name` → 第二次 `init_db()` 抛 RuntimeError），恢复新顺序后为绿 —— 判别力是跑出来的，不是推断的
- 修复波：**追加裁定**：spec §3.1 的**流程箭头**（`无业务表（全新库） → create_all() → 盖章…`）陈述的是步骤先后，须一并改；上一轮「§3.1 不动」的指示划错了范围（§3.1 的**对照表**讲结果、不动，流程箭头讲顺序、要改） — 若判断有误的代价：一行流程图。
- 修复波：实施者顾虑「回归测试用『重复给 `project` 加 `name` 列』制造必然失败，依赖该列存在」—— **接受，登记为维护注意**：project 表结构若变，这条测试的判别力会钝化。
- 修复波：定向复评进行中

## 修复波复评

- 修复波复评：**All findings addressed, no new Critical/Important breakage**。三条（Important #1、Minor #7、控制方追加的 spec 同步）均落地且有**可判别**证据；复评者独立推演了「盖了章但一张表都没建成」与「盖了章但只建成一部分表」两条自愈路径，均走得通；并确认 spec §1.2 与 §3.1 对照表（讲结果、不动）确实未被改
- 控制方在修复波后独立复跑：`uv run pytest -q` → **232 passed, 1 warning**；`session.py` 的顺序与理由注释已就位
- 修复波复评的残余 **Minor（park）**：`session.py` 与 spec 里「能自愈」的表述缺一个前提 —— **两次启动之间迁移列表未变**。若崩在 `create_all` 中途、下次成功启动前作者升级了应用（`MIGRATIONS` 长出新的改表步骤），新迁移若恰好针对那张尚未建出的表 → `no such table` → 同类永久失败。触发需三重条件同时成立，且**旧顺序在同一场景下必然更早失败**，故非回归、够不上 Important — Ruling: **park，不开第二波修复**（判停规则：一次修复波 + 一次定向复评之后不再开波）；改以「LEGACY 登记」处理 —— 写进归档账本与 `CLAUDE.md` 的阶段记录遗留 — 若判断有误的代价：一句注释少了限定语，读者可能高估自愈的适用范围。
- 修复波复评的范围外观察（同样 park，登记入遗留）：(a) spec §5 测试策略表未收录新的顺序判别用例、§6 任务 4 的措辞「把『迁移之后才 create_all』的顺序钉住」只覆盖存量库路径；(b) 新测试的判别力依赖 `project.name` 列存在，未来改该表结构会静默钝化

## 归档与收尾

- 归档任务：`87232a4` —— 账本按 `*-ledger.md` 惯例归档到 `docs/superpowers/plans/2026-10-16-migration-and-contract-ledger.md`（172 行），`CLAUDE.md` 的指向改对，补三条遗留。**控制方逐字比对过**：副本与源文件只差开头 13 行说明 + 4 处 reviewer ID 清理，正文零改写
- 归档任务审查：**Approved**，无 Critical/Important。审查者独立复核了三条例遗与 `session.py:155-158`、spec `:231-242`/`:255` 的一致性
- 归档任务审查的 **Minor（要修）**：`CLAUDE.md` §7 阶段记录仍写「改后 231 passed」且未交代整支复查与修复波，而新补的三条遗留都以「整支复查后 park」收尾 → 悬空引用 + 数字滞后。**Ruling：补修**（这是交给作者读的那份文档，且是同一批文档收口的收尾），resume 原实施者
- 归档任务审查的另一条 Minor（归档副本首行体例与 p1b1 先例不同）→ **park，不改**（纯体例）

- 归档任务 fix round 1：`c903945` —— §7 阶段记录补一段「收口」，交代整支复查（覆盖分叉点起全部提交）结论为可合并、其 Important 以一次修复波 + 一次定向复评收口、最终 232 passed，并说明为什么多走这一步不亏；231 明确标注为修复波之前的数。三条遗留的「整支复查后 park」现已有出处
- 归档任务 fix round 1 的定向复评进行中

## 分支终态（2026-10-16）

- 分支 `worktree-migration-contract`，**距 master（a17decd）21 个提交**，工作树干净，master 未动
- 完整套件 **232 passed, 1 warning**（那条 warning 是既有的 `StarletteDeprecationWarning`，非本切片引入）
- 全部任务：Task 1–3（追认，评审缺失，由整支复查覆盖）、Task 4、Task 5、Task 6、整支复查、修复波、归档 —— 均已完成且各有审查或复评
- **未做**：合并 master（属需作者点头的动作，留给作者裁决）

- 归档任务 fix round 1 的定向复评：被审的那条 **ADDRESSED**（四项要求全达成、两个数字不再矛盾），但**本轮补记带出一处新 Important** —— `CLAUDE.md:360` 的流程箭头仍是旧顺序（`create_all() → 盖章`），与刚补的 `:376` 相距 16 行自相矛盾；代码与 spec §3.1 都是新顺序，**CLAUDE.md 里这份抄件是唯一漏改的拷贝**（上一轮修复波只改 spec —— 派发范围是我的漏，已在账本留痕）
- 归档任务 fix round 2：resume 原实施者，改 `CLAUDE.md:360` 的流程箭头

- 归档任务 fix round 2：`e117a5b` —— `CLAUDE.md:360` 的流程箭头同步为新顺序。定向复评：**All findings addressed, no new Critical/Important breakage**；复评者另用 grep 扫了 CLAUDE.md 与 spec，确认没有第二份该改而未改的流程箭头抄件
- 归档任务 fix round 3（控制方自查发起的追加）：**计划文档 Task 4 的 Step 3 代码块仍是最先建表、后盖章的旧顺序** —— 复评者只扫了 CLAUDE.md 与 spec 两份，plan 不在其范围，是控制方自己查出来的。**改判上一轮「plan 不动」的裁定**：本仓库对 plan 的既有做法就是让它与实现同步（先例就在这份 plan 自己身上：`0b2ec1e docs(plan): M2 修复` 改的正是 Task 2 的代码块），留一份会被照抄的旧代码块比多一次文档提交的代价大

- 归档任务 fix round 3：`900c02f docs(plan): Task 4 的 init_db 代码块同步为先盖章再建表`（选方案 a：改对代码块 + 加「注意」块讲清为什么不能对调）
- 归档任务 fix round 3 的定向复评：**All findings addressed, no new Critical/Important breakage**。复评者把 plan 的代码块与 `session.py` **逐语句对照**（9 行全一致），确认「照抄即得正确实现」这个唯一验收点成立；并逐步走了一遍注意块里的失败链，与代码事实吻合
- 归档任务 fix round 3 复评的 **Out-of-Scope Observation（park）**：plan `:601` 的 `Produces:` 行「全新库：建表 + 盖 `migrations.latest_version()`」字面读序仍与代码块相反。复评者自陈「严重度低、不阻断」，且明令「不得动这份 plan 的其它部分」— Ruling: **park，按规则处理**（范围外观察不阻断、不延长循环，登记入账本） — 若判断有误的代价：将来有人再扫一遍这份 plan 时会把它当第四处旧顺序重报一次，届时两字对调即可。
- 归档任务：**complete**（commits a9fcbba..900c02f，全部 fix round 的复评通过）

## 切片终态

- 分支 `worktree-migration-contract`，距 master（a17decd）**24 个提交**，工作树干净，master 未动
- 完整套件 **232 passed, 1 warning**（既有 `StarletteDeprecationWarning`，非本切片引入）
- 账本已归档：`docs/superpowers/plans/2026-10-16-migration-and-contract-ledger.md`
- **未做**：合并 master —— 留给作者裁决
