# P3 走查与复验记录：模型分路、参数档、精确记账、单价与费用

> 2026-10-21。分支 `worktree-p3-model-management`。真实模型复验已完成（`qwen3.8-flash`，四次调用）。

## 1. 已完成（不花额度）

### 1.1 自动化测试

| 项 | 结果 |
|---|---|
| 后端 | **653 passed**（基线 594，本段新增 59） |
| 前端 | **30 passed** |
| 前端构建 | `pnpm build` 干净 |

### 1.2 临时数据目录走查（假传输层，0 真实调用）

做法：`STORYFORGE_DATA_DIR` 指向临时目录，用 `httpx.MockTransport` 替换运行时客户端，走真实 HTTP 路由。

| 步骤 | 预期 | 实测 |
|---|---|---|
| 建服务商 + 配置单价（qwen3.8-flash，输入 0.3 / 输出 1.2） | 200 | ✅ |
| 把 `idea_parse` 分路配成该服务商 + 模型 + `creative`，角色卡本身不绑模型 | 设置写入 | ✅ |
| 跑一次灵感解析 | 模型取自分路 | ✅ `model=qwen3.8-flash` |
| 参数档 | `creative` 生效 | ✅ 发出去 `temperature=1.0`（首次走查为 0.2，见 §1.3） |
| token 来源 | 服务商返回了 usage | ✅ `usage_source=provider`，1000 + 500 |
| 费用 | 按单价算 | ✅ `(1000×0.3 + 500×1.2)/1e6 = 0.0009` |
| 三维汇总 | 有按任务分组 | ✅ `by_task` 含「灵感解析」，`unpriced_runs=0` |
| 删掉单价后再看汇总 | 转为未定价 | ✅ `unpriced_runs=1` |
| 作者真实库 | 不动 | ✅ 走查全程用临时目录 |

### 1.3 走查中发现并修复的缺陷

**预置版本的参数档挡住了分路。** 解析师预置出厂就是 `strict`，而最初的规则是「版本参数档非 `balanced` 即视为作者显式选择」，于是分路里配的 `creative` 永远不生效 —— 而那个 `strict` 根本不是作者选的。

修法：改用「版本有没有 `preset_fingerprint`」判定。有指纹 = 未改动的预置，参数档跟随分路；无指纹 = 作者编辑过的版本，参数档以版本为准。两条规则各有测试钉住。

### 1.4 顺带修掉的测试污染

两条既有用例（`test_generate_without_writer_model_is_400_before_streaming`、`test_context_preview_without_writer_is_400`）会清空模型绑定 / 停用执笔且不还原，共享的 `client` 库因此被污染，后续所有生成类用例一起 400。已改为 `finally` 还原。新增的 `conftest._default_settings` 夹具保证 `settings.json` 在用例之间回到默认值 —— 模型分路会改变哪条用例能跑通，串状态后的失败看起来像产品缺陷。

## 2. 真实模型复验（已完成）

做法：SQLite backup API 复制作者库 + `secrets.bin` 到系统临时目录，后端用 `STORYFORGE_DATA_DIR=<副本>` 启动，全程未写作者原库。

| 步骤 | 结果 |
|---|---|
| 副本首次启动 | 迁移 `[0,1] → [0..7]`，生成 `backups/pre-migration-v7-20261021-131722/`；`usage_source` 列存在；2 项目 / 3 智能体一条不少 |
| 副本二次启动 | 版本不变、不产生第二个备份、智能体不重复预置 |
| 预置补齐 | 3 → 9 个角色卡；执笔 / 章纲策划 / 场景策划 / 审校 / 逻辑审查官 / 回写助手的模型绑定为空 —— 正好可验分路 |
| 分路指向不存在的服务商 | 400，文案「指定的服务商不存在：does-not-exist」 |
| 分路给 `write` 配 `qwen3.8-flash` + `creative`，执笔本身不绑模型 | 生成成功；运行记录 `model=qwen3.8-flash`、`params.temperature=1.0`、`prompt_tokens=855`、`completion_tokens=2540`、`usage_source=provider` |
| 与存量运行对比 | 同库早期记录（P1b-1 时期）为 `usage_source=estimated`、`temperature=0.7` —— 新旧口径区分清晰 |
| 配单价（输入 0.3 / 输出 1.2）后再生成 | `cost_estimate=0.003882`；项目汇总新增该费用；`unpriced_runs=1`（只有那条历史无价记录） |
| 任务分组 | 正文 3 次 0.003882 / 对话 3 次 / 灵感解析 1 次 / 架构推荐 1 次，费用按组正确归集 |
| 作者把执笔版本改成 `strict` 后再生成 | `params.temperature=0.2` —— 作者版本压过分路的 `creative`（1.0），符合设计 |
| 作者原库 | `storyforge.db` / `secrets.bin` SHA-256 前后一致；副本已删除 |

**额度**：四次真实调用（分路报错那次不发请求），估算新增约 855+2540 + 855+2584 + 855+3477 ≈ 11.2k tokens；累计约 99.5k / 1,000,000。

### 2.1 复验确认的三条设计意图

1. **分路能接管未绑模型的智能体**：预置阵容出厂不带模型名，作者只在「模型与费用」里按任务配一次即可跑通，不必逐张角色卡去绑。
2. **参数档真的发出去了**：同一智能体在 `creative` / `strict` 下请求体里的 `temperature` 分别是 1.0 与 0.2。
3. **token 来源可信**：新运行为 `provider`（服务商返回值），历史记录保持 `estimated`，界面上能区分哪个数不可信。
