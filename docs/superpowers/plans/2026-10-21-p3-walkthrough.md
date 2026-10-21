# P3 走查与复验记录：模型分路、参数档、精确记账、单价与费用

> 2026-10-21。分支 `worktree-p3-model-management`。**真实模型复验暂停**：作者表示等想好再指定模型，本文件先记录不花额度的部分。

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

## 2. 待做（需要真实模型）

作者暂停在模型选择这一步。恢复后按下列步骤执行，**只用作者库副本**：

1. 复制 `storyforge.db`（SQLite backup API）与 `secrets.bin` 到系统临时目录。
2. 后端用 `STORYFORGE_DATA_DIR=<副本>` 启动，先验证迁移 v7 执行、`usage_source` 列存在、原数据一条不少、二次启动不重复。
3. 真实流式生成一次：确认 `usage_source=provider`，token 与服务商返回一致。
4. 删掉执笔版本上的模型绑定、给 `write` 配分路 → 生成成功，运行记录 model 等于分路值。
5. 分路指向不存在的服务商 → 报错文案含键名。
6. 把执笔版本参数档改成 `creative` → 运行记录 `params.temperature == 1.0`。
7. 删除副本，核对作者原库 `storyforge.db` / `secrets.bin` 的 SHA-256 未变。

**额度基线**：复验前 `qwen3.8-flash` 累计约 88,269 / 1,000,000。本次预计 3–5k。
