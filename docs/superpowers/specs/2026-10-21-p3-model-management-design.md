# StoryForge P3 设计：智能体工作室与模型管理

> 2026-10-21。P2 结束后，模型这一层还欠着四笔账：**按任务分派模型没人读**、**参数档只存不生效**、**流式 token 与费用靠估算**、**每百万 token 单价无处填写**。这四笔账都指向同一件事 —— 作者改了界面上的模型设置，行为却没变。P3 把它们一次结清，并把调试台补成真正能回答「这次为什么慢、为什么贵」的地方。
>
> 上位依据：`StoryForge-产品设计文档.md` §4.9（智能体工作室）、§4.10（模型接入与成本）、§5.1（角色卡）、§5.6（调试台）、§7.3（数据模型）、D-06（版本化）、D-07（界面开销要看得见）、D-21（不引入重型依赖）。

## 1. 阶段定义

### 1.1 为什么先做这四件，而不做管线编排

上位文档把 P3 写成「智能体工作室与模型管理：角色卡全字段、调试台、管线编排、模型分路、费用记账」。其中角色卡全字段与调试台**已在 P1a 收口时交付**。剩下的是：

| 项 | 现状 | 影响 |
|---|---|---|
| 模型分路 | `settings.model_routing` 存在但**全仓无人读取** | 作者按任务换模型时改了没反应 |
| 参数档 | `AgentVersion.param_profile` 只存不生效；实际发出去的是全局 `default_params` | 「严谨 / 平衡 / 发散」三档是装饰 |
| 精确记账 | 流式路径不请求 usage，token 靠 `estimate_tokens` 估算 | 长篇批量生成后，费用表与实际对不上 |
| 单价配置 | `model_binding_json.prices` 有计算逻辑，**没有任何界面能填** | 所有费用恒为 `$0` |

这四件是同一条链路（**选哪个模型 → 用什么采样参数 → 花了多少 → 是多少钱**）上的四个断点。合成一段实施，能一次把「作者改了设置，行为跟着变」验证到底；拆开做会把同一套真实模型验证跑四遍，而这道验证正是 P3 唯一必须花额度的地方。

**管线编排（可编辑节点、换绑智能体、调顺序）本段不做。** 理由：它要的是一张新的`pipeline` 领域模型 + 一套编排执行器，与上面四件事没有共享代码；而且现有 8 个预置智能体已经覆盖了管线里的全部节点，编排的业务价值要等作者真的需要「同一节点换不同智能体并排比较」时才成立。这一项留到 P3b（见 §10）。

### 1.2 验收标准

1. **模型分路生效**
   - 全局设置里能按**任务类型**（`idea_parse` / `architecture` / `worldbuilding` / `chapter_plan` / `scene_plan` / `write` / `writeback` / `continuity` / `logic_check` 等）指定「服务商 + 模型 + 参数档」。
   - 解析优先级：**角色卡显式绑定 > 全局分路 > 全局默认模型**。
   - 角色卡没显式绑定某个字段（比如只绑了模型没绑服务商）时，缺的字段从分路里补，而不是整体回落到默认；这样「只换模型、服务商跟随分路」是可能的。
   - 分路里配了不存在的服务商 → 明确报错并指出是哪一条分路，不静默回落。
2. **参数档生效**
   - 三个内置档 `strict` / `balanced` / `creative` 各自解析成一组采样参数，并**真正发给服务商**。
   - 角色卡版本里可以写自定义参数（`model_binding_json.params`），**优先级高于参数档**；全局 `default_params` 只补两者都没提到的键。
   - 调试台能看见这次实际发出去的 `params`（已落库为 `GenerationRun.params_json`，界面上补一栏）。
3. **精确记账**
   - 流式路径向服务商请求 usage（`stream_options.include_usage`），拿到就用真实值，拿不到才回落到估算，并在运行记录上标出**这一个是估算的**。
   - `GenerationRun` 新增 `usage_source`（`provider` / `estimated`），迁移 **v7**。
   - 流式 SSE 的 `done` 事件带上 `usage_source`，写作台明示。
4. **单价与费用**
   - 每百万 token 的输入 / 输出单价按「服务商 + 模型」配置，存在**本机数据库**（新表，`create_all`），不塞进角色卡版本里 —— 否则同模型在十个智能体上绑十次就要填十遍。
   - 单价解析优先级：**角色卡绑定里的 `prices`（老数据兼容）> 模型单价表**。
   - 费用汇总能按项目、按智能体、按任务类型三个维度看；未配置单价的模型在界面上明确标「未定价」，**不把 `$0` 伪装成「免费」**。
   - 预算提醒：`settings.budget_alert` 已存在，接上实际读取并在仪表盘提示。
5. **调试台补齐**
   - 运行详情显示：实际模型、实际参数、token 数与**来源**、费用、耗时、渲染提示词、原始返回、解析结果。
   - 能按智能体筛最近运行（接口已支持 `agent_id`，前端补入口）。
6. **基线**：后端既有 594 条全绿；前端 30 条全绿、`pnpm build` 干净。
7. **真实模型复验**：至少一次真实流式调用拿到服务商 usage（`usage_source=provider`）；至少一次分路切换后实际请求的模型名与设置一致；至少一次未绑模型时按分路取到模型并成功。作者真实库只读，验证走副本。

### 1.3 明确不做

- **管线编排**（可编辑节点 / 换管线 / A/B 并排生成）—— P3b。
- **多服务商自动故障转移**（限流/网络错误换一家重试一次）—— 上位 §4.10 列了，但它需要先有「可用性探测 + 冷却」的机制，否则每次失败都要多等一个超时；与 P3 四件事无共享代码，记入 P4。
- **精确 token 计数的本地分词器** —— 估算函数保留作为兜底；不引入 tiktoken 这类依赖（D-21）。
- **按 token 预算自动中止**（花到多少就停）—— 预算提醒只做提示，不拦截。
- **服务商内置预设清单**（一键填 DeepSeek / Moonshot 地址）—— 现状是手填 `/v1` 地址，够用；预设清单要维护一份会过期的地址表，P5 再说。
- **参数档的名词自定义**（作者自建具名档）—— 内置三档 + 版本级自定义参数已覆盖；具名档属于「智能体工作室深化」，留 P3b。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 分路粒度 | 按 **task_type**，不是按 agent | 任务是作者心里的概念（「正文用哪个模型」），智能体是它的实现；按 agent 会把「复制一个执笔做实验」变成分路的第二套配置 |
| 分路字段 | `{provider_id?, model?, param_profile?}`，全部可选 | 允许只换模型不动服务商；缺哪项补哪项，好处是「一家服务商 + 多档模型」这种最常见情形只需填模型名 |
| 分路不存在的服务商 | **报错**，不回落 | 静默回落会让作者以为在用 A 家，实际在花 B 家的钱 |
| 参数档存哪 | 代码里的常量表 `PARAM_PROFILES` | 三档是产品定义的一部分（严谨/平衡/发散），不是作者数据；改它要发版，正好走版本记录 |
| 参数优先级 | `版本 params` > **参数档** > 全局 `default_params` | 全局是「所有调用共有的兜底」；参数档是「这个智能体的性格」；版本 params 是作者点名要的 |
| 参数档与分路的交互 | 角色卡 `param_profile` 优先，未绑时取分路的 | 与模型同一套「显式覆盖」语义，不引入第二种规则 |
| usage 获取 | 流式请求带 `stream_options: {"include_usage": true}`；**服务商若不认这个字段导致 400，自动去掉重试一次** | 不赌兼容性，但也不因噎废食；重试只发生一次且仅在 400 时 |
| usage 回落 | 拿不到 usage → 估算，并写 `usage_source="estimated"` | 让作者知道哪个数不可信，比给出一个精确的假数好 |
| token 保存字段 | 不新增 token 列，新增 `usage_source`（迁移 v7） | token 数本来就存了，缺的是「这个数从哪来」 |
| 单价存哪 | 新表 `model_price`（provider_id + model 唯一），`create_all` | 单价是「模型」的属性，不是「绑定」的属性；放角色卡里同模型要填多遍 |
| 单价与旧数据 | 角色卡 `prices` **仍然优先** | P1a 以来的数据与测试都基于它；保留兼容，界面上不再鼓励写它 |
| 未定价显示 | 界面显示「未定价」而不是 `$0`；汇总里 `unpriced_runs` 计数 | `$0` 会被读成「免费」 |
| 费用汇总维度 | 项目 / 智能体 / 任务类型 | 产品 §4.10 要求按这三个汇总 |
| 预算提醒 | 只读 `settings.budget_alert` 并提示，**不拦截调用** | 控制力：花多少由作者定；提醒是信息不是闸门 |
| 调试台 | 复用既有 `RunTrace`，补「实际参数」与「token 来源」；按智能体筛选运行 | 数据已在库里，只是没展示 |
| 迁移 | 只加 `usage_source` 一列（v7） | 其余全是新表或设置项，走 `create_all` / `settings.json` |

## 3. 模型分路

### 3.1 数据结构（`settings.json`）

```jsonc
{
  "model_routing": {
    "write":       { "provider_id": "…", "model": "qwen-max",  "param_profile": "balanced" },
    "logic_check": { "model": "qwen-flash", "param_profile": "strict" },
    "architecture": { "provider_id": "…" }
  },
  "default_model": "qwen-flash"
}
```

- 键是 `task_type`。未知键在读取时忽略并给一条 warning（不阻断 —— 作者可能刚从旧版升级，也可能是删掉了一个智能体）。
- 值是对象；老数据里若有「键 → 字符串」的形态（历史上没人写过，但为防手改 settings.json），读取时把它当作 `{"model": 字符串}`。

### 3.2 解析链（`runtime_service.resolve_binding`）

新增一个纯函数模块 `app/runtime/routing.py`（不碰数据库，可单测）：

```python
def resolve_binding(*, version_binding, version_profile, task_type, routing, default_model, default_params, profiles):
    """返回 (binding, profile_name, warnings)。缺哪项补哪项。"""
```

顺序（**逐字段**，不是整体回落）：

```
provider_id : 版本 > 分路
model       : 版本 > 分路 > settings.default_model
param_profile: 作者版本 > 分路 > 未改动的预置 > balanced
params      : default_params（底层） ← PARAM_PROFILES[profile] ← 版本 params
```

关于 `param_profile`：角色卡版本一直有值（预置出厂就带 `strict` / `balanced`），若照「版本优先」处理，分路里的参数档几乎永远不会生效。判据是**版本是否来自未改动的预置**：有 `preset_fingerprint` 说明它是预置内容，参数档跟随分路；没有指纹说明是作者编辑出来的版本，参数档以版本为准。

（设计初稿写的是「不等于 `balanced` 才算显式」。走查实测推翻了它：解析师预置是 `strict`，分路配的 `creative` 被挡住，而那个 `strict` 不是作者选的值。两者都在问「作者表过态吗」，但只有指纹能区分预置自带与作者手改。）

`provider_id` 解析失败时抛 `ValueError("模型分路「write」指向的服务商不存在：…")`；模型缺失时沿用既有文案并补一句「或在模型分路里为任务 write 指定模型」。

### 3.3 应用位置

- `RuntimeService.prepare` 改为先调 `resolve_binding`，再解析服务商（`resolve_provider` 接受已定好的 `provider_id`，不再自己读 binding）。
- 所有既有调用点（`/api/runs`、ideas、architecture、world、chapters、audit、logic、writeback、batch、text）自动生效 —— 它们都走 `prepare`。
- 写作台的 `/context-preview` 也走同一条链，因此**预览里显示的模型就是真会用的模型**。

## 4. 参数档

### 4.1 常量表（`app/runtime/params.py`）

```python
PARAM_PROFILES = {
    "strict":   {"temperature": 0.2, "top_p": 0.8},
    "balanced": {"temperature": 0.7, "top_p": 0.9},
    "creative": {"temperature": 1.0, "top_p": 1.0},
}
PARAM_PROFILE_LABELS = {"strict": "严谨", "balanced": "平衡", "creative": "发散"}
```

- 只放「调性相关」的键；`max_tokens` 属于容量，仍由 `default_params` 提供（默认 4096）。
- 未知档名（作者手写过别的字符串）→ 回落到 `balanced` 并记 warning，不报错。
- 每档只写 `temperature` / `top_p`：不同服务商对 `presence_penalty` 等键的接受度不一，多写一个键就多一分 400 的风险。

### 4.2 合并顺序

```
{ **default_params, **PARAM_PROFILES[profile], **(版本 binding.params or {}) }
```

`max_tokens` 因此在多数情况下来自 `default_params`；作者在版本里写 `{"max_tokens": 8000}` 能覆盖。

## 5. 精确记账

### 5.1 客户端接口

`ChatClient.stream` 目前只 yield 字符串。改为 yield **事件**：

```python
@dataclass(frozen=True)
class StreamDelta:
    text: str

@dataclass(frozen=True)
class StreamUsage:
    prompt_tokens: int
    completion_tokens: int

async def stream(...) -> AsyncIterator[StreamDelta | StreamUsage]
```

- `HttpxChatClient.stream` 在 `include_usage` 生效时，末尾会收到一个 `choices: []`、带 `usage` 的块，转成 `StreamUsage`。
- 若首次请求因 `stream_options` 返回 400：去掉该字段**重试一次**（只重试一次，且只在这种情形），重试前不能已经吐过任何字符（400 在响应头阶段返回，天然满足）。
- 上层（`api/text.py`）累加 delta，收到 usage 就用真值。

**这是一处接口变更**：`test_text_api.FakeStreamClient` 与 `test_llm` 的断言都要跟着改成事件形态。这是刻意的 —— 留着 yield 字符串的旧接口，就得在调用处再猜一次「最后那个块是不是 usage」。

### 5.2 落库

`GenerationRun` 新增：

| 列 | 值 | 说明 |
|---|---|---|
| `usage_source` | `provider` / `estimated` | 迁移 v7，默认 `estimated`（存量数据视为估算） |

非流式路径本来就用服务商返回的 usage（`llm.complete` 里的 `usage.prompt_tokens`），只要服务商没给就回落估算 —— 同样写 `usage_source`。

### 5.3 界面

- `RunTrace` 在 token 旁显示 `（估算）` 角标。
- 写作台 `done` 事件带 `usage_source`，生成完成后在状态行明示「token 为服务商返回值 / 估算值」。

## 6. 单价与费用

### 6.1 新表 `model_price`（`create_all`）

| 列 | 类型 | 说明 |
|---|---|---|
| id | str | |
| provider_id | FK provider CASCADE | |
| model | str(120) | |
| input_price | float | 每百万 token |
| output_price | float | 每百万 token |
| currency | str(8) | 默认 `CNY` |

唯一索引 `(provider_id, model)`。删除服务商时级联删除。

### 6.2 费用解析（`app/runtime/pricing.py` 扩展）

```python
def resolve_prices(*, binding_prices, price_row) -> dict | None
```
- `binding_prices` 非空 → 用它（老数据兼容）。
- 否则 `price_row` → `{"input": …, "output": …}`。
- 都没有 → `None`（计费为 0，但计入 `unpriced_runs`）。

`GenerationRun` **不新增** `unpriced` 列：单价配置是**事后可改**的，一条运行的「是否定价」若落库，改完单价后历史仍显示未定价。因此 `unpriced_runs` 在**查询时**按当前单价表判定。

### 6.3 汇总接口

`GET /api/projects/{id}/cost` 扩展（不破坏既有字段）：

```jsonc
{
  "runs": 12, "prompt_tokens": …, "completion_tokens": …, "cost_estimate": …,
  "unpriced_runs": 3,
  "by_agent":  [{"agent_id":…,"name":…,"runs":…,"prompt_tokens":…,"completion_tokens":…,"cost_estimate":…,"unpriced_runs":…}],
  "by_task":   [{"task_type":"write","label":"正文","runs":…,…}]
}
```

任务类型的中文标签复用 `roster.TASK_TYPES` 旁边新增的 `TASK_TYPE_LABELS`（单一真相）。

### 6.4 预算提醒

`settings.budget_alert`（每项目？全局？）——**定为全局金额上限的提示**：仪表盘与模型页在「本项目费用 > budget_alert」时显示提示条。不拦截。

### 6.5 界面

- 模型页新增「模型单价」表格：服务商 + 模型 + 输入单价 + 输出单价，可增删改。
- 模型页费用区改为三个维度的小表：按项目 / 按智能体 / 按任务类型。
- 未定价的模型在单价表里明确可识别（列表里没有它的行）。

## 7. 调试台补齐

- `RunTrace` 增加「实际参数」区块（`run.params`，已有数据）。
- token 行显示来源：`（服务商）` / `（估算）`。
- 工作室调试台下方加「最近运行」列表，可按当前智能体筛选（`GET /api/runs?agent_id=`），点一条在 `RunTrace` 里展开。

## 8. 测试策略

| 层 | 测什么 | 方式 |
|---|---|---|
| `routing.py` | 逐字段补齐、显式覆盖、`balanced` 视为无意见、未知分路键、服务商不存在 | 纯 pytest，无数据库 |
| `params.py` | 三档合并顺序、版本覆盖、未知档回落 | 纯 pytest |
| `runtime_service` | 分路生效后 `prepare()` 的 model/params/provider 对；分路报错文案 | pytest + 现有夹具 |
| `llm.stream` | usage 块解析、`stream_options` 400 后退一次、重试后仍失败、后台 usage 缺失 | `httpx.MockTransport` |
| `text_api` | 流式改用事件后 `done` 带 `usage_source=provider`；服务商无 usage 时 `estimated`；取消路径仍收敛 | 既有假客户端改造 |
| `model_price` | CRUD、唯一约束、级联删除、费用解析优先级 | pytest |
| 费用汇总 | 三维度聚合、`unpriced_runs` 口径 | pytest |
| 迁移 v7 | 存量库补列、二次启动不重复、`requires=("generation_run",)` | 既有迁移测试模式 |
| 前端 | 费率表、费用三维、调试台参数与来源 | vitest（纯逻辑）+ 手工走查 |

## 9. 文件结构（预期）

```
backend/app/runtime/
  routing.py          # 新增：分路解析纯函数
  params.py           # 新增：参数档常量与合并
  pricing.py          # 扩展：resolve_prices
  llm.py              # 改：stream 返回事件；include_usage；400 重试一次
backend/app/db/models/
  config_models.py    # 改：ModelPrice 表
  run.py              # 改：usage_source
backend/app/db/migrations.py   # 改：v7
backend/app/services/
  runtime_service.py  # 改：resolve_binding、resolve_provider 签名
  provider_service.py # 改：cost_summary 三维、模型单价 CRUD
backend/app/agents/roster.py   # 改：TASK_TYPE_LABELS
backend/app/api/
  providers.py        # 改：单价 CRUD、费用维度
  text.py             # 改：流式事件、usage_source
frontend/src/
  pages/Models.tsx    # 改：单价表、三维费用、预算提示
  pages/Studio.tsx    # 改：参数档说明、最近运行
  components/RunTrace.tsx  # 改：实际参数、token 来源
  api/client.ts       # 改：类型
```

## 10. 遗留与后续

- **管线编排 / A/B 并排生成** → P3b。
- **多服务商故障转移** → P4（需要可用性探测与冷却）。
- **参数档具名自定义** → P3b。
- **精确计费货币换算** → 不做；单价按作者填的币种原样显示。
- **流式 usage 的服务商覆盖**：已知部分 OpenAI 兼容服务商不返回 `stream_options` 的 usage；回落估算并标注，是本段接受的结果。
