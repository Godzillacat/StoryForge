# P1a 收口 · 实施过程账本（SDD ledger）

> 2026-10-16 归档。这份文件在实施期间是 subagent 驱动流程的工作区账本，位于
> worktree 内的 git-ignored 目录；worktree 合并后归档到此，以免「裁定」与
> 「延后 Minor」随工作区一起消失。
>
> 内容包括：执行前的冲突扫描表、派发前的全部裁定（Ruling）、每个任务的完成
> 记录与审查发现、以及整支复查的延后事项分诊。**实施记录与最终结论见
> `CLAUDE.md` §7；设计见 `2026-10-14-p1a-hardening-design.md`。**

---

Spec: docs/superpowers/specs/2026-10-14-p1a-hardening-design.md（存在且可读，裁定有权威依据）
Branch: worktree-p1a-hardening ｜ 基线提交: 2f773f2 ｜ 12 个任务

---

## 执行前裁定

Ruling: 在隔离 worktree 里执行，master 保持不动 — 依据本 skill 的「Never start implementation on a main/master branch without explicit consent」，且项目自身的 P1a 也是 worktree → merge 的做法 — 代价：若本意是直接在 master 上改，合并时多一步。
Ruling: T12 重建开发库用**改名备份**而非删除 — 与本次会话早先处理 stale 库的先例一致；开发库里有走查数据 — 代价：`%LOCALAPPDATA%\StoryForge\` 会多一个备份文件。
Ruling: T9/T10/T11 的「手工走查」步骤不在实施 subagent 内完成 — 前端无自动化测试（Global Constraints 明写「UI 不写自动化测试」），且需要跑着的服务与浏览器 — 代价：这三步的 UI 验证集中到 T12 由控制方执行，若 UI 有缺陷会在那时才暴露。

## 派发前冲突扫描

### 共享文件/接口的任务对

| 对 | 共享什么 | 产出 vs 消费 | 发现 |
|---|---|---|---|
| T1 → T2 | 接口 `describe_contract` | T1 产出 `describe_contract(schema)->str`；T2 追加到 prompt | 一致 |
| T1 → T3 | 接口 `describe_contract` | T3 的测试消费它做一致性断言 | 一致 |
| T2 → T3 | 无（不同文件） | T3 删掉提示词里的字段清单，可读性依赖 T2 的契约块 | 一致，但 T3 必须在 T2 之后（顺序正确） |
| T2 → 既有测试 | `rendered_prompt` 等值断言 | T2 让 rendered_prompt 多出契约块 | **冲突 F2** — 见下 |
| T3 → 既有 `test_roster.py` | 提示词文本 | T3 重写两段提示词；旧测试断言含「不替作者决定」「编造」 | 一致 — 新提示词保留了这两处词 |
| T4 → 既有 `test_api.py:177` | 接口 `_resolve_client` | T4 把签名改成 `(self, timeout)`；该处打成单参 lambda | **冲突 F1** — 见下 |
| T5 → T6 | 文件 `agent_service.py` | T5 重写 `create_version`；T6 末尾追加 `update_agent` | 一致 — 不同区域，先后顺序正确 |
| T6 → T7 | 文件 `api/schemas.py` | T6 追加 `AgentUpdate`；T7 追加 `ProviderTest` | 一致 — 各自追加，不重叠 |
| T6 → T9 | `PATCH /api/agents/{id}`、`GET /api/slots` | T6 产出；T9 消费 | 一致 |
| T7 → T11 | `POST /api/providers/{id}/test` 带 body | T7 产出；T11 消费 | 一致 |
| T8 → T9 | `api.updateAgent` / `api.listSlots` / `SlotSpec` | T8 产出；T9 消费 | 一致 |
| T8 → T11 | `api.updateProvider` / `deleteProvider` / `testProvider` / `Settings.request_timeout_seconds` | T8 产出；T11 消费 | 一致 |
| T5 → 既有 `test_api.py:100` | `create_version` 继承语义 | T5 改继承源；该测试只断言 version_no 递增与回滚生效 | 一致 — 不受影响 |
| T9/T10/T11 → 测试策略 | 前端 | 计划给的验证是 `pnpm build` + 手工走查 | 见裁定 R3 |
| T12 → 工作区之外 | 开发库目录 | T12 重建 `storyforge.db` | 见裁定 R2 |

### 每个任务的自洽性

| Task | 检查项 | 发现 |
|---|---|---|
| T1 | 测试断言 vs 生成逻辑；缩进 | 一致（depth=1 → `"  " * 1` = 两格，与断言相符） |
| T2 | 测试 vs 实现；被打破的既有测试 | **F2**，已在计划中修正 |
| T3 | `title` 覆盖全 property；提示词不含 snake_case；跨产物测试 | 一致 |
| T4 | 测试 vs 实现；`_resolve_client` 的全部调用点 | **F1**，已在计划中修正 |
| T5 | `_make_agent` 造的 v1 与 v3 继承断言 | 一致 |
| T6 | 夹具选择（只用 `client`） | 一致（原稿的 `client, session` 已在写作期修正） |
| T7 | 假传输层的 patch 手法 vs 顶层导入 | 一致（patch `provider_service.HttpxChatClient` 模块属性有效） |
| T8 | 步骤 vs 文件 | 一致（纯接口与类型） |
| T9 | 代码 vs T8 提供的接口 | 一致 |
| T10 | 代码 vs 依赖 | 一致（不新增后端接口） |
| T11 | 代码 vs 依赖 | 一致（`PUT /api/settings` 已存在） |
| T12 | 步骤 vs 前置 | 一致（依赖前 11 个任务） |

### F1 / F2 的裁定

Ruling: F1（`test_api.py:177` 的 `lambda self: fake` 会因 T4 改签名而抛 `TypeError`，打挂 5 条既有测试）— 已把「改为 `lambda self, timeout: fake`」写进计划的 T4 — 依据：这是计划缺陷（T4 只列了两个测试文件，漏了这处补丁），不是 T4 的设计问题 — 代价：若裁定有误，多改一行无害。
Ruling: F2（`test_runtime_service.py:60` 与 `test_execute.py:95` 是同一条等值断言分居两文件，计划只提了后者）— 已把两处一并写进计划的 T2 — 依据：同 F1，属计划遗漏 — 代价：同上。

扫描结论：除 F1/F2 外无其它冲突，两处均已在派发前修入计划文本。

---

## 进度

Task 1: complete (commits cb500b2..d7bb41d, review clean)
Task 1: minor (deferred): 顶层字段被缩进两格（`contract.py:26` 传 depth=1），与 brief 示例的 col-0 不符；brief 的断言全用 `in`，`"- genre…"` 是 `"  - genre…"` 的子串，故测试结构上抓不到。仅提示词装饰，无功能影响
Task 1: minor (deferred): 直接嵌套的对象属性（非数组）无专门测试 —— Task 3 的 ARCHITECTURE_SCHEMA 含 `story_bible_v0`，其跨产物测试会覆盖该分支
Task 1: minor (deferred): `_type_label` 对无 type 的节点回落「值」、`minItems: 0` 被丢弃，均无害且未测

Task 2: complete (commits d7bb41d..c2c5a3b, review clean)
Task 2: minor (deferred): 契约块未计入 `build_context` 的预算核算，`trimmed` 与超预算报告不反映发送提示里的这段文本（行为本身正确——该块不该被裁剪），仅调试台的预算显示会低估
Task 2: minor (deferred): `ChatFailure` 路径携带契约块这一行为无测试锁定，仅靠检视成立

Ruling: 实施者发现计划的 T2 `git add` 行漏列了 `backend/tests/test_runtime_service.py`（照原样提交会交出红树）。据此排查了全部 12 条 `git add`，又发现 T4 的行漏列 `backend/tests/test_api.py`（由我自己的修正引入）。两行均已改入计划。— 依据：计划缺陷，非实施问题 — 代价：若排查有漏，后续任务仍可能出现「提交后套件变红」，届时有测试兜底。

Task 3: minor (deferred): `test_every_schema_property_carries_a_chinese_title` 只断言 title 非空，不校验是否中文 —— 断言弱于测试名
Task 3: minor (deferred): 「单一真相」未完全达成 —— 提示词散文里仍手写「它没把握的问题」「适配理由」等中文名副本，改 title 时不会同步，且无测试守卫（讲解性用语，影响有限）

Task 3: fix round 1/5 (1 addressed, 0 open — 护栏正则漏单字键；新正则 `[A-Za-z_][A-Za-z0-9_]*` 减槽位减白名单 {v0}，并以「把适配理由改回裸 reason 必须变红」证明了新护栏真能失败；仅 test_roster.py +13/-3)
Task 3: complete (commits 98aaf1d..fe7c61e, review clean)
Task 3: minor (deferred): 断言消息「手写了字段键」在语义放宽后不精确 —— 任意非槽位 ASCII token（未来正当出现的 JSON/schema/模型名）都会报红，却被称为「字段键」，会误导定位
Task 3: minor (deferred): `_ALLOWED_LATIN` 对 idea_parser 也生效，而 `v0` 只出现在架构师提示词里（白名单作用域略宽）

Task 4: complete (commits c5bd2e2..129dc25, review clean)
Task 4: minor (deferred): 超时解析缺 `timeout_seconds: 0`（假值落回全局）与「全局键缺失」两条路径的用例
Task 4: minor (deferred): 默认值 300 在 `config.py:18` 与 `runtime_service.py:36` 重复；因 `load_settings()` 合并 DEFAULT_SETTINGS，后者的兜底分支实际不可达
Task 4: minor (deferred): 新测试写入 **session 级共享的** `settings.json` 且未隔离（`conftest.py` 的临时目录整个 session 共享，`session` 夹具只重建库）；且声明了 `monkeypatch` 参数却未使用。当前套件下无串扰（唯一消费者在注入假传输层时不受超时值影响，且该文件按字母序最后跑），但「142 项通过」只证明默认收集顺序下无碍，不是隔离性证据 —— 套件既有惯例是逐用例 `monkeypatch.setenv("STORYFORGE_DATA_DIR", tmp_path)`
Task 4: minor (deferred): `execute` 每轮读两次设置文件（`runtime_service.py:76` 与 `_resolve_timeout` 内各一次）
Task 4: minor (deferred): `test_llm.py` 文件中部重复导入 `httpx` / `pytest` / `app.runtime.llm`

Task 5: complete (commits 129dc25..e82e2dc, review clean)
Task 5: minor (deferred): `conftest.py:33-36` 的 teardown 非异常安全 —— `drop_all` 写在 `with` 块之后而非 `try/finally`，用例抛异常时 pytest 会把异常 throw 进生成器，teardown **静默不执行**，而红跑恰是它最该生效的场景（后果被两点限制：下个用例开头仍会 drop；字母序在该文件前的写库文件只有 test_agents_service.py）
Task 5: minor (deferred): 继承源未校验归属 —— `agent_service.py:43-47` 直接信任 `current_version_id`，而同文件 `rollback_to` 对同类指针做了 `agent_id` 校验（brief 未要求）
Task 5: minor (deferred): `or highest` 的真实回退分支无覆盖（「有历史版本但 current_version_id 为空/指向不存在行」）；且报告的自审把它说成已覆盖，属过度声明
Task 5: minor (deferred): `test_agents_service.py:1` 的 `import pytest` 未使用（brief 逐字带入）
Task 5: minor (deferred): `client` 夹具（`test_api.py:13-32`）自身仍零隔离，本次只堵了 `session` 一侧

Ruling: T5 的实施者在 brief 文件清单之外改了 `backend/tests/conftest.py`（补 `session` 夹具的用例后清表）。**判定为正当偏离，予以保留** —— 诊断经代码核实成立（`client` 夹具只 init_db + seed、不 drop/create；`find_by_task_type` 无 ORDER BY，会选中遗留的同 task_type 智能体），修法落在该夹具 docstring 自己承诺的「不留跨用例的状态」上，是对既有承诺的补全而非新增约束，且无任何用例同时使用 `session` 与 `client`，不波及其它测试。实施者另起独立提交（`e82e2dc`）便于审查与回滚，做法正确。（审查者独立复核后给出同一判断。）— 依据：新测试文件按字母序排在 `test_api.py` 之前暴露了既有夹具缺陷，属本任务的波及面 — 代价：若判断有误，conftest 是多文件共享夹具，回滚该单笔提交即可。

Task 6: complete (commits e82e2dc..0754ee8, review clean)
Task 6: minor (deferred): `role_label` / `color` 允许空串而 `name` 不允许（`schemas.py:91-93`），`PATCH {"role_label": ""}` 会静默清空 —— plan-mandated，与既有 `ProviderUpdate` 风格一致，判定无害
Task 6: minor (deferred): `update_agent` 静默忽略白名单外的键（拼错字段名会 200），当前路由转发路径下不可达
Task 6: minor (deferred): `slots.py` 由 api 层直接 import runtime 的 `SLOT_REGISTRY`，未走 service —— 与其它路由不必构，但未违反任一条分层硬约束，且是 brief 指定形状
Task 6: minor (deferred): 测试把 `raw_idea.over_budget` 写死为 `"drop"`，是唯一一处重述常量（plan-mandated；但它同时守住了字段名拼写）

Task 7: complete (commits 0754ee8..b551168, review clean)
Task 7: minor (deferred): `_first_bound_model` 的两条兜底支路（唯一启用服务商 + 无主绑定应被采用；多启用时兜底须失效）无测试覆盖
Task 7: minor (deferred): 网络失败断言偏松（两选一），未锁死 ConnectError → network 分类；状态码表未覆盖 5xx 与无 status 的 kind 兜底分支
Task 7: minor (deferred): `_first_bound_model` 扫描全部 `AgentVersion` 而非当前版本（brief 规定），最坏是用已弃用版本的模型去探测，产生「模型名不存在」假阴性——不会产生本任务要消灭的假阳性

Task 8: complete (commits b551168..adbd062, review clean)
Task 8: minor (deferred): `updateProvider` / `updateAgent` 的 body 用 `Record<string, unknown>`，编译器不校验字段名与后端 schema 的对应（拼错不报错）—— 该文件既有约定，非本任务偏离

Ruling: 审查者（只读）留下的 ⚠️「`pnpm build` 无法独立验证」由我亲自解决 —— 在 worktree 的 `frontend/` 跑 `pnpm build`，`tsc -b && vite build` 输出 49 modules、`✓ built in 2.41s`、无类型错误。该 ⚠️ 消解，T8 以「构建干净」结案。— 依据：本任务唯一 gate 不能只凭报告采信 — 代价：无。

Ruling: T9 的两条 Important —— 均判定为**真缺陷、进修复循环第 1 轮**。
  (1) 保存 agent 级字段会静默还原未保存的版本级编辑：`saveAgentFields` → `refreshAgents` 造出**新的** `selected` 对象 → 依赖 `[selected]` 的重置 effect 复跑 → `setDraft` 整体覆盖。按钮与提示词同屏，是会真实触发的路径；同根因还令成功提示被 `setNotice('')` 抹掉。修法：把重置时机从「selected 变了」改为「智能体或当前版本变了」（复合键 `id:current_version.id`），且仅在换智能体时清 notice 与 run。这是 brief 逐字给出的代码所致，属计划缺陷。
  (2) 清空输出契约实际不会清空：页面正确发 `null`，但后端 `agents.py` 的 `model_dump(exclude_none=True)` 把显式 null 当「未提供」丢掉，`create_version` 于是继承上一版契约；而界面占位文案明写「留空表示不做结构化校验」，是可被反复触发的假承诺。修法：改 `exclude_unset=True`，使「显式传 null」= 清空、「未传」= 继承，并补两条回归测试。
  — 依据：前者是 T9 自身引入的可达数据丢失路径，后者是 T9 界面文案与其后端契约不一致；两者都不修则 T9 的交付不能被信任 — 代价：(2) 的修法改动了版本创建的入参语义，若判断有误，影响面是「显式传 null 的字段不再继承」——只在作者主动清空时发生，且这正是期望行为；两条回归测试分别钉住两种语义。

Task 9: fix round 1/5 (2 addressed, 0 open — ①重置时机改复合键 `id:current_version.id`，保存 agent 级字段不再还原版本级草稿，成功提示也不再被抹掉（并顺带新增 `setRun(null)` 修掉切智能体后调试台残留）；②后端 `exclude_none` → `exclude_unset`，显式 null 真正清空契约，补两条回归测试。commits 3dfe58e..8ed7c52)
Task 9: complete (commits adbd062..8ed7c52, review clean)
Task 9: minor (deferred): `skills_json` 仍未在页面暴露，是「角色卡全字段」下版本级唯一缺席字段（brief 未要求）
Task 9: minor (deferred): 挂载期读取路径（listProviders/listSlots/listAgents/listProjects/listVersions）无 `.catch`，后端不可用时表现为空面板、无可读原因（保存路径有提示）
Task 9: minor (deferred): 非对象 JSON（`[]`/`123`/`"x"`）能穿过页面校验，随后被后端 422，且 client.ts 对数组型 detail 会字符串化成 `[object Object]`
Task 9: minor (deferred): 「触发方式」与参数档一样只存不生效，但免责说明只写了参数档
Task 9: minor (deferred): 清空模型名会回落到 `provider.name`（即 P1a 复验的失败路径），页面未说明「留空 ≠ 自动选模型」
Task 9: minor (deferred): 保存按钮无 loading/禁用，连点会连建多个版本

Ruling: 把计划文档 Task 9 里那段有缺陷的 effect 同步为已交付版本 —— 与 T3 的处理同一依据（计划是实施输入，留着错误代码等于留着错误指令）。— 代价：无（纯文档同步）。

Ruling: T10 审查为 spec ❌ + Needs fixes，四条 Important —— 全部判定为真缺陷，**进修复循环第 1 轮**。
  (1) `data.architecture` 被整段丢弃，四个字段只写不读、刷新即空 —— spec 要求「编辑故事圣经」是持续能力，非一次性动作。修法：项目加载时从已存架构回填草稿与幕，并新增 `hasSaved` 让编辑器在该状态下也显示。
  (2) 清空字段传 `undefined` → 键消失 → 后端按「保持原值」处理，删掉的文字静默回来。修法：四个字段改为传空串（后端 `if payload.get(key) is not None` 会真正置空）。
  (3) 在途推荐无身份校验：推荐是 120s+ 的真实调用，期间点「手工建立」或切项目，响应回来会覆盖手写内容或填错项目（而 `adopt` 用当前 projectId，会写进另一个项目）。修法：加 `runToken` ref，换项目与转手工各递增一次，响应回来先比对令牌。
  (4) 两个 GET 无 `.catch`；且 `savedActs` 只在成功分支替换，失败时 B 项目标题下显示 A 项目的幕。修法：补 `.catch`，并在 effect 开头同步清空 `savedActs`。
  — 依据：四条都属「接线而非模型」类缺陷，正是本切片要消灭的那一类；(1) 是 spec 明确要求的一半未达成 — 代价：(1) 放开了「已存结构可再次采纳」，若后端 `adopt` 是追加语义就会把幕翻倍 —— **已先读 `architecture_service.adopt` 核实为替换语义**（先 `session.delete(existing_acts)` 再重建，docstring 明写「重复采纳则原地更新」），该风险不成立。

Task 10: fix round 1/5 (4 addressed, 0 open，但修复引入 1 条新 Important —— `busy` 卡死；commits b73ff2f..fb9d4ea)
Task 10: fix round 2/5 — 待验（换项目递增 token 后未清 `busy`，而 `recommend` 的 finally 被 token 守卫拦下，导致「推荐在途→切项目」后按钮永久停在「生成中…」）

Ruling: T10 修复引入的 `busy` 卡死 —— **这是我的修法漏洞**（我给 `startManual` 加了 `setBusy(false)`，却漏了换项目这条路径），非实施者失误。按 skill「修复 diff 里的新 Critical/Important 并入待办清单」进第 2 轮，修法为在 `[projectId]` effect 的 `runToken.current++` 之后补 `setBusy(false)`。— 代价：无（一行）。

Task 10: fix round 2/5 (1 addressed, 0 open —— `[projectId]` effect 内 `runToken.current++` 之后补 `setBusy(false)`；commits fb9d4ea..f0b8b99)
Task 10: complete (commits c75dbb3..f0b8b99, review clean)
Task 10: minor (deferred): 占比输入非数值时静默丢弃（`Number('25%')` → `NaN` → 序列化为 `null`），无报错无提示，且「已写入的结构」不显示该字段
Task 10: minor (deferred): `DraftAct.seq` 是死字段（三处维护它，`adopt` 却按数组下标重新编号），两个来源并存
Task 10: minor (deferred): 幕行用 `key={index}`，删除中间行按位复用 DOM 节点（当前受控值无可见错误，加拖拽排序会串值）
Task 10: minor (deferred): `message` 渲染在顶部工具条，而「至少填一幕。」「已写入项目结构」都发生在底部编辑器处，作者视线需上移
Task 10: minor (deferred): 手动模式下再点「推荐结构」，模型产出会填进草稿但标题仍写「（手工）」
Task 10: minor (deferred): 无取值/合计校验（不校验 0–1 范围、不校验各幕占比之和为 1）
Task 10: minor (deferred): `recommend()` 入口未递增 `runToken`，两次并发推荐会共享同一 token；当前 UI 因 `busy` 禁用按钮而不可达

Ruling: T11 的两条 Important —— 均判定为真缺陷，**进修复循环第 1 轮**。两条的共同点是后果**不可恢复**：
  (1) 删除服务商无二次确认，而服务端会一并 `dpapi.delete_secret` 删掉本机密钥，密钥在界面上永远是屏蔽态、作者无从找回；按钮又与「编辑」「测试连通性」同排。修法：`window.confirm` 确认 + 删除被编辑行时清 `editing`。
  (2) 超时输入 `Number('') === 0` 会把 `request_timeout_seconds` 持久化为 0，后端无下界校验，此后每次模型调用立刻超时。修法：`Number.isFinite(value) && value > 0` 守卫 + 保存挪到 `onBlur`（顺带消掉每击键一次 PUT）。
  — 依据：两条都属「一次误操作即永久损坏本机配置」，不是风格问题 — 代价：若裁定过严，多两处守卫，无产品风险。

Ruling: 我额外把一条 Minor 与发现 1 同批修掉：`saveProvider` 未 trim `api_key`，纯空白密钥会被当成真值覆盖已存密钥（同为不可恢复）。超出审查发现范围，但要改的 `saveProvider`/`removeProvider` 本就在本次派发内、且同属「不可恢复丢失」一类，一并处理比留到最终审查更省事 — 代价：扩大了一点审查面；该行改动已在派发里显式标注为「控制方加派」。

Task 11: fix round 1/5 (3 addressed, 0 open —— 删除加 `window.confirm` 并清编辑态；超时加 `Number.isFinite && > 0` 守卫并把保存挪到 `onBlur`（输入框改 `key`+`defaultValue`）；`api_key` 补 trim。commits d67909b..a62fbbf)
Task 11: complete (commits f0b8b99..a62fbbf, review clean)
Task 11: minor (deferred): 改 `key`+`defaultValue` 后，**非法失焦或保存失败**时输入框会停在陈旧值（清空后停在空白，服务端仍是原值），受控写法本会弹回；有 notice 兜底，刷新即恢复
Task 11: minor (deferred): 「上下文预算」输入仍是受控 + `onChange` 即时保存的旧写法，同样存在「清空写 0 / 每击键 PUT」的形态（不在本次 fix diff 内）
Task 11: minor (deferred): `editing` 在删除被编辑行后不清空（本次已修其中一半）；编辑路径不校验 `name`/`base_url` 非空，与 `addProvider` 不一致

## 最终整支复查

整支复查（opus，922432a..a62fbbf，22 提交）：**Ready to merge: With fixes**，无 Critical，三条 Important。
  (1) `model` 仍回落到 `provider.name` —— 发现 §3.2 的根因没拔，只加了 UI 逃生口；运行路径仍会把服务商显示名当模型 ID 发出去。
  (2) Studio 保存版本重造 `model_binding_json`，静默抹掉 `timeout_seconds`/`prices`/`params`（本切片引入的回退）。
  (3) 上下文预算输入清空即写 0（T11 刚给超时字段修掉的同一类，唯独漏了预算）。
  延后事项分诊：仅 (3) 判为合入前必修；其余 Minor 分四组（装饰/覆盖缺口/测试隔离/防御性小项/UX 文案）判为可留待后续。
  建议：明确补做 T12（真实模型复验）；考虑把 agent 级超时暴露到工作室（否则 spec §3.2 第一层是死代码）。

最终修复波（一个 commit，8d4b530）：三条 Important 全部 ADDRESSED。实施者标出一处需裁决的偏离 —— 发现 1 改抛错后 9 条既有测试失败（两个夹具原本靠静默回落才跑得通），它按 `client` 夹具既有做法补「智能体需绑定模型」前置条件，未改预置阵容。
最终修复波 re-review：**All findings addressed，无新 Critical/Important**；偏离经证据裁决**接受**（既有注释先例；5 条 API 用例断言的是 raw_text/rendered_prompt/落库字段，无一条断言模型名，补前置恢复的正是原路径；改预置阵容会更差，与「模型由作者绑定」的既定决定冲突）。

Ruling: 最终整支复查的三条 Important —— 全部判定为真缺陷，按 skill「ONE fix dispatch」合成**一次**修复波派出（未按条分派，避免各自重建上下文与重跑套件）。— 依据：三条都在本切片的接线层，且 (2)(3) 是本切片自己引入/漏改的 — 代价：三条混在一个 commit，若要单独回滚需手工拆。

Ruling: 最终修复波实施者在 brief 之外改了 `backend/tests/test_api.py`（补夹具的模型前置条件）—— **判定为正当偏离，予以保留**。依据：发现 1 是刻意把静默回落改成显式报错，其连带影响就是「依赖该回落的夹具不再成立」；改预置阵容会替作者决定生产默认值，与 spike 结论（模型由作者绑定）冲突。经独立 re-review 复核，未掏空被测行为。— 代价：若判断有误，夹具前置条件是多文件共享处，可单独回滚。

## 未完成

Task 12（真实模型端到端复验）：**未执行**。原因：需重建开发库（工作区之外的副作用）＋ 消耗作者的计费额度 ＋ 需要作者本人重新录入服务商密钥（重建库会清掉 provider 行）。属需停下来问的四类之一。整支复查亦独立指出「不能仅凭 pytest 绿就宣称 P1a 完成」，与本切片的存在理由一致。

Ruling: re-review 提的 Out-of-Scope 观察 —— 计划文档 Task 3 的代码块里仍留着那个被证伪的弱正则（`\b[a-z]+(?:_[a-z]+)+\b`）。计划是实施输入，后来者照抄会静默退回旧盲区 → 已把计划中该代码块同步为交付版本（含 `_WORD_RE` / `_ALLOWED_LATIN`）。— 依据：计划必须与已审查通过的代码一致，否则它是错误指令 — 代价：无（纯文档同步）。

Ruling: T3 审查的 Important（plan-mandated）—— 我写的护栏正则 `\b[a-z]+(?:_[a-z]+)+\b` 要求至少一个下划线，**漏掉全部单字键**（genre/reason/tool/risks…），而 schema 的键多为单字，即最可能的复发形态恰在盲区内；审查者给的现成反例是 base 版 `ARCHITECT_PROMPT` 的裸 `reason`。spec §4 明写这条跨产物一致性测试是本切片要补的关键测试，护栏带这种盲区不算达成 → **裁定修，进入修复循环第 1 轮**，改为「查所有 ASCII 标识符 − 槽位 − 白名单 {v0}」，并要求实施者用「故意改回裸 reason 必须变红」来证明新护栏真能失败。— 依据：spec §4 对本测试的定位，而非代码风格偏好 — 代价：若裁定过严，只多改一条测试，无产品风险。

