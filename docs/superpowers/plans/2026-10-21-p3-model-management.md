# P3 Implementation Plan：模型分路、参数档、精确记账、单价与费用

> **For agentic workers:** 按任务顺序实施，每个任务先写失败测试再实现，提交信息用中文 Conventional Commits。

**Goal:** 让模型分路与参数档真正生效，把流式 token 换成服务商真值，补上单价配置与三维费用汇总，并补齐调试台展示。

**Architecture:** 分路解析与参数合并下沉为 `runtime/` 下的纯函数（不碰数据库、不依赖 FastAPI）；`RuntimeService.prepare` 调用它们决定 provider / model / profile / params；流式客户端改为 yield 事件（文本 / usage）；单价进新表 `model_price`，费用汇总在读时聚合。

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + SQLite，React 19 + TypeScript + Vite + Tailwind，pytest / vitest。

**Spec:** `docs/superpowers/specs/2026-10-21-p3-model-management-design.md`

## Global Constraints

- 实施在隔离 worktree `worktree-p3-model-management`（从本地 `master` 切出）；master 在收口前不动。
- 基线：后端 **594 passed**，前端 **30 passed**，`pnpm build` 干净。每个任务结束不得低于基线。
- `api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。**新逻辑优先落在 `runtime/`**，能被纯 pytest 覆盖。
- 参数档常量只写 `temperature` / `top_p`；`max_tokens` 仍归 `default_params`。
- 新表 `model_price` 归 `create_all`；改已有表（`generation_run.usage_source`）走迁移 **v7**，SQL 冻结为字面量，`requires=("generation_run",)`。
- 流式接口的变更要**同批改完所有调用点与测试替身**，不留兼容层。
- 费用未定价时显示「未定价」，不显示 `$0`。
- 不写作者真实库；真实模型复验只用库副本，调用前确认阿里云百炼免费额度，只用 `qwen3.8-flash`。
- 不要用 `git stash`；不要擅自 rebase / 改写历史。
- 每个任务一个提交。

---

### Task 1: 分路解析纯函数（`runtime/routing.py`）

**Files:**
- Create: `backend/app/runtime/routing.py`
- Test: `backend/tests/test_routing.py`

**Interfaces:**
- Produces: `resolve_binding(*, version_binding, version_profile, task_type, routing, default_model) -> RoutingResult`，其中 `RoutingResult(binding: dict, profile: str, warnings: list[str])`；`normalize_routing_entry(value) -> dict`。
- Consumes: 无（纯函数）。

- [ ] **Step 1: 写失败测试**

`test_routing.py` 覆盖：
- 版本显式绑定 provider + model → 原样返回，不读分路。
- 版本只绑 model，分路有 provider → 补齐 provider。
- 版本什么都没绑，分路有 model → 取分路。
- 版本与分路都没有 model → 取 `default_model`；`default_model` 也没有 → `binding["model"]` 缺失（由调用方报错）。
- `param_profile`：版本为 `balanced` 且分路为 `strict` → `strict`；版本为 `creative` → 保持 `creative`。
- 未知 `task_type` 的分路键被忽略并给 warning。
- 分路值写成字符串（手改 settings.json）→ 当作 `{"model": 字符串}`。

- [ ] **Step 2: 实现**

```python
@dataclass(frozen=True)
class RoutingResult:
    binding: dict
    profile: str
    warnings: list[str]

_DEFAULT_PROFILE = "balanced"

def normalize_routing_entry(value) -> dict:
    if isinstance(value, str):
        return {"model": value} if value.strip() else {}
    if isinstance(value, dict):
        return dict(value)
    return {}

def resolve_binding(*, version_binding, version_profile, task_type, routing, default_model):
    vb = dict(version_binding or {})
    route = normalize_routing_entry((routing or {}).get(task_type))
    warnings = []
    ...
```

逐字段：`provider_id = vb.get("provider_id") or route.get("provider_id")`；`model = vb.get("model") or route.get("model") or default_model`；profile：`version_profile` 非空且不等于 `balanced` 时用它，否则 `route.get("param_profile") or version_profile or balanced`。

- [ ] **Step 3: 跑测试** `cd backend && uv run pytest tests/test_routing.py -q`

- [ ] **Step 4: 提交** `feat(runtime): 模型分路解析纯函数`

---

### Task 2: 参数档常量与合并（`runtime/params.py`）

**Files:**
- Create: `backend/app/runtime/params.py`
- Test: `backend/tests/test_params.py`

**Interfaces:**
- Produces: `PARAM_PROFILES`、`PARAM_PROFILE_LABELS`、`resolve_params(*, profile, default_params, override) -> tuple[dict, list[str]]`。
- Consumes: 无。

- [ ] **Step 1: 写失败测试**

- 三档各自返回对应 `temperature` / `top_p`。
- `default_params` 里的键保留（如 `max_tokens`）。
- 参数档覆盖 `default_params` 同名的 `temperature`。
- `override` 覆盖参数档。
- 未知档名 → 回落 `balanced` 且 warning 点出原名。
- 参数档不含 `max_tokens`。

- [ ] **Step 2: 实现**

```python
PARAM_PROFILES = {
    "strict": {"temperature": 0.2, "top_p": 0.8},
    "balanced": {"temperature": 0.7, "top_p": 0.9},
    "creative": {"temperature": 1.0, "top_p": 1.0},
}
PARAM_PROFILE_LABELS = {"strict": "严谨", "balanced": "平衡", "creative": "发散"}

def resolve_params(*, profile, default_params, override=None) -> tuple[dict, list[str]]:
    warnings = []
    name = profile or "balanced"
    if name not in PARAM_PROFILES:
        warnings.append(f"未知的参数档「{name}」，已按「平衡」处理")
        name = "balanced"
    merged = {**(default_params or {}), **PARAM_PROFILES[name], **(override or {})}
    return merged, warnings
```

- [ ] **Step 3: 跑测试** `cd backend && uv run pytest tests/test_params.py -q`

- [ ] **Step 4: 提交** `feat(runtime): 参数档常量与合并顺序`

---

### Task 3: 运行时接入分路与参数档

**Files:**
- Modify: `backend/app/services/runtime_service.py`
- Test: `backend/tests/test_runtime_service.py`

**Interfaces:**
- Consumes: `resolve_binding`、`resolve_params`。
- Changes: `resolve_provider(version)` → `resolve_provider(provider_id: str | None)`；`PreparedExecution` 增加 `profile: str`、`warnings: list[str]`。

- [ ] **Step 1: 写失败测试**

- 角色卡未绑模型、分路给 `write` 配了模型 → `prepare()` 的 `model` 为分路值。
- 角色卡绑 `creative`、全局默认 `balanced` → `params["temperature"] == 1.0`。
- 版本 `params={"max_tokens": 8000}` → 最终 params 里是 8000。
- 分路指向不存在的服务商 → `ValueError` 文案含分路键名与 provider id。
- 分路给的模型与角色卡显式模型冲突 → 角色卡赢。
- 未绑任何模型、分路也没有、`default_model` 也没有 → 报错文案含「模型分路」。

- [ ] **Step 2: 实现**

`prepare()` 里：

```python
settings = config.load_settings()
routing = settings.get("model_routing") or {}
resolved = resolve_binding(
    version_binding=binding,
    version_profile=version.param_profile,
    task_type=agent.task_type,
    routing=routing,
    default_model=settings.get("default_model"),
)
provider_id = resolved.binding.get("provider_id")
provider, base_url, api_key, prices = self.resolve_provider(provider_id)
model = resolved.binding.get("model")
if not model:
    raise ValueError(f"智能体「{agent.name}」还没有绑定模型，请在「智能体工作室」为它指定，或在「模型与费用」里为任务 {agent.task_type} 配置模型分路")
params, param_warnings = resolve_params(profile=resolved.profile, default_params=settings.get("default_params", {}), override=binding.get("params") or {})
```

`resolve_provider(provider_id)` 显式传入不存在时抛错（不再静默回落到第一家）：

```python
if provider_id:
    provider = self._session.get(Provider, provider_id)
    if provider is None:
        raise ValueError(f"模型分路指向的服务商不存在：{provider_id}")
    return ...
```

注意：角色卡**显式**绑了 provider_id 但该服务商被删的场景，原先也是静默回落；新行为是报错 —— 这正是 spec §3.2 要的。

- [ ] **Step 3: 跑测试** `cd backend && uv run pytest tests/test_runtime_service.py -q`，再跑全量。

- [ ] **Step 4: 提交** `feat(runtime): 分路与参数档接入执行链`

---

### Task 4: 流式客户端改为事件流 + usage

**Files:**
- Modify: `backend/app/runtime/llm.py`
- Modify: `backend/tests/test_llm.py`
- Modify: `backend/tests/test_text_api.py`（替身）
- Modify: `backend/app/api/text.py`

**Interfaces:**
- Produces: `StreamDelta(text)`、`StreamUsage(prompt_tokens, completion_tokens)`；`ChatClient.stream(...) -> AsyncIterator[StreamDelta | StreamUsage]`。
- Changes: `HttpxChatClient.stream` 发送 `stream_options: {"include_usage": True}`；遇 400 去掉该字段重试一次。

- [ ] **Step 1: 写失败测试**

- 正常流：先若干 `StreamDelta`，最后 `StreamUsage`，token 与 payload 一致。
- 无 usage 块：只有 delta，不产生 usage 事件。
- 首个响应 400（模拟服务商不认 `stream_options`）：去掉字段后重试成功，且**只重试一次**；断言第二次请求体不含 `stream_options`。
- 两次都 400：抛 `ChatFailure`，kind 为 `bad_request`。
- 中途断流：`ChatFailure.partial_text` 为已收到文本（既有断言保持）。

- [ ] **Step 2: 实现**

```python
@dataclass(frozen=True)
class StreamDelta:
    text: str

@dataclass(frozen=True)
class StreamUsage:
    prompt_tokens: int
    completion_tokens: int
```

`stream()` 内部：第一次带 `stream_options`；若 `response.status_code == 400` 且尚未 yield 过任何 delta，则以不带该字段的 body 重新发起一次；第二次的任何错误照常分类抛出。解析到 `chunk.get("usage")` 且非空时 yield `StreamUsage`。

- [ ] **Step 3: 改调用点**

`api/text.py` 的事件循环：

```python
usage: StreamUsage | None = None
async for event in prepared.client.stream(...):
    if isinstance(event, StreamUsage):
        usage = event
        continue
    parts.append(event.text)
    yield _sse("delta", {"text": event.text})
```

`usage()` 函数改为优先用 `usage` 对象；`done` 事件带 `"usage_source": "provider" if usage else "estimated"`。

`test_text_api.FakeStreamClient` 改为 yield `StreamDelta`；新增一个 yield `StreamUsage` 的变体。

- [ ] **Step 4: 跑测试** `cd backend && uv run pytest tests/test_llm.py tests/test_text_api.py -q`

- [ ] **Step 5: 提交** `feat(runtime): 流式返回 usage 事件`

---

### Task 5: `usage_source` 落库（迁移 v7）

**Files:**
- Modify: `backend/app/db/models/run.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/app/services/text_service.py`
- Modify: `backend/app/api/_serializers.py`
- Test: `backend/tests/test_migration_runner.py`
- Test: `backend/tests/test_runtime_service.py`
- Test: `backend/tests/test_text_api.py`

**Interfaces:**
- Produces: `GenerationRun.usage_source`；迁移 v7。
- Changes: `RunResult` 增加 `usage_source: str`；`finalize_run(...)` 增加 `usage_source`。

- [ ] **Step 1: 写失败测试**

- 模型默认 `usage_source == "estimated"`（存量语义）。
- 非流式且服务商返回 usage → `provider`；无 usage → `estimated`。
- 流式 `done` 事件与运行记录一致。
- 迁移 v7：存量库补列且盖章、二次启动不重复、`requires == ("generation_run",)`。

- [ ] **Step 2: 实现**

迁移：

```python
Migration(
    version=7,
    statements=(
        "ALTER TABLE generation_run ADD COLUMN usage_source VARCHAR(20) DEFAULT 'estimated' NOT NULL",
    ),
    requires=("generation_run",),
    note="记录 token 来自服务商还是估算",
)
```

`RunResult` 与 `execute_prepared` 里：`usage_source = "provider" if chat.usage_available else "estimated"`。`ChatResult` 增加 `usage_available: bool`（`llm.complete` 里按 payload 有没有 `usage` 判定）。

- [ ] **Step 3: 跑测试**，再跑全量。

- [ ] **Step 4: 提交** `feat(runtime): 记录 token 来源（迁移 v7）`

---

### Task 6: 模型单价表与解析

**Files:**
- Modify: `backend/app/db/models/config_models.py`
- Modify: `backend/app/runtime/pricing.py`
- Modify: `backend/app/services/provider_service.py`
- Modify: `backend/app/api/providers.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_model_price.py`
- Test: `backend/tests/test_model_price_api.py`

**Interfaces:**
- Produces: `ModelPrice` ORM；`resolve_prices(binding_prices, price_row)`；CRUD `list_prices / upsert_price / delete_price`；`GET/PUT/DELETE /api/model-prices`。
- Consumes: `Provider`。

- [ ] **Step 1: 写失败测试**

- 同名 `(provider_id, model)` 二次 upsert 更新而非插入第二行。
- 删除服务商级联删除单价。
- `resolve_prices`：binding 优先；无 binding 用表；都没有返回 `None`。
- API：列表按服务商分组返回；非法价格（负数）400；不存在的 provider 404。
- 运行落库时若用到单价，`cost_estimate` 与 `(prompt*in + completion*out)/1e6` 一致。

- [ ] **Step 2: 实现**

```python
class ModelPrice(IdMixin, TimestampMixin, Base):
    __tablename__ = "model_price"
    __table_args__ = (UniqueConstraint("provider_id", "model", name="uq_model_price"),)
    provider_id: Mapped[str] = mapped_column(ForeignKey("provider.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(120))
    input_price: Mapped[float] = mapped_column(Float, default=0.0)
    output_price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
```

`resolve_prices(binding_prices, price_row)` 落在 `runtime/pricing.py`（纯函数，接受 dict 或 None，不 import ORM）：

```python
def resolve_prices(binding_prices: dict | None, row: dict | None) -> dict | None:
    if binding_prices:
        return binding_prices
    if row:
        return {"input": row.get("input_price", 0.0), "output": row.get("output_price", 0.0)}
    return None
```

服务层负责把 ORM 行转成 dict 再传入。

- [ ] **Step 3: 接进执行链**

`resolve_provider` 返回值增加 `price_row`：按 `(provider.id, model)` 查单价（**model 在 provider 之后才能确定**，所以顺序调整为：先定 provider → 定 model → 查单价 → 合成 prices）。`PreparedExecution.prices = resolve_prices(binding.get("prices"), price_row_dict)`。

- [ ] **Step 4: 跑测试**，再跑全量。

- [ ] **Step 5: 提交** `feat(billing): 模型单价表与费用解析`

---

### Task 7: 三维费用汇总与预算提醒

**Files:**
- Modify: `backend/app/services/provider_service.py`
- Modify: `backend/app/api/providers.py`
- Modify: `backend/app/agents/roster.py`
- Test: `backend/tests/test_cost_summary.py`

**Interfaces:**
- Produces: `TASK_TYPE_LABELS`；`cost_summary(session, project_id) -> dict`（保留旧键，新增 `unpriced_runs` / `by_agent` / `by_task`）。
- Consumes: `ModelPrice`、`Agent`。

- [ ] **Step 1: 写失败测试**

- 两个智能体、三种任务类型 → `by_agent` / `by_task` 各分组求和正确。
- 一条运行用的模型没有单价 → 进 `unpriced_runs`，其 `cost_estimate` 仍按绑定 prices（若有）。
- 任务类型标签：`write → 正文`、`logic_check → 逻辑自检`；未知类型回落原键。
- 旧字段 `runs / prompt_tokens / completion_tokens / cost_estimate` 保持不变（兼容）。

- [ ] **Step 2: 实现**

`unpriced_runs` 口径：**该运行的模型当前没有单价行，且绑定里也没有 prices**。按 `(provider_id, model)` 集合一次性查出有价模型，再逐条判定，避免 N+1。

- [ ] **Step 3: 跑测试**，再跑全量。

- [ ] **Step 4: 提交** `feat(billing): 三维费用汇总与任务类型标签`

---

### Task 8: 调试台与前端

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/RunTrace.tsx`
- Modify: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/pages/Models.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Test: `frontend/src/lib/*.test.ts`（若有纯函数）

**Interfaces:**
- Consumes: Task 5/6/7 的接口与字段。

- [ ] **Step 1: 类型与展示**

- `RunView` 增加 `usage_source`；`CostSummary` 增加三维字段；`ProviderView` 不变；新增 `ModelPrice` 类型与 `api.listModelPrices / upsertModelPrice / deleteModelPrice`。
- `RunTrace`：token 行加「（估算）」角标；新增 `<details>` 显示 `run.params`。
- `Studio`：参数档下拉旁给出三档说明（严谨 0.2 / 平衡 0.7 / 发散 1.0）；底部加「最近运行」，按当前智能体调 `api.listRuns({agentId})`，点选展开 `RunTrace`。
- `Models`：新增「模型单价」表（服务商下拉 + 模型 + 输入 + 输出 + 币种 + 保存/删除）；费用区改为三个小表；未定价模型在聚合里显示「未定价 N 次」。
- `Dashboard`：`budget_alert` 有值且本项目费用超出时显示提示条。

- [ ] **Step 2: 跑前端测试与构建** `cd frontend && pnpm vitest run && pnpm build`

- [ ] **Step 3: 手工走查**（临时 `STORYFORGE_DATA_DIR`）：配置单价 → 跑一次调试台 → 费用三维出现；切参数档 → 运行详情里 `params.temperature` 变化；分路填 model → 未绑模型智能体的运行成功。

- [ ] **Step 4: 提交** `feat(frontend): 分路、参数档、单价与费用展示`

---

### Task 9: 文档同步与真实模型复验

**Files:**
- Modify: `CLAUDE.md`（§7 路线图、阶段记录、§8 变更记录）
- Create: `docs/superpowers/plans/2026-10-21-p3-walkthrough.md`

- [ ] **Step 1: 真实模型复验**（作者库副本，`qwen3.8-flash`）
  - 一次流式生成：`usage_source == "provider"` 且 token 与服务商返回一致。
  - 分路：给 `write` 配一个模型，删掉执笔版本上的 model 绑定 → 生成成功，运行记录的 model 等于分路值。
  - 分路指向不存在的服务商 → 报错文案含分路键名。
  - 参数档：把执笔版本改成 `creative` → 运行记录 `params` 里 `temperature == 1.0`。
- [ ] **Step 2: 走查记录与文档同步**
- [ ] **Step 3: 提交** `docs: P3 阶段记录与走查`

---

## 自检

| 检查 | 结果 |
|---|---|
| spec 每条验收标准都有任务覆盖 | 分路→T1/T3，参数档→T2/T3，记账→T4/T5，单价费用→T6/T7，调试台→T8，复验→T9 |
| 迁移只加一列，`requires` 正确 | v7，`requires=("generation_run",)` |
| 流式接口变更是否留了兼容层 | 不留；同批改完调用点与测试替身 |
| 是否引入重型依赖 | 无 |
