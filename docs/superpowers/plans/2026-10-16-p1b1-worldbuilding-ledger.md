# P1b-1 设定与规则 · 实施过程账本（SDD ledger）

> 2026-10-16 归档。这份文件在实施期间是 subagent 驱动流程的工作区账本，位于
> worktree 内的 git-ignored 目录；worktree 合并前归档到此，以免「裁定」与
> 「延后 Minor」随工作区一起消失。
>
> 内容包括：执行前的冲突扫描表、派发前的全部裁定（Ruling）、每个任务的完成
> 记录与审查发现、以及真实模型复验的结论。**阶段记录见 `CLAUDE.md` §7；
> 设计见 `2026-10-16-p1b1-worldbuilding-design.md`。**

---

Spec: docs/superpowers/specs/2026-10-16-p1b1-worldbuilding-design.md（存在且可读，裁定有权威依据）
Branch: worktree-p1b1-worldbuilding ｜ 14 个任务 ｜ 起点 52cfe6b

（工作区内的 plan 文件比 52cfe6b 多两处派发前的修正，见下方 G1/G2。）

---

## 执行前裁定

Ruling: 在隔离 worktree 里执行，master 保持不动 — 依据本 skill 的「Never start implementation on a main/master branch without explicit consent」，与上一轮 P1a 收口的做法一致 — 代价：若本意是直接在 master 上改，合并时多一步。
Ruling: T8–T12 的「手工走查」不在实施 subagent 内完成 — 前端无自动化测试（Global Constraints 明写「UI 不写自动化测试」），且需要跑着的服务与浏览器 — 代价：UI 验证集中到 T13 由控制方执行，若 UI 有缺陷会在那时才暴露。
Ruling: T13 起服务时**优先只让 `seed_agents` 补上缺失的那张角色卡**，不整库重建 — 本切片只新增一张角色卡，其余角色卡不受影响；整库重建会连 `provider` 与密钥一起清掉（上一轮已证实不必要） — 代价：若角色卡内容陈旧（提示词/契约不含新内容），需回退到定向清理，多一步。

## 派发前冲突扫描

### 共享文件/接口的任务对

| 对 | 共享什么 | 产出 vs 消费 | 发现 |
|---|---|---|---|
| T1 → T2 | `normalize_type` / `normalize_hardness` / `SettingEntry` | T1 产出，T2 消费 | 一致 |
| T1 → T3 | `EntryRelation` | T1 产出，T3 消费 | 一致 |
| T1 → T6 | `ENTRY_TYPES` / `HARDNESS_LEVELS` | T1 产出，T6 消费（写进契约 `title`） | 一致 |
| T2 → T3 | 文件 `world_service.py` | T2 建文件，T3 末尾追加 | 一致 |
| T2 → T4 | 文件 `api/world.py`、`main.py` | T2 建路由并挂载，T4 追加路由 | 一致 |
| T2 → T5 | `world_service.list_entries` | T5 的 `list_terms` 调它 | 一致 |
| T3 → T4 | 文件 `api/world.py`、`schemas.py` | 两任务各自追加，不重叠 | 一致 |
| T6 → T7 | `find_by_task_type("worldbuilding")` | T6 产角色卡，T7 消费 | 一致 |
| T6 → 既有护栏 | `test_roster.py` 的两条跨产物护栏 | T6 新增角色卡 | 一致 — 护栏遍历 `DEFAULT_ROSTER`，自动覆盖新卡（计划已注明） |
| T6 → 既有夹具 | `seed_agents` 落 `trigger_mode` | T6 改 `seed_service.py` | 一致 — 无其它任务改该文件 |
| T7 → T11 | `api.suggestEntries` | T7 产出，T11 消费 | 一致 |
| T8 → T9/T10/T11/T12 | 接口封装与类型 | T8 产出，四个前端任务消费 | 一致 |
| T9 → T10/T11 | `EntryEditor` / `EntryDraft` / `EMPTY_DRAFT` / `splitList` / `joinList` | T9 产出，T10 与 T11 消费 | 一致 |
| T10 → T11 | 文件 `World.tsx` | T10 建，T11 改 | 一致 — T11 在 T10 的骨架上加候选区与 `refresh()` |
| T10 → T12 | 文件 `App.tsx` | 两任务各加一项导航与路由 | 一致 |
| T13 ↔ T14 | 文件 `CLAUDE.md` §7 | 两者都要写 §7 | **G2** — 见下 |

### 每个任务的自洽性

| Task | 检查项 | 发现 |
|---|---|---|
| T1 | 测试 vs 模型定义；`__init__.py` 注册 | 一致 |
| T2 | 测试 vs 服务签名；`_ENTRY_FIELDS` 与归一化的分工 | 一致（写作期已把 `type` 从常量里拿出来单独处理） |
| T3 | 测试 vs 服务签名；跨项目条目的拒绝 | 一致 |
| T4 | **新测试文件能否拿到 `client` 夹具** | **G1** — 见下 |
| T5 | 投影字段与前端 `TermRow` 类型 | 一致 |
| T6 | 契约 `title` 里带类型清单 → 说明块能讲到八类；`seed_agents` 落 `trigger_mode` | 一致（`seed_agents` 确实没传 `trigger_mode`，计划已改成确定语句） |
| T7 | `_patch_runtime` 的 lambda 参数个数（`self, timeout`） | 一致 — 上一轮 P1a 改过 `_resolve_client` 签名，计划里的 lambda 是双参 |
| T8 | 类型与接口名 | 一致 |
| T9 | 组件 props vs T10/T11 的用法 | 一致 |
| T10 | 用到的接口都在 T8 里；空态与手工路径 | 一致 |
| T11 | `busy` prop 传入的值；`splitList` 的使用 | 一致（写作期已把死值 `false` 改成 `suggesting`、把未用的导入删掉） |
| T12 | `TermRow` 字段 vs T5 的投影 | 一致 |
| T13 | 步骤与前置；与 T14 的分工 | **G2** — 见下（已修） |
| T14 | 只改路线图与 §8 | 一致 |

### G1 / G2 的裁定

Ruling: **G1** —— `client` 夹具目前只定义在 `backend/tests/test_api.py:13-32`，而 **pytest 的夹具不跨测试模块共享**；T4 新建的 `test_world_api.py` 直接用它只会在收集期报 `fixture 'client' not found`，Task 4 会当场卡住。已把「把该夹具连同所需导入搬进 `conftest.py`，并删掉 `test_api.py` 里的原件与因此不再使用的导入」写进计划的 T4 Step 1，并在搬完后加了一次全量回归。— 依据：夹具的共享位置是 pytest 的机制问题，不是取舍 — 代价：改动落在一个多文件共享的测试文件上；若搬错，`test_api.py` 的既有用例会立刻变红，兜得住。

Ruling: **G2** —— T13 Step 3 与 T14 Step 1 都要改 `CLAUDE.md` §7 的路线图表，会互相覆盖。已改成：**T13 只写 §7 的新阶段记录，路线图表与 §8 变更记录归 T14**。— 依据：同一张表不该由两个任务各改一半 — 代价：无。

扫描结论：除 G1/G2 外无其它冲突，两处均已在派发前修入计划文本。

---

## 进度

Task 1: complete (commits b0e4e23..e6b7bef, review clean)
Task 1: minor (deferred): `test_setting_entry_defaults_and_roundtrip` 名为 roundtrip 实读身份映射对象（`session.py` 配了 `expire_on_commit=False`），补一行 `session.expire_all()` 才名副其实；当前不产生假过
Task 1: minor (deferred): `description` 与 `note` 的 `default=""` 无断言（`summary` 有），覆盖略不齐
Task 1: minor (deferred): JSON 列（`aliases_json` / `tags_json`）未用 `MutableList`，原地改列表不会被追踪 —— 本 diff 内无此路径，**T2/T3 的 CRUD 要留意**（计划的 T2 用整列赋值，本就不踩）
Task 1: minor (deferred): `from sqlalchemy.types import JSON` 与 `app.db.base` 的导入分组不顺（I001），plan-mandated，留待整支复查统一修
Task 1: minor (deferred): `normalize_type` 的报错只列中文标签、不列英文键，模型返回 `"location"` 这类值时对照成本偏高；待 T6 接入时再定

Ruling: T2 的实施者报了两处**测试与实现互相矛盾**（我没有跑过这对组合），两处都属实，裁定如下。
  (1) **`aliases`/`tags` 的参数名** —— 改实现：**服务层说领域名（`aliases`/`tags`），`_json` 后缀是存储细节不往上传**。依据是仓里既有约定：`idea_service.create_idea(session, project_id, raw_text, tags)` 收领域名而模型列是 `tags_json`。原计划让 API 层做重命名，与既有约定相反，是我写反了。实施者的测试写法是对的，不改。
  (2) **`hardness`** —— 改测试：spec §2.1 明写「仅 `rule` 有值」，那是不变量，实现（非规则类一律置 None）正确。是我那条 `test_type_change_re_normalizes` 写错了 —— 拿 faction 去断言 `hardness == "soft"`，与不变量冲突。改成用 rule 类型，并补一条 update 路径的断言（规则改成势力后硬度被清掉）。
  — 依据：spec 是约束权威；既有代码约定优先于我的新写法 — 代价：(1) 若既有约定其实不是这样，服务层的公开词汇会与 `idea_service` 不一致 —— 但那条既有代码是可核对的既成事实，风险很低。

Task 2: fix round 1/5 (2 addressed, 0 open —— ① `update_entry` 补空白名守卫；② 重名报错改用提交前取出的名字。commits ced7362..ad5c7ad)
Task 2: complete (commits a0c8a46..ad5c7ad, review clean)
Task 2: minor (deferred): 唯一约束的 `IntegrityError` 被无限定地当成「重名」—— 外键违规（不存在的 project_id）会被报成「已经有叫 X 的条目了」，诊断与事实相反（需前端传失效 id，故判 Minor）
Task 2: minor (deferred): 没有测试钉住「update 不改未传字段」（代码对，无断言）
Task 2: minor (deferred): `EntryRelation` 在 `world_service.py` 里导入未使用（T3 会用，判定可接受）
Task 2: minor (deferred): 未知 id 在 PATCH 上是 400、在 DELETE 上是 404（同一条件两种状态码）；`PATCH/DELETE /api/entries/{id}` 不带 project 作用域（plan-mandated，单机单人可忽略）
Task 2: minor (deferred): `list_entries` 的排序依赖 `created_at` 的微秒精度（表无自增列，当前模型下是可用选择）

Task 3: complete (commits 05e1f16..cb514f5, review clean)
Task 3: minor (deferred): 「存储 trim 后的 kind」无测试覆盖（`kind=" 位于 "` 的路径无人验证）
Task 3: minor (deferred): 跨项目用例的两个场景在同一函数里都只断言异常类型，失败时报不出是哪条分支断的
Task 3: minor (deferred): `list_relations` 仅按 `created_at` 排序、无次级排序键
Task 3: minor (deferred): 路由用 `**payload.model_dump()` 展开，schema 加字段会在运行期变成 TypeError（brief 指定写法）

Task 4: complete (commits cb514f5..4424138, review clean)
Task 4: minor (deferred): `test_api.py:2` 的 `import pytest` 已无引用（plan-mandated：我的计划说留着，理由「还有 monkeypatch 用例」不成立 —— monkeypatch 是夹具参数）
Task 4: minor (deferred): conftest 的新增导入放在文件末尾，与既有约定不一致（但顶部先设 `STORYFORGE_DATA_DIR` 再导 `app.*` 是硬约束，位置有其道理）
Task 4: minor (deferred): `client` 夹具不清理数据，新增 5 个用例会向共享库留行（当前安全：收集顺序 + 每用例自建项目）

Task 5: complete (commits 4424138..fccfdd1, review clean)
Task 5: minor (deferred): 条目内重复别名会产生完全相同的两行（`entry_id` 与 `form` 都同）—— 根在录入层未对别名 strip/去重；前端若按 `entry_id + form` 作 key 会撞键
Task 5: minor (deferred): 别名两侧空白原样带进 `form`，故 `" 记忆交易局"` 不会被判为与名字相同、会多一行

**★ 给 P2 的契约备注（由 T5 审查提出，勿丢）**：同一个 `form`（表面形式）**可以来自两个不同条目** —— 例如 A 的别名等于 B 的名字，或两条目用了同一个别名。投影两行都保留（信息完整，`entry_id` 不同故前端不撞键），**但没有任何「此形式歧义」的信号**。P2 的连续性检查若按表面形式建白名单查找表（`{t["form"]: t}` 那种写法），会静默丢掉一行。届时须规定：**同一 `form` 可多行，取值须优先 `is_primary`**。

Task 6: complete (commits fccfdd1..3fec84d, review clean)
Task 6: minor (deferred): 同一文件里出现了第二份八类清单（提示词 `roster.py:157` 硬写中文八类，而标题是从词表派生的）；护栏只查英文键，改 `ENTRY_TYPES` 时提示词会静默过期
Task 6: minor (deferred): 三个硬度名与 `minItems == 3` 无测试兜住（审查者手工渲染确认行为正确，仅覆盖缺口）
Task 6: minor (deferred): `test_roster.py` 的「六项必备字段」测试不断言 `trigger_mode`，将来某张卡漏写会静默落 `manual`
Task 6: minor (deferred): 一处测试 docstring 说法不准确（称模型只可能从契约块知道类型，而提示词本身也列了八类）

**★ T13 必看的观察点（T6 审查提出）**：提示词让模型「其余类别的硬度留空」，而模型很可能落成 `"hardness": null`；`schema.py` 对「存在的键」一律按类型严检（`null` 不是 `string`），**一个 null 会让整份 payload 校验失败、降级纯文本，作者拿不到任何候选**。这是 P1a 校验层既有行为（解析师同样暴露），非本切片引入。注意：**提示词里不能写 "null"** —— 会被「禁英文字段键」的护栏拦下。Ruling：不改，留到 T13 用真实模型看它是否真会发作；真发作再改校验器（改动会波及三个智能体，需要自己的审查）。

Task 7: fix round 1/5 — 待验（① `_reason` 的 template 分支补上缺失变量名；② 「跑一次不写库」先断言真的产出了候选）

Task 7: fix round 1/5 (2 addressed, 0 open —— ① template 分支附缺失变量名；② 不写库测试先断言成功。commits ad9cc0c..29af9f7)
Task 7: complete (commits 3fec84d..29af9f7, review clean)
Task 7: minor (deferred): `_seed_slots` 直插 `Architecture` 对「采纳才进故事圣经」这条产品规则的测试代表性（槽位源当前不校验采纳状态，故可观察状态不可区分）
Task 7: minor (deferred): 追加的「（运行记录里说缺的是：…）」子句无断言覆盖（现有断言只查指引正文里的「灵感」「架构」子串）
Task 7: minor (deferred): 文案里出现嵌套冒号「说缺的是：提示词引用了未提供的变量：…」，略拗口
Task 7: minor (deferred): `_reason` 的 template 分支硬编码了本智能体的前置条件，多智能体复用时需提取（实施者自陈）

Task 8: complete (commits 29af9f7..76bcb55, review clean)
Task 8: minor (deferred): `aliases`/`tags` 标非空 `string[]`，而 `_entry_out` 原样透传不做兜底（当前不可达：列有 `default=list`）—— 若库里有历史 NULL 行，界面会拿到 null 而类型不报警
Task 8: minor (deferred): `SuggestedEntry` 的 `type`/`name`/`summary` 标为可选，而契约把它们列为必填；方向保守，但 T11 不该假定它们一定存在

Task 9: complete (commits 76bcb55..21247bc, review clean)
Task 9: minor (deferred): `EMPTY_DRAFT.type` 硬编码 `'place'`，与后端词表耦合（已核实 `place` 存在，风险理论性；若后端删掉它，下拉会显示空白而 `draft.type` 仍是 `'place'`）
Task 9: minor (deferred): 类型从 `rule` 改走后草稿里的 `hardness` 残留（后端 `type != "rule"` 时一律置 None，不会污染落库；调用方无需清理）

Task 10: fix round 1/5 — 待验（① `typeLabel` 的映射合并硬度词表；② 无项目时的空态改说要先建项目）

Task 10: fix round 1/5 (2 addressed, 0 open —— ① 词表映射合并硬度；② 无项目空态改指仪表盘。commits d08d08c..10069e6)
Task 10: complete (commits 21247bc..10069e6, review clean)
Task 10: minor (deferred): 首屏 `listEntryTypes`/`listProjects` 无 `.catch`，后端不可达时静默停在空态
Task 10: minor (deferred): 切项目的两个 `listEntries` 请求可乱序返回，且切换瞬间不清 `entries`/`relations`，旧树短暂残留
Task 10: minor (deferred): 成功与失败共用同一条 `notice`，样式与语义不区分；`refresh()` 在 save 的 try 内，保存成功但重拉失败时提示指向另一件事
Task 10: minor (deferred): `selectEntry` 对已选中项也重新播种 draft，点一下正在编辑的名字即丢弃未保存改动

Task 11: fix round 1/5 — 待验（三条 Important 见下）

Task 11: fix round 1/5 (3 addressed, 0 open —— ① 换项目清候选 ② 展开态按稳定 key ③ 采纳失败不丢编辑。commits 6bd58a6..ace735c)
Task 11: fix round 2/5 — 待验（在途 suggestEntries 与换项目的竞态，见下）

Task 11: fix round 2/5 (1 addressed, 0 open —— 令牌作废在途候选请求。commits ace735c..245168d)
Task 11: complete (commits 10069e6..245168d, review clean)
Task 11: minor (deferred): `openQuestions.map` 用问题文本作 React key，重复文本会触发控制台警告
Task 11: minor (deferred): 采纳期间无 in-flight 锁（唯一约束会挡住重复，真实代价只是一句误导性提示）
Task 11: minor (deferred): `listEntries`/`listRelations` 无令牌守卫，同类竞态（症状是左树而非候选）；窗口为毫秒级（本地 SQLite），与 suggest 的 100 秒不可比
Task 11: minor (deferred): `adoptCandidate`/`refresh` 未纳入令牌，采纳期间切项目会往旧项目 refresh 回 `entries`（窗口窄：候选在切项目时已清空）

Task 12: fix round 1/5 — 待验（① 空态区分「无匹配」与「无术语」；② 术语行 key 加行号）

Task 12: fix round 1/5 (2 addressed, 0 open —— ① 空态按关键字分支；② 行 key 带行号。commits 17722bf..17159d3)
Task 12: complete (commits 245168d..17159d3, review clean)
Task 12: minor (deferred): 首屏无加载门，空态文案会在数据到达前先画出（一个项目都没有时该句持续为错误指示）
Task 12: minor (deferred): 两个首屏请求（`listEntryTypes`/`listProjects`）无 `.catch`，失败静默，作者反而被告诉「去建几条设定」
Task 12: minor (deferred): `notice` 不随项目切换清理，旧错误残留在页顶
Task 12: minor (deferred): 切项目的 `listTerms` 竞态（同类，窗口毫秒级）
Task 12: minor (deferred): 库空 + 已输入关键字时，空态说「没有匹配「xxx」」而非「还没有术语」（措辞可打磨）

Task 13: complete（真实模型复验，九步全过；1 次调用 `qwen3.8-flash`，1153 + 7375 tokens，116.2s，状态 ok，$0）
  证据：8 条候选覆盖全部八类、每条都引用解析卡/故事圣经的具体要素；14 条 open_questions 单列；契约块把八个类型与三档硬度都送到模型；改后采纳落库的是**作者改过的名字**；三条 AI 采纳都带 `source_run_id`，手工那条为 None；关联与术语投影（32 行 = 4 名字 + 28 别名）与界面一致；`type=rule/hardness=hard` 落库正确。
  未发作：T6 审查警告的 `null` 硬度风险（模型对非规则类给的是空串）。
  **发现一条 Important**：见 Task 15。

Ruling: T13 发现的缺陷 —— 模型按契约块里教它的**中文值**返回 `type`（「规则体系」）与 `hardness`（「硬规则」），而前端 `CandidateList.draftOf` 把标签原样放进 `EntryDraft.type`，与英文键的下拉对不上：类型回落到显示第一个选项（一条规则显示成「地理」），且规则类的硬度控件（条件 `draft.type === 'rule'`）**根本不出现**。**数据层是对的**（已核实 `type=rule`、`hardness=hard`），缺陷纯在边界。
  **判定为 Important、追加为 Task 15 修**。修法取「在后端响应里归一一次」而非「前端再抄一份映射」—— 因为前者的映射是纯逻辑、能被 pytest 覆盖，而后者落在「UI 不写自动化测试」的盲区里。— 依据：它让作者看到错的类型、且够不到本切片最强调的那个字段 — 代价：改动落在 `api/world.py`（呈现层投影，不越「api 不写业务逻辑」的线，与同文件既有 `_reason` 同性质）。

Task 15: complete（commits 17159d3..5dfaa19，review clean）
Task 15: fix round 1/5 (1 addressed, 0 open —— 候选行类型标记映射回中文。commits 5dfaa19..fcc3575)
Task 15: complete (commits 17159d3..fcc3575, review clean)
Task 15: minor (deferred): `hardness` 的归一缺非字符串防护（`type` 有 `str(...)` 兜住），当前被契约校验挡在 `structured=False` 一侧，不可达
Task 15: minor (deferred): 「运行记录原样」这一半靠浅拷贝保证，无测试钉住
Task 15: minor (deferred): 非 dict 候选被静默丢弃（与「不因一条怪条目拖垮整批」略有张力；同被契约挡住）
Task 15: minor (deferred): `World.tsx` 的 `api.listEntryTypes()` 无 `.catch`，失败时 `types` 恒为 null，候选行与类型下拉都会退化

Ruling: T15 审查抓到的**回归** —— 归一化让候选行的类型标记从中文（模型原值「势力」）变成了英文键（`faction`），是这次改动自己引入的、可见的、违反「界面文案用中文」的问题。前端文件不属 Task 15 的契约范围，故审查者只判 Minor；**我持有跨任务上下文**（那个组件是 T11 的、`types` 早已作为 prop 传入，一行即可修），判为真回归、**进修复第 1 轮**。其余 Minor（`hardness` 缺非字符串防护且当前被契约校验挡住、「运行记录原样」无测试钉住、非 dict 候选被静默丢弃）判可延后。— 依据：自己引入的回归该自己收 — 代价：改动落在 T11 的文件上，跨了任务的边界，但一行且由我指派。

**实现阶段结束**：12 个实施任务全部通过任务级审查，其中 6 个走了修复循环（T2/T7/T10/T11×2/T12），共 5 轮修复 + 5 次范围复验。

Ruling: T12 审查的 Important（空态把过滤后的空当成库里的空，作者搜不到就被告诉「还没有术语」并可能去重录已有条目）—— **判定为真缺陷、进修复第 1 轮**，与 T10 那条同类（给作者的话是错的）。
Ruling: 另把一条 Minor 同批修 —— **同一条目里的重复别名让行 key 撞键**（`entry_id + form`；录入层不去重，写「阿明、阿明」即可复现）。本页无逐行状态，加行号即可解决。**根因（录入层不做 strip/去重、后端投影不做条目内去重）不动**，与 T5 审查当初把该根因判为可延后一致。— 依据：撞键点落在本页、属本页自身代码；根因跨层且已被裁定延后 — 代价：一行 map 参数 + key 改动。
Ruling: 其余 Minor（首屏无加载门、两个首屏请求无 `.catch`、`notice` 不随项目切换清理、切项目竞态）**判可延后**。— 依据：与前几任务同类，留给最终复查分诊 — 代价：无。

Ruling: T11 修复后的 re-review 查出一条**同型残留**：项目下拉在 `suggesting` 期间未禁用，在途请求若在切项目后返回，会把 A 的候选写回 B —— 与刚修掉的 Finding 1 是同一症状，只是走竞态路径。re-reviewer 按指令（只审 fix diff）把它划出范围，但我持有跨任务上下文：**让 Finding 1 成为 Important 的那条论证（真模型下单次 100 秒以上，等待期间切项目是常态）对这条路同样成立** → 判为真缺陷，**进第 2 轮**，用与上一轮架构页同款的令牌修法。— 依据：同症状同触发条件，只修静态路径等于没修完整 — 代价：改动小（一个 ref + 三处守卫），但要再复验一轮。

Ruling: T11 实施者删掉 `SuggestedEntry` 导入 —— **判定必要且正确**：候选改成 `CandidateRow[]` 后它零引用，而 `noUnusedLocals: true` 会让构建失败；brief 的注记是上一版代码的残留。— 代价：无。

Ruling: T11 审查的三条 Important —— 全部判定为真缺陷，**进修复第 1 轮**。
  (1) **换项目不清候选**：A 的候选可写进 B，`source_run_id` 指向 A 的运行（无外键裸字符串，后端不拦），D-03 的可追溯变成悬空引用。实施者称「brief 未要求」—— 审查者驳回，理由成立：该页既有的重置约定本就要求项目作用域状态整体换掉。
  (2) **展开态与草稿按 index 定位**（实施者未报、审查者查出）：丢弃上方一行或再点「让 AI 提候选」都会让草稿漂到别的候选上，采纳提交的是作者没在改的那条、`source_run_id` 还对不上。**直接打在「AI 提议、作者裁决」上**。修法取审查者给的第一方案（按稳定 key 记）而非第二方案（一律复位）—— 后者会在丢弃其他行时丢掉作者正在改的内容。
  (3) **采纳失败时展开区收起、编辑全丢**：失败恰常发生在「撞名的候选改名后仍然撞名」，是功能的中心场景。
  另**控制方加派一行**：`suggest` 的 `未结构化：${parse_error}` 去掉前缀 —— T7 已保证未结构化时必有可读原因，而那原因可能根本**不是格式问题**（如「上游还没做」），套前缀会自相矛盾。
  未采纳两条 Minor（`openQuestions` 用文本作 key、采纳期无 in-flight 锁）—— 判可延后。
  — 依据：三条都是作者会撞到且与产品立场冲突的行为 — 代价：改动跨两个文件，审查面略大。

Ruling: T10 审查的 Important（左树把硬度词表的英文键当标签显示 —— `types.types` 与 `types.hardness` 是**两份**词表，而 `typeLabel` 只合了前者）—— **判定为真缺陷、进修复第 1 轮**。它违反「界面文案用中文」这条硬约束，作者建第一条规则条目就会看到；代码出自我计划、实施者逐字转写无过。另有一条 Minor（无项目时空态叫作者点一个被禁用的按钮，指示是错的、新装首屏撞上即死胡同）**同批修** —— 与 Important 同属「给作者的话是错的」。其余 Minor（首屏无 catch、切项目竞态、成功失败共用 notice、重复选中即丢未保存改动等）**判可延后**。— 依据：新代码里「给作者错指示」的缺陷该修；健壮性问题留给最终复查分诊 — 代价：多一次修复 + 复验。

Ruling: T9 审查指出 brief 的散文与代码块不一致（散文写 `<EntryEditor value draft onChange types />`，代码块只有 `draft / types / onChange`）—— **判定代码块为准，不是缺口**；T10/T11 都按代码块消费，无歧义。另一处「Consumes 提到 `SettingEntry` 而代码未导入」经核实是为规避 `noUnusedLocals`，实施者取舍正确。— 依据：brief 的代码块是权威，散文只是概述 — 代价：无。

Ruling: T7 审查的两条 Minor —— 均判定同批修掉（各一行，且落在本次已动过的两个文件里）。
  (1) `template` 失败**不只**发生在「上游没做」，也发生在作者自己把提示词改坏时（D-03 允许改提示词），而我的分支把那句指引说死了、还丢掉了运行时给出的缺失变量名 —— **这打在 `_reason` 自己的存在理由上**（它就是为了避免误导），属新代码里的真缺陷，不是风格问题。
  (2) 「跑一次不写库」不断言 `structured is True`，静默降级时也会通过，变成在断言「失败也不写库」。
  另一条（`_seed_slots` 直插 `Architecture` 不代表「已采纳」这条产品规则的测试代表性）**判可延后**：需要判断而非一行改动，且槽位源当前不校验采纳状态。
  — 依据：新代码里「使自身目的落空」的缺陷该修；测试诊断力与代表性观察留给最终复查分诊 — 代价：多一次修复 + 一次范围复验。

Ruling: T7 实施者报了两处**我的计划写错**的地方，都属实，都改了计划。
  (1) **槽位前置条件缺失** —— 世界观构建师的提示词引用 `{{ parsed_idea }}` 与 `{{ story_bible }}`，而我的测试拿空项目直接跑：槽位取不到值 → `build_context` 丢掉 → `render` 抛 `MissingVariableError` → 整个 run 变 `template` 错误。修法：测试内加 `_seed_slots(project_id)` 补一条已解析的 `Idea` 与一条 `Architecture`（与 `client` 夹具补服务商/补模型绑定同一条路子）。**方案 B（走真实 HTTP 流）不可行**：`_patch_runtime` 对所有调用返回同一份候选 JSON，解析那步会因契约不符而失败，`parsed_json` 写不进去。
  (2) **`minItems: 3` 而我给的候选只有 2 条** —— 契约校验必败。修法：候选加到 3 条。
  — 依据：两处都是我写测试时没跑过与 T6 契约/SlotSource 的组合 — 代价：无（测试夹具，改起来便宜）。

Ruling: T7 实施者提出的**产品问题** —— 空项目上这个接口返回技术性错误 run，而前端会显示成「未结构化：模型没按契约返回」，**但模型根本没被调用**。判定**在 T7 的路由里加一层翻译**（不是留给 T10/T11）：给 `template` 失败一句作者能照做的中文（去解析灵感、去采纳架构），其余失败透出运行记录里的原始原因。依据：项目自己的验收标准里就有「未配置服务商时给出可读中文原因而非 500」，同一原则；一句假话会把作者引向错误的排查方向。**连带**：这让 T11 的 `parse_error ?? 兜底` 写法不再需要额外改动 —— 路由保证未结构化时必有一句可读原因。— 代价：路由多了一个十来行的展示层函数，属「api 不写业务逻辑」之外的呈现映射，可接受。

Ruling: T4 实施者发现**我计划里的 `client` 夹具片段漏了「绑定模型」的前置条件循环**（上一轮 P1a 收口补的），照抄会打挂 5 条既有测试；它按「忠实搬家」处理并给出证据。**判定其读法正确、结果忠实**（审查者已独立核对 `runtime_service.py:80-84` 确认未绑模型必抛错，且 diff 里两段循环逐字一致）。我已把该片段与导入清单改入计划。— 依据：搬家的语义是「保持行为不变」，而非「逐字照抄我抄错的快照」 — 代价：无。

Ruling: T3 审查留的 ⚠️「自关联（`from_id == to_id`）与重复关联的语义 brief 未裁决」—— **判定不是 spec 缺口、不入修复循环**。依据：spec 与计划都没有这两条要求；界面上目标条目的下拉**排除了源条目自身**，自关联从 UI 不可达；重复边只是冗余行、作者可删。真正的语义裁决时点在 P1b-2 —— 那张表就是为关系网复用的，人物之间的自环与重边该不该存在到那时才有答案。— 依据：无要求即无缺口；不为未定语义提前加约束 — 代价：若作者绕过界面用接口建自关联，会得到一条无意义的边，但看得出来、删得掉。

Ruling: T2 修复波里实施者主动做了一处偏离 —— 在我给的空白名守卫片段上加了 `session.rollback()` 再抛。**判定必要、正确、予以接受**：`_apply_entry_fields` 已经改脏持久对象，不回滚则身份映射里留着非法值（我自己那条测试会因此变红），且与同函数既有的 `IntegrityError` 处理同形。`create_entry` 不需要它是**正当差异**（守卫在 `session.add` 之前，对象还是 transient）。已同步进计划。— 依据：我给的片段本身不一致 — 代价：无（已由独立复验确认）。

Ruling: T2 审查的 Important（`update_entry` 缺空白名守卫，审查者实跑确认 `PATCH name="  "` 能写出空白条目）—— 判定为真缺陷，**进修复循环第 1 轮**。与 create 不对称，而 `EntryUpdate` 的 `min_length=1` 只挡空串 —— 依据：同一聚合的两条写路径该守同样的不变量 — 代价：一行守卫 + 一条测试。
Ruling: 我另外把一条 Minor 与它同批修掉：**update 撞重名时报的是旧名字**（`rollback()` 后实例 expire，`entry.name` 读回改动前的值；审查者实跑得到「已经有叫乙的条目了」而乙正是被编辑的那条）。超出审查发现的范围，但要改的两个函数本就在本次派发内，且这是**诊断结论与事实相反**而非文案风格问题 — 依据：误导的错误信息会把作者引向错误的方向，与本切片「接线正确」的目标同类 — 代价：多了两条测试；该 Minor 已在派发里显式标注为「控制方加派」。

Ruling: 审查者点名 T2/T3 会踩「JSON 列无 MutableList」，但计划里的 CRUD 用的是整列 `setattr`，不存在原地修改路径 —— 判定**无需改计划**，仅作提示带进 T2 的派发。— 依据：计划文本已避开该模式 — 代价：若实施者自作主张改成 `append`，会在 T2 的审查里被抓到。

