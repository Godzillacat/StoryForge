# P2a 执笔闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「场景卡 → 流式生成正文 → AI 草稿 → 整场 diff → 采纳 → 已采纳正文与修订快照」，并交付独立写作台。

**Architecture:** 复用现有运行时（槽位 → 预算 → 渲染 → 模型）并抽出可复用的准备步骤；新增一条 SSE 生成端点与正文三件套（`scene.body` / `scene_draft` / `scene_revision`）；前端新增 `/write` 三栏写作台，流式解析与行级 diff 下沉为可测纯函数。

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy + SQLite，React 19 + TypeScript + Vite + Tailwind，SSE 流式（`StreamingResponse` + `fetch` ReadableStream），vitest。

**Spec:** `docs/superpowers/specs/2026-10-18-p2a-writing-loop-design.md`

## Global Constraints

- 实施在隔离 worktree（建议 `worktree-p2a-writing-loop`，从本地 `master` 切出）；master 在收口前不动。
- 基线：后端 **381 passed**，前端 **18 passed**，`pnpm build` 干净。每个任务结束时不得低于基线。
- `api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI。
- 纯逻辑必须测（pytest / vitest）；**UI 不写自动化测试**。
- 标识符与代码用英文；注释、界面文案、提示词用中文。
- 迁移语句冻结为字面量；新表由 `create_all` 建，只有 `scene.body` 走迁移 v4。
- `scene.body` 是已采纳正文；AI 草稿永不自动写入正文（D-04）。
- 流式路径的 token 用 `estimate_tokens` 估算，并明确标注为估算值。
- 不写作者真实库；真实模型复验只用库副本与临时数据目录；调用前先确认阿里云百炼免费额度。
- 不要用 `git stash`；不要擅自 rebase / 改写历史。
- 每个任务一个提交（或按步骤中的提交点）；提交信息用中文、遵循 Conventional Commits 前缀。

---

### Task 1: 数据基础（正文列、草稿 / 修订表、字数函数、迁移 v4）

**Files:**
- Modify: `backend/app/db/models/chapter.py`（`Scene` 加 `body`）
- Create: `backend/app/db/models/text.py`
- Modify: `backend/app/db/models/__init__.py`
- Modify: `backend/app/db/migrations.py`（追加 v4）
- Create: `backend/app/text_stats.py`
- Create: `backend/tests/test_text_models.py`
- Modify: `backend/tests/test_migrations.py`
- Modify: `backend/tests/test_migration_runner.py`

**Interfaces:**
- Produces: `Scene.body: str | None`；`SceneDraft(id, scene_id, run_id, content, created_at, updated_at)`；`SceneRevision(id, scene_id, content, source, run_id, note, created_at, updated_at)`；`app.text_stats.count_words(text: str | None) -> int`；迁移 v4。

- [ ] **Step 1: 写失败测试（模型与字数）**

Create `backend/tests/test_text_models.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Chapter, Project, Scene, SceneDraft, SceneRevision, Volume
from app.db.session import SessionLocal
from app.text_stats import count_words


def _scene(session) -> Scene:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="找到录音带")
    session.add(scene)
    session.commit()
    return scene


def test_count_words_counts_non_whitespace_characters():
    assert count_words(None) == 0
    assert count_words("") == 0
    assert count_words("  \n\t") == 0
    assert count_words("他 说：\n你好") == 5
    assert count_words("Hello, 世界") == 8


def test_scene_body_defaults_to_none(session):
    scene = _scene(session)
    assert scene.body is None
    scene.body = "正文第一段。"
    session.commit()
    assert session.get(Scene, scene.id).body == "正文第一段。"


def test_draft_is_unique_per_scene(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="第一版"))
    session.commit()
    session.add(SceneDraft(scene_id=scene.id, content="第二版"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_revision_roundtrip(session):
    scene = _scene(session)
    revision = SceneRevision(
        scene_id=scene.id, content="旧稿", source="author", note="第一次保存"
    )
    session.add(revision)
    session.commit()

    stored = session.get(SceneRevision, revision.id)
    assert stored.content == "旧稿"
    assert stored.source == "author"
    assert stored.note == "第一次保存"
    assert stored.created_at is not None


def test_deleting_scene_cascades_draft_and_revision(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿"))
    session.add(SceneRevision(scene_id=scene.id, content="修订", source="ai"))
    session.commit()
    scene_id = scene.id

    session.delete(scene)
    session.commit()

    with SessionLocal() as fresh:
        assert fresh.query(SceneDraft).filter_by(scene_id=scene_id).count() == 0
        assert fresh.query(SceneRevision).filter_by(scene_id=scene_id).count() == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --directory backend pytest tests/test_text_models.py -q`
Expected: FAIL（`SceneDraft` / `SceneRevision` / `count_words` 不存在）。

- [ ] **Step 3: 实现模型与字数函数**

Modify `backend/app/db/models/chapter.py` — 在 `Scene` 的 `source_run_id` 后加：

```python
    body: Mapped[str | None] = mapped_column(Text, default=None)
```

Create `backend/app/db/models/text.py`:

```python
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class SceneDraft(IdMixin, TimestampMixin, Base):
    """每个场景至多一条可编辑的 AI 草稿；不污染已采纳正文（D-04）。"""

    __tablename__ = "scene_draft"
    __table_args__ = (UniqueConstraint("scene_id", name="uq_scene_draft_scene"),)

    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scene.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_run.id", ondelete="SET NULL"), default=None
    )
    content: Mapped[str] = mapped_column(Text, default="")


class SceneRevision(IdMixin, TimestampMixin, Base):
    """不可变修订快照：ai（采纳）/ author（保存）/ restore（恢复）。"""

    __tablename__ = "scene_revision"

    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scene.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="ai")
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_run.id", ondelete="SET NULL"), default=None
    )
    note: Mapped[str] = mapped_column(Text, default="")
```

Modify `backend/app/db/models/__init__.py` — 追加导入与 `__all__`：

```python
from app.db.models.text import SceneDraft, SceneRevision
```

（按该文件现有风格加入 `__all__`。）

Create `backend/app/text_stats.py`:

```python
"""正文统计的纯函数。"""

from __future__ import annotations


def count_words(text: str | None) -> int:
    """中文写作惯例：按非空白字符数计。空文本返回 0。"""
    if not text:
        return 0
    return sum(1 for char in text if not char.isspace())
```

- [ ] **Step 4: 运行模型测试确认通过**

Run: `uv run --directory backend pytest tests/test_text_models.py -q`
Expected: PASS（5 passed）。

- [ ] **Step 5: 追加迁移 v4 并更新迁移测试**

Modify `backend/app/db/migrations.py` — 在 `MIGRATIONS` 元组末尾追加：

```python
    Migration(
        version=4,
        note="scene 加已采纳正文列",
        statements=("ALTER TABLE scene ADD COLUMN body TEXT",),
    ),
```

Modify `backend/tests/test_migrations.py`:

```python
def test_the_first_real_migration_adds_the_character_columns():
    assert [m.version for m in migrations.MIGRATIONS] == [1, 2, 3, 4]

    step = migrations.MIGRATIONS[0]
    assert all(
        statement.startswith("ALTER TABLE setting_entry ADD COLUMN ")
        for statement in step.statements
    )
    assert migrations.latest_version() == 4
```

并追加：

```python
def test_v4_adds_the_scene_body_column():
    step = migrations.MIGRATIONS[3]
    assert step.statements == ("ALTER TABLE scene ADD COLUMN body TEXT",)
```

Modify `backend/tests/test_migration_runner.py` 的存量库用例
`test_the_character_columns_are_added_to_a_pre_existing_database`：

1. 在原始建表段追加一张**没有 body 列**的 `scene` 表：

```python
        conn.exec_driver_sql(
            "CREATE TABLE scene (id VARCHAR(36) PRIMARY KEY, chapter_id VARCHAR(36) NOT NULL,"
            " seq INTEGER NOT NULL DEFAULT 0, goal TEXT, conflict TEXT, turn TEXT,"
            " characters_json JSON, location_id VARCHAR(36), story_time VARCHAR(200),"
            " pov VARCHAR(100), target_words_min INTEGER, target_words_max INTEGER,"
            " status VARCHAR(20), source_run_id VARCHAR(36))"
        )
        conn.exec_driver_sql(
            "INSERT INTO scene (id, chapter_id, seq, goal)"
            " VALUES ('s1', 'c1', 0, '找到录音带')"
        )
```

2. 把版本断言改为：

```python
        assert conn.exec_driver_sql(
            "SELECT version FROM schema_migration ORDER BY version"
        ).fetchall() == [(0,), (1,), (2,), (3,), (4,)]
```

3. 追加断言：

```python
    scene_columns = {c["name"] for c in inspect(clean_db).get_columns("scene")}
    assert "body" in scene_columns
    with clean_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT goal, body FROM scene").fetchall() == [
            ("找到录音带", None)
        ]
```

- [ ] **Step 6: 运行迁移测试**

Run: `uv run --directory backend pytest tests/test_migrations.py tests/test_migration_runner.py -q`
Expected: PASS。若存量库用例因缺 `scene` 表失败，确认 Step 5 的原始建表段已加入。

- [ ] **Step 7: 跑全量并提交**

Run: `uv run --directory backend pytest -q`
Expected: 387 passed（381 + 6）。

```bash
git add backend/app/db/models/chapter.py backend/app/db/models/text.py backend/app/db/models/__init__.py backend/app/db/migrations.py backend/app/text_stats.py backend/tests/test_text_models.py backend/tests/test_migrations.py backend/tests/test_migration_runner.py
git commit -m "feat(db): 增加正文草稿与修订快照模型及迁移 v4"
```

---

### Task 2: 运行时准备步骤抽取

**Files:**
- Modify: `backend/app/runtime/execute.py`
- Modify: `backend/app/runtime/render.py`
- Modify: `backend/app/services/runtime_service.py`
- Test: `backend/tests/test_runtime_service.py`

**Interfaces:**
- Produces:
  - `PreparedPrompt(rendered_prompt, messages, trimmed, prompt_tokens, contents, over_budget, output_schema, error)`
  - `prepare_prompt(*, system_prompt, context_slots, output_schema, token_budget, source) -> PreparedPrompt`
  - `execute_prepared(prepared, *, config, params, prices, client, started=None) -> RunResult`
  - `RuntimeService.prepare_context(project_id, agent_id, extra=None) -> tuple[Agent, AgentVersion, PreparedPrompt]`
  - `RuntimeService.prepare(project_id, agent_id, extra=None) -> PreparedExecution`
  - `PreparedExecution(agent, version, provider, model, params, prices, config, prompt, client)`
- Consumes: `build_context`、`render`、`describe_contract`、`apply_contract`、`ChatClient`。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_runtime_service.py`:

```python
def test_prepare_returns_rendered_prompt_and_trimmed(session):
    project, _provider, agent, _version = _seed(session)
    prepared = RuntimeService(session).prepare(project.id, agent.id)

    assert "能听见死者遗言的验尸官" in prepared.prompt.rendered_prompt
    assert prepared.model == "test-model"
    assert prepared.prompt.messages == [
        {"role": "user", "content": prepared.prompt.rendered_prompt}
    ]
    assert prepared.prompt.trimmed == {}


def test_prepare_records_missing_variable_without_raising(session):
    project, _provider, agent, version = _seed(session)
    version.system_prompt = "缺少：{{ world_context }}"
    version.context_slots_json = ["raw_idea"]
    session.commit()

    prepared = RuntimeService(session).prepare(project.id, agent.id)

    assert prepared.prompt.error["kind"] == "template"
    assert "world_context" in prepared.prompt.error["message"]
    assert prepared.prompt.rendered_prompt == ""


def test_missing_optional_slot_renders_empty_for_plain_text():
    from app.runtime.execute import prepare_prompt

    class EmptySource:
        def scene_characters(self):
            return None

        def summarize(self, key, text):
            return text

    prepared = prepare_prompt(
        system_prompt="人物：{{ scene_characters }}",
        context_slots=["scene_characters"],
        output_schema=None,
        token_budget=8000,
        source=EmptySource(),
        allow_missing=True,
    )

    assert prepared.error is None
    assert prepared.rendered_prompt == "人物："
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_runtime_service.py -q`
Expected: FAIL（`RuntimeService.prepare` 不存在）。

- [ ] **Step 3: 重写 `backend/app/runtime/execute.py`**

用以下实现替换文件（保留 `ExecuteInput` / `RunResult` 的形状）：

```python
"""运行时编排：槽位收集 → 预算裁剪 → 提示词渲染 → 模型调用 → 契约校验。

这里不碰数据库、不碰 FastAPI。准备步骤与执行步骤拆开，流式路径复用同一个
渲染结果；落库仍由 services 层负责。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.runtime.context import SlotSource, build_context
from app.runtime.contract import describe_contract
from app.runtime.llm import ChatClient, ChatConfig, ChatFailure
from app.runtime.pricing import compute_cost, estimate_tokens
from app.runtime.render import MissingVariableError, render
from app.runtime.schema import apply_contract


@dataclass(frozen=True)
class ExecuteInput:
    project_id: str
    agent_id: str
    version_id: str
    provider_id: str | None
    model: str
    base_url: str
    api_key: str
    params: dict
    system_prompt: str
    context_slots: list[str]
    output_schema: dict | None
    token_budget: int
    prices: dict | None = None


@dataclass(frozen=True)
class PreparedPrompt:
    rendered_prompt: str
    messages: list[dict]
    trimmed: dict[str, str]
    prompt_tokens: int
    contents: dict[str, str]
    over_budget: bool
    output_schema: dict | None
    error: dict | None = None


@dataclass(frozen=True)
class RunResult:
    rendered_prompt: str
    raw_output: str
    parsed: Any | None
    structured: bool
    parse_error: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float
    duration_ms: int
    status: str  # ok | partial | error
    error: dict | None
    trimmed: dict[str, str]


def prepare_prompt(
    *,
    system_prompt: str,
    context_slots: list[str],
    output_schema: dict | None,
    token_budget: int,
    source: SlotSource,
    allow_missing: bool = False,
) -> PreparedPrompt:
    bundle = build_context(context_slots, source, token_budget)
    try:
        rendered = render(
            system_prompt, bundle.contents, allow_missing=allow_missing
        )
    except MissingVariableError as exc:
        return PreparedPrompt(
            rendered_prompt="",
            messages=[],
            trimmed=bundle.trimmed,
            prompt_tokens=0,
            contents=bundle.contents,
            over_budget=bundle.over_budget,
            output_schema=output_schema,
            error={"kind": "template", "message": str(exc)},
        )

    contract_block = describe_contract(output_schema)
    if contract_block:
        rendered = f"{rendered}\n\n{contract_block}"

    return PreparedPrompt(
        rendered_prompt=rendered,
        messages=[{"role": "user", "content": rendered}],
        trimmed=bundle.trimmed,
        prompt_tokens=estimate_tokens(rendered),
        contents=bundle.contents,
        over_budget=bundle.over_budget,
        output_schema=output_schema,
    )


def _failure(
    prepared: PreparedPrompt,
    started: float,
    message: str,
    *,
    kind: str = "runtime",
    status: str = "error",
    raw_output: str = "",
    prices: dict | None = None,
) -> RunResult:
    prompt_tokens = estimate_tokens(prepared.rendered_prompt)
    completion_tokens = estimate_tokens(raw_output)
    return RunResult(
        rendered_prompt=prepared.rendered_prompt,
        raw_output=raw_output,
        parsed=None,
        structured=False,
        parse_error=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate=compute_cost(prompt_tokens, completion_tokens, prices),
        duration_ms=int((time.monotonic() - started) * 1000),
        status=status,
        error={"kind": kind, "message": message},
        trimmed=prepared.trimmed,
    )


async def execute_prepared(
    prepared: PreparedPrompt,
    *,
    config: ChatConfig,
    params: dict,
    prices: dict | None,
    client: ChatClient,
    started: float | None = None,
) -> RunResult:
    started_at = time.monotonic() if started is None else started
    if prepared.error:
        return _failure(
            prepared,
            started_at,
            prepared.error["message"],
            kind=prepared.error["kind"],
            prices=prices,
        )

    try:
        chat = await client.complete(config, prepared.messages, params)
    except ChatFailure as exc:
        return _failure(
            prepared,
            started_at,
            exc.error.message,
            kind=exc.error.kind,
            status="partial" if exc.partial_text else "error",
            raw_output=exc.partial_text,
            prices=prices,
        )

    parsed, structured, parse_error = apply_contract(
        chat.text, prepared.output_schema
    )
    completion_tokens = chat.completion_tokens or estimate_tokens(chat.text)
    prompt_tokens = chat.prompt_tokens or prepared.prompt_tokens
    return RunResult(
        rendered_prompt=prepared.rendered_prompt,
        raw_output=chat.text,
        parsed=parsed,
        structured=structured,
        parse_error=parse_error,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate=compute_cost(prompt_tokens, completion_tokens, prices),
        duration_ms=int((time.monotonic() - started_at) * 1000),
        status="ok",
        error=None,
        trimmed=prepared.trimmed,
    )


async def execute_run(inp: ExecuteInput, source: SlotSource, client: ChatClient) -> RunResult:
    started = time.monotonic()
    prepared = prepare_prompt(
        system_prompt=inp.system_prompt,
        context_slots=inp.context_slots,
        output_schema=inp.output_schema,
        token_budget=inp.token_budget,
        source=source,
    )
    return await execute_prepared(
        prepared,
        config=ChatConfig(base_url=inp.base_url, api_key=inp.api_key, model=inp.model),
        params=inp.params,
        prices=inp.prices,
        client=client,
        started=started,
    )
```

注意：`_failure` 的成本按既有行为由 `execute_prepared` 外层的 `compute_cost` 负责仅在成功路径；失败路径原实现会计算成本，但 token 为空时结果也是 0。若既有测试断言失败路径成本，按测试调整；当前 `test_execute.py` 未断言失败成本。

- [ ] **Step 4: 给渲染器加「可选槽位」容错**

Modify `backend/app/runtime/render.py`：

```python
def render(
    template: str,
    context: dict[str, str],
    *,
    allow_missing: bool = False,
) -> str:
    missing: list[str] = []

    def _substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in context:
            missing.append(name)
            if allow_missing:
                return ""
            return match.group(0)
        return context[name]

    rendered = _VAR_RE.sub(_substitute, template)
    if missing and not allow_missing:
        raise MissingVariableError(f"提示词引用了未提供的变量：{'、'.join(sorted(set(missing)))}")
    return rendered
```

- [ ] **Step 5: 重写 `RuntimeService` 的准备与执行**

Modify `backend/app/services/runtime_service.py`：

顶部导入追加：

```python
from dataclasses import dataclass

from app.runtime.execute import (
    ExecuteInput,
    PreparedPrompt,
    RunResult,
    execute_prepared,
    prepare_prompt,
)
from app.runtime.llm import ChatClient, ChatConfig, HttpxChatClient
```

追加数据类与常量（放在 `RuntimeService` 前）：

```python
@dataclass(frozen=True)
class PreparedExecution:
    agent: Agent
    version: AgentVersion
    provider: Provider
    model: str
    params: dict
    prices: dict | None
    config: ChatConfig
    prompt: PreparedPrompt
    client: ChatClient
```

把 `execute()` 替换为：

```python
    def prepare_context(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> tuple[Agent, AgentVersion, PreparedPrompt]:
        agent = self._session.get(Agent, agent_id)
        if agent is None:
            raise ValueError(f"智能体不存在：{agent_id}")
        if not agent.current_version_id:
            raise ValueError(f"智能体「{agent.name}」没有可用版本")
        version = self._session.get(AgentVersion, agent.current_version_id)
        if version is None:
            raise ValueError(f"智能体「{agent.name}」的当前版本已丢失")

        settings = config.load_settings()
        source = DbSlotSource(self._session, project_id, extra_slots=extra)
        prompt = prepare_prompt(
            system_prompt=version.system_prompt,
            context_slots=version.context_slots_json or [],
            output_schema=version.output_schema_json,
            token_budget=int(settings.get("context_token_budget", 8000)),
            source=source,
            # 没有输出契约的预置是纯文本执笔：首场天然可能没有人物、检索结果
            # 或前情正文，缺槽位按空串渲染；结构化预置仍严格报缺变量。
            allow_missing=version.output_schema_json is None,
        )
        return agent, version, prompt

    def prepare(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> PreparedExecution:
        agent, version, prompt = self.prepare_context(project_id, agent_id, extra)
        provider, base_url, api_key, prices = self.resolve_provider(version)
        binding = version.model_binding_json or {}
        settings = config.load_settings()

        model = binding.get("model") or settings.get("default_model")
        if not model:
            raise ValueError(
                f"智能体「{agent.name}」还没有绑定模型，请先在「智能体工作室」为它指定一个"
            )
        params = {
            **settings.get("default_params", {}),
            **(binding.get("params") or {}),
        }
        return PreparedExecution(
            agent=agent,
            version=version,
            provider=provider,
            model=model,
            params=params,
            prices=prices,
            config=ChatConfig(base_url=base_url, api_key=api_key, model=model),
            prompt=prompt,
            client=self._resolve_client(self._resolve_timeout(binding)),
        )

    def execute(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> tuple[GenerationRun, RunResult]:
        prepared = self.prepare(project_id, agent_id, extra)
        result = _run_sync(
            execute_prepared,
            prepared.prompt,
            config=prepared.config,
            params=prepared.params,
            prices=prepared.prices,
            client=prepared.client,
        )
        run = self._persist_run(project_id, prepared, result)
        return run, result

    def _persist_run(
        self, project_id: str, prepared: PreparedExecution, result: RunResult
    ) -> GenerationRun:
        run = GenerationRun(
            project_id=project_id,
            agent_id=prepared.agent.id,
            agent_version_id=prepared.version.id,
            provider_id=prepared.provider.id,
            model=prepared.model,
            params_json=prepared.params,
            rendered_prompt=result.rendered_prompt,
            raw_output=result.raw_output,
            parsed_json=result.parsed,
            structured=result.structured,
            parse_error=result.parse_error,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_estimate=result.cost_estimate,
            duration_ms=result.duration_ms,
            status=result.status,
            error_json=result.error,
            trimmed_json=result.trimmed,
        )
        self._session.add(run)
        self._session.commit()
        return run
```

把 `_run_sync` 改为支持关键字参数：

```python
def _run_sync(coro_factory, *args, **kwargs):
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory(*args, **kwargs))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro_factory(*args, **kwargs)).result()
```

删除不再使用的 `ExecuteInput` 组装与旧 `execute` 主体；`estimate_tokens` 若不再使用则删除导入。

- [ ] **Step 6: 跑相关测试与全量**

Run: `uv run --directory backend pytest tests/test_execute.py tests/test_runtime_service.py tests/test_api.py -q`
Expected: PASS（行为不变 + 3 条新测试）。

Run: `uv run --directory backend pytest -q`
Expected: 390 passed。

- [ ] **Step 7: 提交**

```bash
git add backend/app/runtime/execute.py backend/app/services/runtime_service.py backend/tests/test_runtime_service.py
git commit -m "refactor(runtime): 抽出可复用的执行准备步骤"
```

---

### Task 3: 三个上下文槽位

**Files:**
- Modify: `backend/app/runtime/context.py`
- Modify: `backend/app/services/slot_source.py`
- Test: `backend/tests/test_slot_source.py`
- Test: `backend/tests/test_context.py`

**Interfaces:**
- Produces:
  - 槽位 `scene_card`（永不裁剪）、`scene_characters`（永不裁剪）、`recent_text`（中优先）。
  - `DbSlotSource.scene_card() / scene_characters() / recent_text()`。
  - `scene_search_query(session, project_id, scene) -> str`。
- Consumes: `Scene.body`、`Scene.characters_json`、`Foreshadow`、`CHARACTER_FIELDS`、`ENTRY_TYPES`。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_slot_source.py`:

```python
def _scene_fixture(session):
    from app.db.models import Chapter, Foreshadow, Scene, SettingEntry, Volume

    project = _seed(session)
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(
        volume_id=volume.id, seq=0, title="第一章", pov="陈默", summary="本章摘要"
    )
    session.add(chapter)
    session.commit()
    character = SettingEntry(
        project_id=project.id,
        type="character",
        name="陈默",
        aliases_json=["阿默"],
        desire="找回记忆",
        fear="想起真相",
        current_state="暂居南滨",
        speech_style="话少",
    )
    place = SettingEntry(project_id=project.id, type="place", name="南滨旧城")
    session.add_all([character, place])
    session.commit()
    first = Scene(
        chapter_id=chapter.id,
        seq=0,
        goal="开场",
        body="第一场的正文，风和雨。",
    )
    scene = Scene(
        chapter_id=chapter.id,
        seq=1,
        goal="找到录音带",
        conflict="档案室有人",
        turn="录音带里是自己的声音",
        characters_json=[character.id],
        location_id=place.id,
        story_time="第三年·春",
        pov="陈默",
        target_words_min=800,
        target_words_max=1500,
    )
    session.add_all([first, scene])
    session.commit()
    session.add(
        Foreshadow(
            project_id=project.id,
            name="失忆的录音带",
            plant_scene_id=scene.id,
            plan_pay_scene_id=first.id,
        )
    )
    session.commit()
    return project, scene


def test_scene_card_contains_full_card_and_foreshadow_names(session):
    project, scene = _scene_fixture(session)
    source = DbSlotSource(session, project.id, extra_slots={"scene_id": scene.id})
    text = source.scene_card()

    assert "找到录音带" in text
    assert "档案室有人" in text
    assert "录音带里是自己的声音" in text
    assert "陈默" in text and "南滨旧城" in text
    assert "第三年·春" in text
    assert "800–1500" in text
    assert "失忆的录音带" in text


def test_scene_characters_returns_full_character_cards_only(session):
    project, scene = _scene_fixture(session)
    source = DbSlotSource(session, project.id, extra_slots={"scene_id": scene.id})
    text = source.scene_characters()

    assert "陈默" in text and "阿默" in text
    assert "找回记忆" in text
    assert "想起真相" in text
    assert "暂居南滨" in text
    assert "话少" in text
    assert "南滨旧城" not in text


def test_recent_text_keeps_the_tail_of_the_previous_scenes(session):
    project, scene = _scene_fixture(session)
    source = DbSlotSource(session, project.id, extra_slots={"scene_id": scene.id})
    assert "第一场的正文" in source.recent_text()

    # 当前场景之前没有别的正文时返回 None
    empty = DbSlotSource(session, project.id, extra_slots={"scene_id": scene.id})
    from app.db.models import Scene

    first = session.query(Scene).filter_by(chapter_id=scene.chapter_id, seq=0).one()
    first.body = None
    session.commit()
    assert empty.recent_text() is None


def test_scene_card_and_characters_return_none_without_scene(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert source.scene_card() is None
    assert source.scene_characters() is None
    assert source.recent_text() is None


def test_scene_search_query_uses_goal_conflict_turn_and_names(session):
    from app.services.slot_source import scene_search_query

    project, scene = _scene_fixture(session)
    query = scene_search_query(session, project.id, scene)
    assert "找到录音带" in query
    assert "档案室有人" in query
    assert "陈默" in query
    assert "南滨旧城" in query
```

追加到 `backend/tests/test_context.py`（按现有断言风格）:

```python
def test_new_writing_slots_are_registered():
    from app.runtime.context import SLOT_REGISTRY

    assert SLOT_REGISTRY["scene_card"].over_budget == "never"
    assert SLOT_REGISTRY["scene_characters"].over_budget == "never"
    assert SLOT_REGISTRY["recent_text"].key == "recent_text"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_slot_source.py tests/test_context.py -q`
Expected: FAIL（槽位方法不存在）。

- [ ] **Step 3: 注册槽位与协议**

Modify `backend/app/runtime/context.py`：

1. `SlotSource` 协议追加：

```python
    def scene_card(self) -> str | None: ...
    def scene_characters(self) -> str | None: ...
    def recent_text(self) -> str | None: ...
```

2. `SLOT_REGISTRY` 追加：

```python
        SlotSpec("scene_card", "当前场景卡", P_NEVER, "never"),
        SlotSpec("scene_characters", "出场人物完整卡", P_NEVER, "never"),
        SlotSpec("recent_text", "最近已采纳正文", P_MID, "drop"),
```

- [ ] **Step 4: 实现槽位取数**

Modify `backend/app/services/slot_source.py`：

1. 导入 `CHARACTER_FIELDS`（现有已导入 `ENTRY_TYPES, HARDNESS_LEVELS`）：

```python
from app.world_types import CHARACTER_FIELDS, ENTRY_TYPES, HARDNESS_LEVELS
```

2. 在 `_chapter()` 后追加：

```python
    def _scene_chain(self) -> tuple[Scene, Chapter, Volume] | None:
        scene_id = self._extra.get("scene_id")
        if not scene_id:
            return None
        scene = self._session.get(Scene, scene_id)
        if scene is None:
            return None
        chapter = self._session.get(Chapter, scene.chapter_id)
        if chapter is None:
            return None
        volume = self._session.get(Volume, chapter.volume_id)
        if volume is None or volume.project_id != self._project_id:
            return None
        return scene, chapter, volume

    def _scene_entries(self) -> dict[str, SettingEntry]:
        return {
            entry.id: entry
            for entry in self._session.scalars(
                select(SettingEntry).where(SettingEntry.project_id == self._project_id)
            )
        }

    def scene_card(self) -> str | None:
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, chapter, volume = chain
        entries = self._scene_entries()
        people = [
            entries[item].name
            for item in (scene.characters_json or [])
            if item in entries
        ]
        location = entries.get(scene.location_id).name if scene.location_id in entries else ""
        foreshadows = self._session.scalars(
            select(Foreshadow).where(Foreshadow.project_id == self._project_id)
        ).all()
        plants = [row.name for row in foreshadows if row.plant_scene_id == scene.id]
        pays = [row.name for row in foreshadows if row.plan_pay_scene_id == scene.id]

        lines = [
            f"第{volume.seq + 1}卷 {volume.name} / 第{chapter.seq + 1}章 {chapter.title} / 场景{scene.seq + 1}",
            f"目标：{scene.goal or '（未写目标）'}",
        ]
        if scene.conflict:
            lines.append(f"冲突：{scene.conflict}")
        if scene.turn:
            lines.append(f"转折：{scene.turn}")
        if people:
            lines.append("出场人物：" + "、".join(people))
        if location:
            lines.append("地点：" + location)
        if scene.story_time:
            lines.append("故事内时间：" + scene.story_time)
        pov = scene.pov or chapter.pov
        if pov:
            lines.append("视角：" + pov)
        if scene.target_words_min is not None or scene.target_words_max is not None:
            lines.append(
                f"目标字数：{scene.target_words_min or '?'}–{scene.target_words_max or '?'}"
            )
        if plants:
            lines.append("埋设伏笔：" + "、".join(plants))
        if pays:
            lines.append("计划回收伏笔：" + "、".join(pays))
        return "\n".join(lines)

    def scene_characters(self) -> str | None:
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, _chapter, _volume = chain
        entries = self._scene_entries()
        lines: list[str] = []
        for item in scene.characters_json or []:
            entry = entries.get(item)
            if entry is None or entry.type != "character":
                continue
            parts = [f"【人物】{entry.name}"]
            if entry.aliases_json:
                parts.append("别名与称呼：" + "、".join(entry.aliases_json))
            if entry.summary:
                parts.append("概述：" + entry.summary)
            if entry.description:
                parts.append("说明：" + entry.description)
            for key, (label, _multiline) in CHARACTER_FIELDS.items():
                value = getattr(entry, key, None)
                if value:
                    parts.append(f"{label}：" + str(value))
            lines.append("；".join(parts))
        return "\n".join(lines) or None

    def recent_text(self) -> str | None:
        chain = self._scene_chain()
        if chain is None:
            return None
        scene, chapter, _volume = chain
        previous = self._session.scalars(
            select(Scene)
            .where(Scene.chapter_id == chapter.id, Scene.seq < scene.seq)
            .order_by(Scene.seq.desc())
        ).all()
        chunks = [
            item.body.strip()
            for item in previous
            if item.body and item.body.strip()
        ][:2]
        if not chunks:
            return None
        text = "\n\n".join(reversed(chunks))
        if len(text) > 1200:
            return "……" + text[-1200:]
        return text
```

3. 文件末尾追加模块函数：

```python
def scene_search_query(session: Session, project_id: str, scene: Scene) -> str:
    """用场景卡里的情节词与实体名拼检索词。"""
    entries = {
        entry.id: entry.name
        for entry in session.scalars(
            select(SettingEntry).where(SettingEntry.project_id == project_id)
        )
    }
    parts = [scene.goal or "", scene.conflict or "", scene.turn or ""]
    parts.extend(entries.get(item, "") for item in (scene.characters_json or []))
    if scene.location_id:
        parts.append(entries.get(scene.location_id, ""))
    return " ".join(part.strip() for part in parts if part and part.strip())
```

- [ ] **Step 5: 跑测试与全量**

Run: `uv run --directory backend pytest tests/test_slot_source.py tests/test_context.py -q`
Expected: PASS。

Run: `uv run --directory backend pytest -q`
Expected: 396 passed（390 + 6）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/runtime/context.py backend/app/services/slot_source.py backend/tests/test_slot_source.py backend/tests/test_context.py
git commit -m "feat(context): 增加场景卡、出场人物与最近正文槽位"
```

---

### Task 4: 执笔预置智能体

**Files:**
- Modify: `backend/app/agents/roster.py`
- Test: `backend/tests/test_roster.py`
- Test: `backend/tests/test_seed_service.py`

**Interfaces:**
- Produces: 预置 `writer`（`task_type=write`，`output_schema=None`，槽位见 spec §4.5）。既有库启动时由 `seed_agents` 自动补建。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_roster.py`:

```python
def test_writer_is_in_the_default_roster():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "writer")
    assert entry["name"] == "执笔"
    assert entry["task_type"] == "write"
    assert entry["output_schema"] is None
    assert entry["param_profile"] == "balanced"
    assert entry["trigger_mode"] == "manual"
    assert entry["context_slots"] == [
        "project_core",
        "story_bible",
        "world_context",
        "volume_outline",
        "chapter_outline",
        "timeline",
        "scene_card",
        "scene_characters",
        "related_settings",
        "recent_text",
    ]


def test_writer_prompt_is_plain_prose_not_json():
    entry = next(e for e in DEFAULT_ROSTER if e["key"] == "writer")
    prompt = entry["system_prompt"]
    assert "场景卡" in prompt
    assert "不要用代码块" in prompt
    assert "JSON" not in prompt
    assert entry["output_schema"] is None
```

追加到 `backend/tests/test_seed_service.py`:

```python
def test_seed_creates_the_writer_agent(session):
    seed_agents(session)
    writer = session.query(Agent).filter_by(task_type="write").one()
    assert writer.name == "执笔"
    version = session.get(AgentVersion, writer.current_version_id)
    assert version.output_schema_json is None
    assert "scene_card" in version.context_slots_json
```

执笔是首个**没有输出契约**的预置。`test_roster.py` 里有两条遍历全部预置、默认每个都有 schema 的测试，必须跳过纯文本预置：

1. `test_contract_block_covers_every_field_of_every_preset_agent`：在 `for entry in DEFAULT_ROSTER:` 之后、`schema = entry["output_schema"]` 之前插入：

```python
        if not entry["output_schema"]:
            continue
```

2. `test_every_schema_property_carries_a_chinese_title`：在 `for entry in DEFAULT_ROSTER:` 之后、`walk(entry["output_schema"], entry["key"])` 之前插入同一行。

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: FAIL（找不到 writer）。

- [ ] **Step 3: 写预置提示词与阵容项**

Modify `backend/app/agents/roster.py` — 在 `SCENE_PLANNER_PROMPT` 后追加：

```python
WRITER_PROMPT = """你是长篇小说执笔，服务对象是作者。你的任务是把当前场景卡写成可以直接进入小说正文的段落。

【项目信息】
{{ project_core }}

【故事圣经】
{{ story_bible }}

【世界观】
{{ world_context }}

【本卷纲要】
{{ volume_outline }}

【本章章纲】
{{ chapter_outline }}

【故事内时间线】
{{ timeline }}

【当前场景卡】
{{ scene_card }}

【出场人物】
{{ scene_characters }}

【相关设定】
{{ related_settings }}

【前情正文】
{{ recent_text }}

要求：
1. 只写这一场，不写章节标题、不写第几章、不写任何解释、提纲或创作说明；
2. 严格按场景卡的目标、冲突、转折、视角与目标字数写，写到转折落地就停；
3. 人物、地点与专有名词一律使用材料里的标准名或已有称呼，不新造名词；
4. 保持章纲与项目的调性，对白与叙述自然，不总结剧情、不评论人物；
5. 输出纯文本段落，段落之间空一行；不要用代码块包裹整篇正文；
6. 材料不足时按已有信息写，不要停下来提问；不确定的地方写得保守些。"""
```

在 `DEFAULT_ROSTER` 末尾追加：

```python
    {
        "key": "writer",
        "name": "执笔",
        "role_label": "正文",
        "color": "#ec4899",
        "task_type": "write",
        "system_prompt": WRITER_PROMPT,
        "context_slots": [
            "project_core",
            "story_bible",
            "world_context",
            "volume_outline",
            "chapter_outline",
            "timeline",
            "scene_card",
            "scene_characters",
            "related_settings",
            "recent_text",
        ],
        "output_schema": None,
        "param_profile": "balanced",
        "trigger_mode": "manual",
        "note": "按场景卡写正文；只出草稿，采纳才入稿。",
    },
```

- [ ] **Step 4: 跑测试**

Run: `uv run --directory backend pytest tests/test_roster.py tests/test_seed_service.py -q`
Expected: PASS。现有 `test_preset_prompts_do_not_hand_list_field_keys` 必须保持绿；若它报出英文词，删掉提示词里对应的英文（只留中文）。

- [ ] **Step 5: 全量与提交**

Run: `uv run --directory backend pytest -q`
Expected: 399 passed（396 + 3）。

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py backend/tests/test_seed_service.py
git commit -m "feat(agents): 增加执笔预置智能体"
```

---

### Task 5: text_service（草稿、正文、修订、采纳、恢复）

**Files:**
- Create: `backend/app/services/text_service.py`
- Test: `backend/tests/test_text_service.py`

**Interfaces:**
- Produces:
  - `GenerationSpec(project_id, scene_id, prepared)`
  - `get_text(session, scene_id) -> dict`
  - `save_body(session, scene_id, content) -> dict`
  - `save_draft(session, scene_id, content) -> dict`
  - `discard_draft(session, scene_id) -> None`
  - `adopt_draft(session, scene_id) -> dict`
  - `list_revisions(session, scene_id) -> list[dict]`
  - `get_revision(session, scene_id, revision_id) -> dict`
  - `restore_revision(session, scene_id, revision_id) -> dict`
  - `prepare_generation(session, scene_id) -> GenerationSpec`
  - `create_run(spec) -> str`
  - `finalize_run(run_id, scene_id, *, content, status, prompt_tokens, completion_tokens, cost_estimate, duration_ms, error) -> str | None`
- Consumes: `RuntimeService.prepare`、`scene_search_query`、`count_words`、`mark_dirty`。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_text_service.py`:

```python
import pytest

from app.db.models import (
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SceneDraft,
    SceneRevision,
    Volume,
)
from app.services import text_service


def _scene(session) -> Scene:
    project = Project(name="雾港")
    session.add(project)
    session.commit()
    volume = Volume(project_id=project.id, seq=0, name="第一卷")
    session.add(volume)
    session.commit()
    chapter = Chapter(volume_id=volume.id, seq=0, title="第一章")
    session.add(chapter)
    session.commit()
    scene = Scene(chapter_id=chapter.id, seq=0, goal="找到录音带")
    session.add(scene)
    session.commit()
    return scene


def test_get_text_starts_empty(session):
    scene = _scene(session)
    state = text_service.get_text(session, scene.id)
    assert state["body"] is None
    assert state["has_body"] is False
    assert state["word_count"] == 0
    assert state["draft"] is None
    assert state["revisions"] == []


def test_save_body_creates_one_author_revision_only_when_changed(session):
    scene = _scene(session)
    first = text_service.save_body(session, scene.id, "第一段。")
    assert first["body"] == "第一段。"
    assert first["has_body"] is True
    assert first["word_count"] == 4
    assert len(first["revisions"]) == 1
    assert first["revisions"][0]["source"] == "author"

    second = text_service.save_body(session, scene.id, "第一段。")
    assert len(second["revisions"]) == 1

    third = text_service.save_body(session, scene.id, "第二段。")
    assert len(third["revisions"]) == 2
    assert third["body"] == "第二段。"


def test_draft_edit_and_discard(session):
    scene = _scene(session)
    session.add(SceneDraft(scene_id=scene.id, content="草稿"))
    session.commit()

    saved = text_service.save_draft(session, scene.id, "改过的草稿")
    assert saved["content"] == "改过的草稿"

    text_service.discard_draft(session, scene.id)
    assert text_service.get_text(session, scene.id)["draft"] is None


def test_save_draft_without_draft_is_an_error(session):
    scene = _scene(session)
    with pytest.raises(ValueError, match="草稿已被替换或删除"):
        text_service.save_draft(session, scene.id, "x")


def test_adopt_requires_a_non_empty_draft(session):
    scene = _scene(session)
    with pytest.raises(ValueError, match="当前没有可采纳的草稿"):
        text_service.adopt_draft(session, scene.id)

    session.add(SceneDraft(scene_id=scene.id, content="   "))
    session.commit()
    with pytest.raises(ValueError, match="草稿为空"):
        text_service.adopt_draft(session, scene.id)


def test_adopt_writes_body_and_ai_revision_and_deletes_draft(session):
    scene = _scene(session)
    run = GenerationRun(project_id=None, status="ok")
    session.add(run)
    session.commit()
    session.add(SceneDraft(scene_id=scene.id, content="采纳的正文。", run_id=run.id))
    session.commit()

    state = text_service.adopt_draft(session, scene.id)

    assert state["body"] == "采纳的正文。"
    assert state["draft"] is None
    assert state["revisions"][0]["source"] == "ai"
    assert state["revisions"][0]["run_id"] == run.id


def test_restore_creates_a_restore_revision(session):
    scene = _scene(session)
    text_service.save_body(session, scene.id, "旧版正文。")
    old = text_service.get_text(session, scene.id)["revisions"][0]

    text_service.save_body(session, scene.id, "新版正文。")
    state = text_service.restore_revision(session, scene.id, old["id"])

    assert state["body"] == "旧版正文。"
    sources = [row["source"] for row in state["revisions"]]
    assert sources[0] == "restore"
    assert "恢复自修订" in state["revisions"][0]["note"]


def test_revisions_are_scoped_to_the_scene(session):
    scene = _scene(session)
    other = Scene(chapter_id=scene.chapter_id, seq=1, goal="另一场")
    session.add(other)
    session.commit()
    text_service.save_body(session, other.id, "别的正文。")
    revision = text_service.get_text(session, other.id)["revisions"][0]

    with pytest.raises(ValueError, match="修订不存在"):
        text_service.get_revision(session, scene.id, revision["id"])
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_text_service.py -q`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 text_service**

Create `backend/app/services/text_service.py`:

```python
"""正文、AI 草稿与修订快照。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Chapter,
    GenerationRun,
    Project,
    Scene,
    SceneDraft,
    SceneRevision,
    Volume,
)
from app.db.session import SessionLocal
from app.services import agent_service, chapter_service, search_service
from app.services.runtime_service import PreparedExecution, RuntimeService
from app.services.slot_source import scene_search_query
from app.text_stats import count_words

_PREVIEW_LIMIT = 80


@dataclass(frozen=True)
class GenerationSpec:
    project_id: str
    scene_id: str
    prepared: PreparedExecution


def _scene(session: Session, scene_id: str) -> Scene:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    return scene


def _project(session: Session, scene: Scene) -> Project:
    return chapter_service.get_project_for_chapter(session, scene.chapter_id)


def _draft(session: Session, scene_id: str) -> SceneDraft | None:
    return session.scalars(
        select(SceneDraft).where(SceneDraft.scene_id == scene_id)
    ).first()


def _draft_out(draft: SceneDraft) -> dict:
    return {
        "id": draft.id,
        "content": draft.content,
        "run_id": draft.run_id,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else "",
    }


def _revision_summary(revision: SceneRevision) -> dict:
    text = revision.content or ""
    preview = text if len(text) <= _PREVIEW_LIMIT else text[:_PREVIEW_LIMIT] + "…"
    return {
        "id": revision.id,
        "source": revision.source,
        "run_id": revision.run_id,
        "note": revision.note,
        "chars": count_words(text),
        "created_at": revision.created_at.isoformat() if revision.created_at else "",
        "preview": preview,
    }


def _revision_detail(revision: SceneRevision) -> dict:
    return {
        "id": revision.id,
        "source": revision.source,
        "run_id": revision.run_id,
        "note": revision.note,
        "content": revision.content,
        "created_at": revision.created_at.isoformat() if revision.created_at else "",
    }


def _state(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    draft = _draft(session, scene_id)
    revisions = session.scalars(
        select(SceneRevision)
        .where(SceneRevision.scene_id == scene_id)
        .order_by(SceneRevision.created_at.desc(), SceneRevision.id.desc())
    ).all()
    return {
        "scene_id": scene.id,
        "body": scene.body,
        "has_body": bool((scene.body or "").strip()),
        "word_count": count_words(scene.body),
        "draft": None if draft is None else _draft_out(draft),
        "revisions": [_revision_summary(row) for row in revisions],
    }


def get_text(session: Session, scene_id: str) -> dict:
    _scene(session, scene_id)
    return _state(session, scene_id)


def save_body(session: Session, scene_id: str, content: str) -> dict:
    scene = _scene(session, scene_id)
    project = _project(session, scene)
    new_content = content or ""
    if (scene.body or "") != new_content:
        scene.body = new_content or None
        session.add(
            SceneRevision(scene_id=scene.id, content=new_content, source="author")
        )
        search_service.mark_dirty(session, project.id)
        session.commit()
    return _state(session, scene_id)


def save_draft(session: Session, scene_id: str, content: str) -> dict:
    _scene(session, scene_id)
    draft = _draft(session, scene_id)
    if draft is None:
        raise ValueError("草稿已被替换或删除，请刷新")
    draft.content = content or ""
    session.commit()
    return _draft_out(draft)


def discard_draft(session: Session, scene_id: str) -> None:
    _scene(session, scene_id)
    draft = _draft(session, scene_id)
    if draft is not None:
        session.delete(draft)
        session.commit()


def adopt_draft(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    draft = _draft(session, scene_id)
    if draft is None:
        raise ValueError("当前没有可采纳的草稿")
    content = draft.content or ""
    if not content.strip():
        raise ValueError("草稿为空，不能采纳")
    project = _project(session, scene)
    scene.body = content
    session.add(
        SceneRevision(
            scene_id=scene.id, content=content, source="ai", run_id=draft.run_id
        )
    )
    session.delete(draft)
    search_service.mark_dirty(session, project.id)
    session.commit()
    return _state(session, scene_id)


def list_revisions(session: Session, scene_id: str) -> list[dict]:
    _scene(session, scene_id)
    rows = session.scalars(
        select(SceneRevision)
        .where(SceneRevision.scene_id == scene_id)
        .order_by(SceneRevision.created_at.desc(), SceneRevision.id.desc())
    ).all()
    return [_revision_summary(row) for row in rows]


def get_revision(session: Session, scene_id: str, revision_id: str) -> dict:
    _scene(session, scene_id)
    revision = session.get(SceneRevision, revision_id)
    if revision is None or revision.scene_id != scene_id:
        raise ValueError("修订不存在")
    return _revision_detail(revision)


def restore_revision(session: Session, scene_id: str, revision_id: str) -> dict:
    scene = _scene(session, scene_id)
    revision = session.get(SceneRevision, revision_id)
    if revision is None or revision.scene_id != scene_id:
        raise ValueError("修订不存在")
    project = _project(session, scene)
    content = revision.content or ""
    scene.body = content or None
    session.add(
        SceneRevision(
            scene_id=scene.id,
            content=content,
            source="restore",
            note=f"恢复自修订 {revision.id}",
        )
    )
    search_service.mark_dirty(session, project.id)
    session.commit()
    return _state(session, scene_id)


def _scene_extra(session: Session, scene: Scene) -> tuple[Project, dict]:
    chapter = session.get(Chapter, scene.chapter_id)
    if chapter is None:
        raise ValueError("场景的章节结构已损坏")
    volume = session.get(Volume, chapter.volume_id)
    if volume is None:
        raise ValueError("场景的章节结构已损坏")
    project = session.get(Project, volume.project_id)
    if project is None:
        raise ValueError("场景的章节结构已损坏")
    return project, {
        "scene_id": scene.id,
        "chapter_id": chapter.id,
        "volume_id": volume.id,
        "search_query": scene_search_query(session, project.id, scene),
    }


def prepare_generation(session: Session, scene_id: str) -> GenerationSpec:
    scene = _scene(session, scene_id)
    project, extra = _scene_extra(session, scene)
    agent = agent_service.find_by_task_type(session, "write")
    if agent is None:
        raise ValueError("找不到执笔智能体，请检查智能体工作室")
    prepared = RuntimeService(session).prepare(project.id, agent.id, extra)
    return GenerationSpec(project_id=project.id, scene_id=scene.id, prepared=prepared)


def create_run(spec: GenerationSpec) -> str:
    prepared = spec.prepared
    with SessionLocal() as session:
        run = GenerationRun(
            project_id=spec.project_id,
            agent_id=prepared.agent.id,
            agent_version_id=prepared.version.id,
            provider_id=prepared.provider.id,
            model=prepared.model,
            params_json=prepared.params,
            rendered_prompt=prepared.prompt.rendered_prompt,
            trimmed_json=prepared.prompt.trimmed,
            status="running",
        )
        session.add(run)
        session.commit()
        return run.id


def finalize_run(
    run_id: str,
    scene_id: str,
    *,
    content: str,
    status: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_estimate: float,
    duration_ms: int,
    error: dict | None,
) -> str | None:
    """幂等收尾：只有 running 的运行会更新；成功后覆盖草稿，失败只补空缺。"""
    with SessionLocal() as session:
        run = session.get(GenerationRun, run_id)
        if run is None or run.status != "running":
            return None

        run.raw_output = content
        run.prompt_tokens = prompt_tokens
        run.completion_tokens = completion_tokens
        run.cost_estimate = cost_estimate
        run.duration_ms = duration_ms
        run.status = status
        run.error_json = error

        draft_id: str | None = None
        if content.strip():
            draft = session.scalars(
                select(SceneDraft).where(SceneDraft.scene_id == scene_id)
            ).first()
            if status == "ok" or draft is None:
                if draft is None:
                    draft = SceneDraft(
                        scene_id=scene_id, run_id=run_id, content=content
                    )
                    session.add(draft)
                    session.flush()
                else:
                    draft.content = content
                    draft.run_id = run_id
                draft_id = draft.id
        session.commit()
        return draft_id
```

- [ ] **Step 4: 跑测试**

Run: `uv run --directory backend pytest tests/test_text_service.py -q`
Expected: PASS（8 passed）。

- [ ] **Step 5: 全量与提交**

Run: `uv run --directory backend pytest -q`
Expected: 407 passed。

```bash
git add backend/app/services/text_service.py backend/tests/test_text_service.py
git commit -m "feat(text): 正文草稿、采纳与修订服务"
```

---

### Task 6: 流式生成服务与 SSE 端点

**Files:**
- Modify: `backend/app/api/schemas.py`（仅后续任务需要；本任务可不改）
- Create: `backend/app/api/text.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_text_api.py`

**Interfaces:**
- Produces: `POST /api/scenes/{scene_id}/generate`，返回 `text/event-stream`，事件 `run / delta / done / error`。
- Consumes: `text_service.prepare_generation/create_run/finalize_run`、`ChatFailure`、`estimate_tokens`、`compute_cost`。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_text_api.py`:

```python
import httpx
import pytest

from app.db.models import GenerationRun, SceneDraft
from app.db.session import SessionLocal
from app.runtime.llm import ChatError, ChatFailure
from app.services.runtime_service import RuntimeService


def _create_scene(client) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={"goal": "找到录音带", "conflict": "档案室有人", "turn": "录音带里是自己的声音"},
    ).json()
    return project["id"], scene["id"]


class FakeStreamClient:
    def __init__(self, chunks, fail_at=None):
        self._chunks = chunks
        self._fail_at = fail_at

    async def stream(self, config, messages, params):
        parts: list[str] = []
        for index, chunk in enumerate(self._chunks):
            if self._fail_at == index:
                raise ChatFailure(
                    ChatError("network", "网络中断"), partial_text="".join(parts)
                )
            parts.append(chunk)
            yield chunk

    async def complete(self, config, messages, params):
        raise AssertionError("流式生成不允许走非流式接口")


def _patch_stream(monkeypatch, fake: FakeStreamClient) -> None:
    monkeypatch.setattr(
        RuntimeService, "_resolve_client", lambda self, timeout: fake
    )


def _stream_body(client, scene_id: str) -> str:
    with client.stream("POST", f"/api/scenes/{scene_id}/generate") as response:
        assert response.status_code == 200
        return "".join(response.iter_lines())


def test_generate_streams_and_saves_a_draft(client, monkeypatch):
    _project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一段。", "第二段。"]))

    body = _stream_body(client, scene_id)

    assert "event: run" in body
    assert "event: delta" in body
    assert "event: done" in body
    state = client.get(f"/api/scenes/{scene_id}/text").json()
    assert state["draft"]["content"] == "第一段。第二段。"
    assert state["has_body"] is False

    with SessionLocal() as session:
        run = session.query(GenerationRun).one()
        assert run.status == "ok"
        assert run.raw_output == "第一段。第二段。"
        assert run.completion_tokens > 0


def test_generate_failure_keeps_partial_content(client, monkeypatch):
    _project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一段。"], fail_at=1))

    body = _stream_body(client, scene_id)

    assert "event: error" in body
    assert "网络中断" in body
    state = client.get(f"/api/scenes/{scene_id}/text").json()
    assert state["draft"]["content"] == "第一段。"
    with SessionLocal() as session:
        run = session.query(GenerationRun).one()
        assert run.status == "partial"
        assert run.raw_output == "第一段。"


def test_failed_regeneration_does_not_overwrite_existing_draft(client, monkeypatch):
    _project_id, scene_id = _create_scene(client)
    _patch_stream(monkeypatch, FakeStreamClient(["第一版。"]))
    _stream_body(client, scene_id)
    _patch_stream(monkeypatch, FakeStreamClient(["第二版。"], fail_at=1))
    _stream_body(client, scene_id)

    state = client.get(f"/api/scenes/{scene_id}/text").json()
    assert state["draft"]["content"] == "第一版。"


def test_generate_without_writer_model_is_400_before_streaming(client):
    _project_id, scene_id = _create_scene(client)
    with SessionLocal() as session:
        from app.db.models import Agent, AgentVersion

        writer = session.query(Agent).filter_by(task_type="write").one()
        version = session.get(AgentVersion, writer.current_version_id)
        version.model_binding_json = {}
        session.commit()

    response = client.post(f"/api/scenes/{scene_id}/generate")
    assert response.status_code == 400
    assert "绑定模型" in response.json()["detail"]


def test_finalize_run_is_idempotent_and_keeps_cancelled_content(client):
    _project_id, scene_id = _create_scene(client)
    with SessionLocal() as session:
        run = GenerationRun(project_id=None, status="running")
        session.add(run)
        session.commit()
        run_id = run.id

    from app.services import text_service

    text_service.finalize_run(
        run_id,
        scene_id,
        content="半截正文。",
        status="cancelled",
        prompt_tokens=10,
        completion_tokens=5,
        cost_estimate=0.0,
        duration_ms=100,
        error=None,
    )
    text_service.finalize_run(
        run_id,
        scene_id,
        content="不应覆盖",
        status="ok",
        prompt_tokens=10,
        completion_tokens=99,
        cost_estimate=0.0,
        duration_ms=200,
        error=None,
    )

    with SessionLocal() as session:
        stored = session.get(GenerationRun, run_id)
        assert stored.status == "cancelled"
        assert stored.raw_output == "半截正文。"
        draft = session.query(SceneDraft).filter_by(scene_id=scene_id).one()
        assert draft.content == "半截正文。"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_text_api.py -q`
Expected: FAIL（路由不存在）。

- [ ] **Step 3: 实现 SSE 端点**

Create `backend/app/api/text.py`:

```python
"""正文与流式执笔。路由层只做参数校验、错误翻译与事件转发。"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.runtime.llm import ChatFailure
from app.runtime.pricing import compute_cost, estimate_tokens
from app.services import text_service

router = APIRouter(prefix="/api", tags=["text"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(("场景不存在", "修订不存在", "草稿已被替换或删除")):
        return HTTPException(status_code=404, detail=message)
    if message.startswith(("当前没有可采纳的草稿", "场景的章节结构已损坏")):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/scenes/{scene_id}/generate")
async def generate_scene(
    scene_id: str, request: Request, session: Session = Depends(get_session)
):
    try:
        spec = text_service.prepare_generation(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc

    prepared = spec.prepared
    if prepared.prompt.error:
        raise HTTPException(
            status_code=400, detail=prepared.prompt.error["message"]
        )

    async def events():
        run_id = text_service.create_run(spec)
        yield _sse(
            "run",
            {
                "run_id": run_id,
                "model": prepared.model,
                "agent": prepared.agent.name,
                "estimated_tokens": prepared.prompt.prompt_tokens,
                "trimmed": prepared.prompt.trimmed,
            },
        )

        parts: list[str] = []
        started = time.monotonic()
        finalized = False

        def usage(content: str) -> tuple[int, int, float]:
            prompt_tokens = prepared.prompt.prompt_tokens
            completion_tokens = estimate_tokens(content)
            cost = compute_cost(prompt_tokens, completion_tokens, prepared.prices)
            return prompt_tokens, completion_tokens, cost

        def finish(
            content: str, status: str, error: dict | None
        ) -> tuple[str | None, int]:
            prompt_tokens, completion_tokens, cost = usage(content)
            duration = int((time.monotonic() - started) * 1000)
            draft_id = text_service.finalize_run(
                run_id,
                scene_id,
                content=content,
                status=status,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_estimate=cost,
                duration_ms=duration,
                error=error,
            )
            return draft_id, duration

        try:
            async for chunk in prepared.client.stream(
                prepared.config, prepared.prompt.messages, prepared.params
            ):
                if await request.is_disconnected():
                    raise asyncio.CancelledError
                parts.append(chunk)
                yield _sse("delta", {"text": chunk})

            content = "".join(parts)
            draft_id, duration = finish(content, "ok", None)
            finalized = True
            prompt_tokens, completion_tokens, cost = usage(content)
            yield _sse(
                "done",
                {
                    "run_id": run_id,
                    "status": "ok",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost_estimate": cost,
                    "duration_ms": duration,
                    "chars": len(content),
                    "draft_id": draft_id,
                },
            )
        except asyncio.CancelledError:
            if not finalized:
                finalized = True
                finish("".join(parts), "cancelled", None)
            raise
        except ChatFailure as exc:
            content = "".join(parts) or exc.partial_text
            if not finalized:
                finalized = True
                status = "partial" if content.strip() else "error"
                finish(
                    content,
                    status,
                    {"kind": exc.error.kind, "message": exc.error.message},
                )
            yield _sse(
                "error",
                {
                    "run_id": run_id,
                    "kind": exc.error.kind,
                    "message": exc.error.message,
                    "chars": len(content),
                },
            )
        except Exception as exc:  # noqa: BLE001
            content = "".join(parts)
            if not finalized:
                finalized = True
                finish(
                    content,
                    "partial" if content.strip() else "error",
                    {"kind": "runtime", "message": str(exc)},
                )
            yield _sse(
                "error",
                {
                    "run_id": run_id,
                    "kind": "runtime",
                    "message": str(exc),
                    "chars": len(content),
                },
            )
        finally:
            if not finalized:
                finish("".join(parts), "cancelled", None)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Modify `backend/app/main.py`：在现有路由注册处追加：

```python
from app.api import text as text_api

app.include_router(text_api.router)
```

（按该文件现有 import / include 风格放置。）

- [ ] **Step 4: 跑测试**

Run: `uv run --directory backend pytest tests/test_text_api.py -q`
Expected: PASS（5 passed）。

注意：`test_generate_without_writer_model_is_400_before_streaming` 依赖 conftest 给每个 AgentVersion 补 `test-model`；本用例在测试内清空 writer 的绑定。

- [ ] **Step 5: 全量与提交**

Run: `uv run --directory backend pytest -q`
Expected: 412 passed。

```bash
git add backend/app/api/text.py backend/app/main.py backend/tests/test_text_api.py
git commit -m "feat(api): 场景正文流式生成端点"
```

---

### Task 7: 正文、草稿与修订 API

**Files:**
- Modify: `backend/app/api/schemas.py`（`TextWrite`）
- Modify: `backend/app/api/text.py`
- Test: `backend/tests/test_text_api.py`

**Interfaces:**
- Produces:
  - `GET /api/scenes/{id}/text`
  - `PUT /api/scenes/{id}/body`
  - `PUT /api/scenes/{id}/draft`
  - `DELETE /api/scenes/{id}/draft`
  - `POST /api/scenes/{id}/adopt`
  - `GET /api/scenes/{id}/revisions`
  - `GET /api/scenes/{id}/revisions/{revision_id}`
  - `POST /api/scenes/{id}/revisions/{revision_id}/restore`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_text_api.py`:

```python
def _add_draft(scene_id: str, content: str) -> None:
    with SessionLocal() as session:
        session.add(SceneDraft(scene_id=scene_id, content=content))
        session.commit()


def test_text_endpoints_roundtrip_body_and_revisions(client):
    _project_id, scene_id = _create_scene(client)

    empty = client.get(f"/api/scenes/{scene_id}/text").json()
    assert empty["body"] is None and empty["draft"] is None

    saved = client.put(
        f"/api/scenes/{scene_id}/body", json={"content": "第一段。"}
    ).json()
    assert saved["body"] == "第一段。"
    assert saved["has_body"] is True
    assert saved["revisions"][0]["source"] == "author"

    same = client.put(
        f"/api/scenes/{scene_id}/body", json={"content": "第一段。"}
    ).json()
    assert len(same["revisions"]) == 1

    changed = client.put(
        f"/api/scenes/{scene_id}/body", json={"content": "第二段。"}
    ).json()
    assert len(changed["revisions"]) == 2

    old = next(
        row for row in changed["revisions"] if row["preview"].startswith("第一段")
    )
    detail = client.get(f"/api/scenes/{scene_id}/revisions/{old['id']}").json()
    assert detail["content"] == "第一段。"

    restored = client.post(
        f"/api/scenes/{scene_id}/revisions/{old['id']}/restore"
    ).json()
    assert restored["body"] == "第一段。"
    assert restored["revisions"][0]["source"] == "restore"


def test_draft_endpoints(client):
    _project_id, scene_id = _create_scene(client)
    _add_draft(scene_id, "AI 草稿")

    state = client.get(f"/api/scenes/{scene_id}/text").json()
    assert state["draft"]["content"] == "AI 草稿"

    edited = client.put(
        f"/api/scenes/{scene_id}/draft", json={"content": "改过的草稿"}
    ).json()
    assert edited["content"] == "改过的草稿"

    adopted = client.post(f"/api/scenes/{scene_id}/adopt").json()
    assert adopted["body"] == "改过的草稿"
    assert adopted["draft"] is None
    assert adopted["revisions"][0]["source"] == "ai"


def test_discard_draft(client):
    _project_id, scene_id = _create_scene(client)
    _add_draft(scene_id, "待丢弃")

    assert client.delete(f"/api/scenes/{scene_id}/draft").status_code == 200
    assert client.get(f"/api/scenes/{scene_id}/text").json()["draft"] is None


def test_adopt_without_draft_is_409(client):
    _project_id, scene_id = _create_scene(client)
    assert client.post(f"/api/scenes/{scene_id}/adopt").status_code == 409


def test_missing_scene_and_revision_are_404(client):
    assert client.get("/api/scenes/nope/text").status_code == 404
    _project_id, scene_id = _create_scene(client)
    assert (
        client.get(f"/api/scenes/{scene_id}/revisions/nope").status_code == 404
    )
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_text_api.py -q`
Expected: FAIL（路由 404/405）。

- [ ] **Step 3: 加请求模型与路由**

Modify `backend/app/api/schemas.py` 末尾追加：

```python
class TextWrite(BaseModel):
    content: str = ""
```

Modify `backend/app/api/text.py`：导入 `TextWrite`，追加路由：

```python
from app.api.schemas import TextWrite


@router.get("/scenes/{scene_id}/text")
def get_text(scene_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return text_service.get_text(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.put("/scenes/{scene_id}/body")
def save_body(
    scene_id: str, payload: TextWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        return text_service.save_body(session, scene_id, payload.content)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.put("/scenes/{scene_id}/draft")
def save_draft(
    scene_id: str, payload: TextWrite, session: Session = Depends(get_session)
) -> dict:
    try:
        return text_service.save_draft(session, scene_id, payload.content)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.delete("/scenes/{scene_id}/draft")
def discard_draft(
    scene_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        text_service.discard_draft(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc
    return {"ok": True}


@router.post("/scenes/{scene_id}/adopt")
def adopt_draft(
    scene_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return text_service.adopt_draft(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/revisions")
def list_revisions(
    scene_id: str, session: Session = Depends(get_session)
) -> list[dict]:
    try:
        return text_service.list_revisions(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/revisions/{revision_id}")
def get_revision(
    scene_id: str, revision_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return text_service.get_revision(session, scene_id, revision_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/scenes/{scene_id}/revisions/{revision_id}/restore")
def restore_revision(
    scene_id: str, revision_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return text_service.restore_revision(session, scene_id, revision_id)
    except ValueError as exc:
        raise _value_error(exc) from exc
```

- [ ] **Step 4: 跑测试**

Run: `uv run --directory backend pytest tests/test_text_api.py -q`
Expected: PASS（10 passed）。

- [ ] **Step 5: 全量与提交**

Run: `uv run --directory backend pytest -q`
Expected: 417 passed。

```bash
git add backend/app/api/schemas.py backend/app/api/text.py backend/tests/test_text_api.py
git commit -m "feat(api): 正文、草稿与修订接口"
```

---

### Task 8: 上下文预览 API

**Files:**
- Modify: `backend/app/api/text.py`
- Test: `backend/tests/test_text_api.py`

**Interfaces:**
- Produces: `GET /api/scenes/{id}/context-preview`，响应形状见 spec §5.2。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_text_api.py`:

```python
def test_context_preview_lists_slots_without_calling_the_model(client, monkeypatch):
    _project_id, scene_id = _create_scene(client)

    def boom(*_args, **_kwargs):
        raise AssertionError("预览不允许调用模型")

    monkeypatch.setattr(
        RuntimeService, "_resolve_client", lambda self, timeout: boom()
    )

    payload = client.get(f"/api/scenes/{scene_id}/context-preview").json()

    assert payload["agent"]["name"] == "执笔"
    assert payload["token_budget"] > 0
    keys = {slot["key"] for slot in payload["slots"]}
    assert {"scene_card", "scene_characters", "recent_text"} <= keys
    card = next(slot for slot in payload["slots"] if slot["key"] == "scene_card")
    assert "找到录音带" in card["text"]


def test_context_preview_without_writer_is_400(client):
    _project_id, _scene_id = _create_scene(client)
    with SessionLocal() as session:
        from app.db.models import Agent

        writer = session.query(Agent).filter_by(task_type="write").one()
        writer.enabled = False
        session.commit()

    _project_id, scene_id = _create_scene(client)
    assert (
        client.get(f"/api/scenes/{scene_id}/context-preview").status_code == 400
    )
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_text_api.py -q`
Expected: FAIL（404）。

- [ ] **Step 3: 实现预览**

Modify `backend/app/services/text_service.py`：追加函数（导入 `config`、`SLOT_REGISTRY`、`estimate_tokens`）：

```python
from app import config
from app.runtime.context import SLOT_REGISTRY
from app.runtime.pricing import estimate_tokens


def context_preview(session: Session, scene_id: str) -> dict:
    scene = _scene(session, scene_id)
    project, extra = _scene_extra(session, scene)
    agent = agent_service.find_by_task_type(session, "write")
    if agent is None:
        raise ValueError("找不到执笔智能体，请检查智能体工作室")

    agent, version, prompt = RuntimeService(session).prepare_context(
        project.id, agent.id, extra
    )
    if prompt.error:
        raise ValueError(prompt.error["message"])

    slots: list[dict] = []
    for key in version.context_slots_json or []:
        spec = SLOT_REGISTRY.get(key)
        text = prompt.contents.get(key)
        slots.append(
            {
                "key": key,
                "label": spec.label if spec else key,
                "priority": spec.priority if spec else 0,
                "over_budget": spec.over_budget if spec else "drop",
                "text": text,
                "estimated_tokens": estimate_tokens(text) if text else 0,
            }
        )

    settings = config.load_settings()
    return {
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "version_no": version.version_no,
        },
        "token_budget": int(settings.get("context_token_budget", 8000)),
        "estimated_tokens": sum(slot["estimated_tokens"] for slot in slots),
        "over_budget": prompt.over_budget,
        "slots": slots,
        "trimmed": prompt.trimmed,
    }
```

Modify `backend/app/api/text.py` 追加：

```python
@router.get("/scenes/{scene_id}/context-preview")
def context_preview(
    scene_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return text_service.context_preview(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc
```

- [ ] **Step 4: 跑测试**

Run: `uv run --directory backend pytest tests/test_text_api.py -q`
Expected: PASS（12 passed）。

- [ ] **Step 5: 全量与提交**

Run: `uv run --directory backend pytest -q`
Expected: 419 passed。

```bash
git add backend/app/services/text_service.py backend/app/api/text.py backend/tests/test_text_api.py
git commit -m "feat(api): 场景上下文预览"
```

---

### Task 9: 场景树 has_body 与正文检索

**Files:**
- Modify: `backend/app/services/chapter_service.py`
- Modify: `backend/app/services/scene_service.py`（`scene_payload` 同步加 `has_body`）
- Modify: `backend/app/services/search_service.py`
- Modify: `backend/app/db/search.py`（版本 2）
- Test: `backend/tests/test_chapters_api.py`
- Test: `backend/tests/test_search_service.py`
- Test: `backend/tests/test_search_api.py`

**Interfaces:**
- Produces: 树的场景节点与 `scene_payload` 带派生 `has_body`；`scene.body` 进入 FTS 文档；`SEARCH_INDEX_VERSION=2`。

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_chapters_api.py`（复用该文件现有建项目辅助函数；如果没有，按下面自带 helper）：

```python
def _writing_scene(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "找到录音带"}
    ).json()
    return project, scene


def test_tree_exposes_has_body_without_the_full_text(client):
    project, scene = _writing_scene(client)
    client.put(
        f"/api/scenes/{scene['id']}/body", json={"content": "灯塔下的密信。"}
    )

    tree = client.get(f"/api/projects/{project['id']}/chapters/tree").json()
    node = tree["volumes"][0]["chapters"][0]["scenes"][0]
    assert node["has_body"] is True
    assert "body" not in node
```

追加到 `backend/tests/test_search_api.py`:

```python
def test_adopted_scene_body_is_searchable(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters", json={"title": "第一章"}
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes", json={"goal": "找到录音带"}
    ).json()
    client.put(
        f"/api/scenes/{scene['id']}/body",
        json={"content": "灯塔下的密信被雨水泡开。"},
    )

    results = client.get(
        f"/api/projects/{project['id']}/search", params={"q": "灯塔下的密信"}
    ).json()["results"]
    assert any(row["entity_type"] == "scene" for row in results)
```

Modify `backend/tests/test_search_service.py` 的版本断言：

```python
    assert state.schema_version == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --directory backend pytest tests/test_chapters_api.py tests/test_search_api.py tests/test_search_service.py -q`
Expected: FAIL（`has_body` 缺失、正文搜不到、版本仍为 1）。

- [ ] **Step 3: 实现派生字段与索引**

Modify `backend/app/services/chapter_service.py` 的 `build_tree` 场景字典，追加：

```python
                    "has_body": bool((scene.body or "").strip()),
```

Modify `backend/app/services/scene_service.py` 的 `scene_payload`，追加：

```python
        "has_body": bool((scene.body or "").strip()),
```

Modify `backend/app/services/search_service.py` 的 `_scene_doc`，在状态之前追加：

```python
    if scene.body:
        parts.append("正文：" + scene.body)
```

Modify `backend/app/db/search.py`：

```python
SEARCH_INDEX_VERSION = 2
```

- [ ] **Step 4: 跑相关测试**

Run: `uv run --directory backend pytest tests/test_chapters_api.py tests/test_search_api.py tests/test_search_service.py -q`
Expected: PASS。

- [ ] **Step 5: 全量与提交**

Run: `uv run --directory backend pytest -q`
Expected: 421 passed。

```bash
git add backend/app/services/chapter_service.py backend/app/services/scene_service.py backend/app/services/search_service.py backend/app/db/search.py backend/tests/test_chapters_api.py backend/tests/test_search_api.py backend/tests/test_search_service.py
git commit -m "feat(search): 正文入索引并暴露场景写入状态"
```

---

### Task 10: 前端纯逻辑（SSE 解析、行级 diff）与 API 客户端

**Files:**
- Create: `frontend/src/lib/sse.ts`
- Create: `frontend/src/lib/sse.test.ts`
- Create: `frontend/src/lib/diff.ts`
- Create: `frontend/src/lib/diff.test.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces:
  - `createSseParser(): { push(chunk: string): SseEvent[] }`
  - `diffLines(oldText: string, newText: string): DiffRow[]`
  - `SceneTextState / SceneTextDraft / RevisionSummary / RevisionDetail / ContextPreview / ContextSlotPreview`
  - `streamSceneGeneration(sceneId, handlers, signal): Promise<void>`
  - 正文 / 草稿 / 修订 / 预览 API 方法。

- [ ] **Step 1: 写失败测试**

Create `frontend/src/lib/sse.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { createSseParser } from './sse'

describe('createSseParser', () => {
  it('parses one complete event', () => {
    const parser = createSseParser()
    expect(parser.push('event: delta\ndata: {"text":"甲"}\n\n')).toEqual([
      { event: 'delta', data: '{"text":"甲"}' },
    ])
  })

  it('buffers an event split across chunks', () => {
    const parser = createSseParser()
    expect(parser.push('event: delta\ndata: {"te')).toEqual([])
    expect(parser.push('xt":"乙"}\n\n')).toEqual([
      { event: 'delta', data: '{"text":"乙"}' },
    ])
  })

  it('joins multi-line data and ignores comments', () => {
    const parser = createSseParser()
    expect(parser.push(': ping\nevent: done\ndata: 第一行\ndata: 第二行\n\n')).toEqual([
      { event: 'done', data: '第一行\n第二行' },
    ])
  })

  it('defaults the event name to message', () => {
    const parser = createSseParser()
    expect(parser.push('data: x\n\n')).toEqual([{ event: 'message', data: 'x' }])
  })

  it('skips blocks without data', () => {
    const parser = createSseParser()
    expect(parser.push('event: ping\n\n')).toEqual([])
  })

  it('normalizes CRLF', () => {
    const parser = createSseParser()
    expect(parser.push('event: run\r\ndata: {}\r\n\r\n')).toEqual([
      { event: 'run', data: '{}' },
    ])
  })
})
```

Create `frontend/src/lib/diff.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { diffLines } from './diff'

describe('diffLines', () => {
  it('marks identical text as same', () => {
    expect(diffLines('甲\n乙', '甲\n乙')).toEqual([
      { kind: 'same', text: '甲', oldLine: 1, newLine: 1 },
      { kind: 'same', text: '乙', oldLine: 2, newLine: 2 },
    ])
  })

  it('marks pure additions', () => {
    expect(diffLines('甲', '甲\n乙')).toEqual([
      { kind: 'same', text: '甲', oldLine: 1, newLine: 1 },
      { kind: 'add', text: '乙', oldLine: null, newLine: 2 },
    ])
  })

  it('marks pure removals', () => {
    expect(diffLines('甲\n乙', '甲')).toEqual([
      { kind: 'same', text: '甲', oldLine: 1, newLine: 1 },
      { kind: 'remove', text: '乙', oldLine: 2, newLine: null },
    ])
  })

  it('marks replacements', () => {
    expect(diffLines('旧', '新')).toEqual([
      { kind: 'remove', text: '旧', oldLine: 1, newLine: null },
      { kind: 'add', text: '新', oldLine: null, newLine: 1 },
    ])
  })

  it('handles an empty old text', () => {
    expect(diffLines('', '新')).toEqual([
      { kind: 'add', text: '新', oldLine: null, newLine: 1 },
    ])
  })

  it('falls back to whole replacement for very long text', () => {
    const oldText = Array.from({ length: 2500 }, (_, i) => `旧${i}`).join('\n')
    const newText = Array.from({ length: 2500 }, (_, i) => `新${i}`).join('\n')
    const rows = diffLines(oldText, newText)
    expect(rows.filter((row) => row.kind === 'remove')).toHaveLength(2500)
    expect(rows.filter((row) => row.kind === 'add')).toHaveLength(2500)
    expect(rows.every((row) => row.kind !== 'same')).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && pnpm vitest run src/lib/sse.test.ts src/lib/diff.test.ts`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现纯函数**

Create `frontend/src/lib/sse.ts`:

```ts
export interface SseEvent {
  event: string
  data: string
}

function parseBlock(raw: string): SseEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of raw.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length === 0 ? null : { event, data: data.join('\n') }
}

export function createSseParser() {
  let buffer = ''
  return {
    push(chunk: string): SseEvent[] {
      buffer = (buffer + chunk).replace(/\r\n/g, '\n')
      const events: SseEvent[] = []
      for (;;) {
        const boundary = buffer.indexOf('\n\n')
        if (boundary < 0) break
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const parsed = parseBlock(block)
        if (parsed) events.push(parsed)
      }
      return events
    },
  }
}
```

Create `frontend/src/lib/diff.ts`:

```ts
export type DiffKind = 'same' | 'add' | 'remove'

export interface DiffRow {
  kind: DiffKind
  text: string
  oldLine: number | null
  newLine: number | null
}

const MAX_DIFF_LINES = 4000

function toLines(text: string): string[] {
  const normalized = text.replace(/\r\n/g, '\n')
  if (normalized === '') return []
  const lines = normalized.split('\n')
  if (lines[lines.length - 1] === '') lines.pop()
  return lines
}

export function diffLines(oldText: string, newText: string): DiffRow[] {
  const oldLines = toLines(oldText)
  const newLines = toLines(newText)

  if (oldLines.length + newLines.length > MAX_DIFF_LINES) {
    return [
      ...oldLines.map((text, index) => ({
        kind: 'remove' as const,
        text,
        oldLine: index + 1,
        newLine: null,
      })),
      ...newLines.map((text, index) => ({
        kind: 'add' as const,
        text,
        oldLine: null,
        newLine: index + 1,
      })),
    ]
  }

  const table: number[][] = Array.from({ length: oldLines.length + 1 }, () =>
    new Array<number>(newLines.length + 1).fill(0),
  )
  for (let i = oldLines.length - 1; i >= 0; i -= 1) {
    for (let j = newLines.length - 1; j >= 0; j -= 1) {
      table[i][j] =
        oldLines[i] === newLines[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1])
    }
  }

  const rows: DiffRow[] = []
  let i = 0
  let j = 0
  while (i < oldLines.length && j < newLines.length) {
    if (oldLines[i] === newLines[j]) {
      rows.push({ kind: 'same', text: oldLines[i], oldLine: i + 1, newLine: j + 1 })
      i += 1
      j += 1
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      rows.push({ kind: 'remove', text: oldLines[i], oldLine: i + 1, newLine: null })
      i += 1
    } else {
      rows.push({ kind: 'add', text: newLines[j], oldLine: null, newLine: j + 1 })
      j += 1
    }
  }
  while (i < oldLines.length) {
    rows.push({ kind: 'remove', text: oldLines[i], oldLine: i + 1, newLine: null })
    i += 1
  }
  while (j < newLines.length) {
    rows.push({ kind: 'add', text: newLines[j], oldLine: null, newLine: j + 1 })
    j += 1
  }
  return rows
}
```

- [ ] **Step 4: 跑纯逻辑测试**

Run: `cd frontend && pnpm vitest run src/lib/sse.test.ts src/lib/diff.test.ts`
Expected: PASS（12 passed）。

- [ ] **Step 5: 扩展 API 客户端**

Modify `frontend/src/api/client.ts`：

1. 顶部导入：

```ts
import { createSseParser } from '../lib/sse'
```

2. `api` 对象内追加（放在 chapter 相关方法之后）：

```ts
  getSceneText: (sceneId: string) =>
    request<SceneTextState>(`/api/scenes/${sceneId}/text`),
  saveSceneBody: (sceneId: string, content: string) =>
    request<SceneTextState>(`/api/scenes/${sceneId}/body`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ content }),
    }),
  saveSceneDraft: (sceneId: string, content: string) =>
    request<SceneTextDraft>(`/api/scenes/${sceneId}/draft`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ content }),
    }),
  discardSceneDraft: (sceneId: string) =>
    request<{ ok: boolean }>(`/api/scenes/${sceneId}/draft`, { method: 'DELETE' }),
  adoptSceneDraft: (sceneId: string) =>
    request<SceneTextState>(`/api/scenes/${sceneId}/adopt`, { method: 'POST' }),
  listSceneRevisions: (sceneId: string) =>
    request<RevisionSummary[]>(`/api/scenes/${sceneId}/revisions`),
  getSceneRevision: (sceneId: string, revisionId: string) =>
    request<RevisionDetail>(`/api/scenes/${sceneId}/revisions/${revisionId}`),
  restoreSceneRevision: (sceneId: string, revisionId: string) =>
    request<SceneTextState>(
      `/api/scenes/${sceneId}/revisions/${revisionId}/restore`,
      { method: 'POST' },
    ),
  getSceneContextPreview: (sceneId: string) =>
    request<ContextPreview>(`/api/scenes/${sceneId}/context-preview`),
```

3. 在 `SceneNode` 接口加：

```ts
  has_body: boolean
```

4. 文件末尾追加类型与流式函数：

```ts
export interface SceneTextDraft {
  id: string
  content: string
  run_id: string | null
  updated_at: string
}

export interface RevisionSummary {
  id: string
  source: string
  run_id: string | null
  note: string
  chars: number
  created_at: string
  preview: string
}

export interface SceneTextState {
  scene_id: string
  body: string | null
  has_body: boolean
  word_count: number
  draft: SceneTextDraft | null
  revisions: RevisionSummary[]
}

export interface RevisionDetail {
  id: string
  source: string
  run_id: string | null
  note: string
  content: string
  created_at: string
}

export interface ContextSlotPreview {
  key: string
  label: string
  priority: number
  over_budget: string
  text: string | null
  estimated_tokens: number
}

export interface ContextPreview {
  agent: { id: string; name: string; version_no: number }
  token_budget: number
  estimated_tokens: number
  over_budget: boolean
  slots: ContextSlotPreview[]
  trimmed: Record<string, string>
}

export interface GenerationRunEvent {
  run_id: string
  model: string
  agent: string
  estimated_tokens: number
  trimmed: Record<string, string>
}

export interface GenerationDoneEvent {
  run_id: string
  status: string
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  duration_ms: number
  chars: number
  draft_id: string | null
}

export interface GenerationErrorEvent {
  run_id: string
  kind: string
  message: string
  chars: number
}

export interface GenerationHandlers {
  onRun?: (data: GenerationRunEvent) => void
  onDelta?: (text: string) => void
  onDone?: (data: GenerationDoneEvent) => void
  onError?: (data: GenerationErrorEvent) => void
}

export async function streamSceneGeneration(
  sceneId: string,
  handlers: GenerationHandlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/scenes/${sceneId}/generate`, {
    method: 'POST',
    signal,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail ?? `请求失败：${response.status}`)
  }
  if (!response.body) throw new Error('当前环境不支持流式读取')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createSseParser()

  const dispatch = (event: string, data: string) => {
    let parsed: unknown
    try {
      parsed = JSON.parse(data)
    } catch {
      return
    }
    if (event === 'run') handlers.onRun?.(parsed as GenerationRunEvent)
    else if (event === 'delta') {
      const payload = parsed as { text?: string }
      if (payload.text) handlers.onDelta?.(payload.text)
    } else if (event === 'done') handlers.onDone?.(parsed as GenerationDoneEvent)
    else if (event === 'error') handlers.onError?.(parsed as GenerationErrorEvent)
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    for (const event of parser.push(decoder.decode(value, { stream: true }))) {
      dispatch(event.event, event.data)
    }
  }
  const tail = decoder.decode()
  if (tail) {
    for (const event of parser.push(tail)) dispatch(event.event, event.data)
  }
}
```

5. Modify `frontend/src/lib/chapterViews.test.ts` 的 `makeScene` 返回对象：在 `source_run_id: null,` 之后加一行 `has_body: false,`，否则新增的必填字段会让 `tsc -b` 失败。

- [ ] **Step 6: 构建并提交**

Run: `cd frontend && pnpm vitest run && pnpm build`
Expected: 30 passed（18 + 12），build 干净。

```bash
git add frontend/src/lib/sse.ts frontend/src/lib/sse.test.ts frontend/src/lib/diff.ts frontend/src/lib/diff.test.ts frontend/src/api/client.ts
git commit -m "feat(frontend): 流式解析、行级 diff 与正文 API 客户端"
```

---

### Task 11: 写作台组件（树、上下文预览、修订历史）

**Files:**
- Create: `frontend/src/components/writing/WritingTree.tsx`
- Create: `frontend/src/components/writing/ContextPreview.tsx`
- Create: `frontend/src/components/writing/RevisionHistory.tsx`

**Interfaces:**
- Consumes: `VolumeNode`（含 `has_body`）、`ContextPreview`、`RevisionSummary`。
- Produces: 三个受控展示组件，供 Task 13 的页面使用。

- [ ] **Step 1: 创建 WritingTree**

Create `frontend/src/components/writing/WritingTree.tsx`:

```tsx
import type { VolumeNode } from '../../api/client'

interface Props {
  volumes: VolumeNode[]
  selectedSceneId: string
  onSelect: (sceneId: string) => void
}

export default function WritingTree({ volumes, selectedSceneId, onSelect }: Props) {
  if (volumes.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        这个项目还没有卷章结构，请先去「章节设计」排卷排章。
      </p>
    )
  }

  return (
    <div className="space-y-3 text-sm">
      {volumes.map((volume) => (
        <section key={volume.id}>
          <h3 className="mb-1 font-medium text-slate-300">
            第{volume.seq + 1}卷 {volume.name}
          </h3>
          {volume.chapters.map((chapter) => (
            <div key={chapter.id} className="mb-2">
              <p className="mb-1 text-xs text-slate-500">
                第{chapter.seq + 1}章 {chapter.title}
              </p>
              <ul className="space-y-1">
                {chapter.scenes.map((scene) => (
                  <li key={scene.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(scene.id)}
                      className={`w-full rounded px-2 py-1 text-left ${
                        selectedSceneId === scene.id
                          ? 'bg-slate-800 text-white'
                          : 'text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      <span className="block truncate">
                        {scene.seq + 1}. {scene.goal || '（未写目标）'}
                      </span>
                      <span
                        className={`text-xs ${
                          scene.has_body ? 'text-emerald-400' : 'text-slate-600'
                        }`}
                      >
                        {scene.has_body ? '已写' : '未写'}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 创建 ContextPreview**

Create `frontend/src/components/writing/ContextPreview.tsx`:

```tsx
import type { ContextPreview as ContextPreviewData } from '../../api/client'

interface Props {
  data: ContextPreviewData | null
  loading: boolean
  error: string
}

export default function ContextPreview({ data, loading, error }: Props) {
  if (loading) {
    return <p className="text-sm text-slate-500">正在准备上下文…</p>
  }
  if (error) {
    return <p className="rounded border border-amber-900 bg-amber-950/40 p-2 text-sm text-amber-300">{error}</p>
  }
  if (!data) {
    return <p className="text-sm text-slate-500">选中场景后显示本次将注入的上下文。</p>
  }

  return (
    <section className="space-y-3 text-sm">
      <h3 className="font-medium text-slate-300">上下文预览</h3>
      <p className={`text-xs ${data.over_budget ? 'text-amber-300' : 'text-slate-500'}`}>
        {data.agent.name} v{data.agent.version_no} · 估算 {data.estimated_tokens} /{' '}
        {data.token_budget} tokens
      </p>
      {data.slots.map((slot) => (
        <details key={slot.key} className="rounded border border-slate-800 p-2">
          <summary className="cursor-pointer text-slate-300">
            {slot.label}{' '}
            <span className="text-xs text-slate-500">{slot.estimated_tokens} tokens</span>
            {data.trimmed[slot.key] && (
              <span className="ml-2 text-xs text-amber-300">{data.trimmed[slot.key]}</span>
            )}
          </summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-xs text-slate-400">
            {slot.text ?? '（已丢弃）'}
          </pre>
        </details>
      ))}
    </section>
  )
}
```

- [ ] **Step 3: 创建 RevisionHistory**

Create `frontend/src/components/writing/RevisionHistory.tsx`:

```tsx
import type { RevisionSummary } from '../../api/client'

const SOURCE_LABELS: Record<string, string> = {
  ai: 'AI 采纳',
  author: '作者保存',
  restore: '恢复',
}

interface Props {
  revisions: RevisionSummary[]
  busy: boolean
  onOpen: (revisionId: string) => void
  onRestore: (revisionId: string) => void
}

export default function RevisionHistory({ revisions, busy, onOpen, onRestore }: Props) {
  if (revisions.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        还没有修订。保存正文或采纳草稿后会在这里留下快照。
      </p>
    )
  }

  return (
    <section className="space-y-2 text-sm">
      <h3 className="font-medium text-slate-300">修订历史</h3>
      <ul className="space-y-2">
        {revisions.map((revision) => (
          <li key={revision.id} className="rounded border border-slate-800 p-2">
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => onOpen(revision.id)}
                className="text-left text-slate-300 hover:text-white"
              >
                {SOURCE_LABELS[revision.source] ?? revision.source} · {revision.chars} 字
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => onRestore(revision.id)}
                className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400 hover:text-white disabled:opacity-50"
              >
                恢复
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {new Date(revision.created_at).toLocaleString()}
            </p>
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">{revision.preview}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
```

- [ ] **Step 4: 构建并提交**

Run: `cd frontend && pnpm build`
Expected: build 干净。

```bash
git add frontend/src/components/writing/WritingTree.tsx frontend/src/components/writing/ContextPreview.tsx frontend/src/components/writing/RevisionHistory.tsx
git commit -m "feat(frontend): 写作台树、上下文预览与修订历史组件"
```

---

### Task 12: 写作台编辑与 diff 组件

**Files:**
- Create: `frontend/src/components/writing/SceneTextView.tsx`
- Create: `frontend/src/components/writing/GenerationStream.tsx`
- Create: `frontend/src/components/writing/DiffPanel.tsx`

**Interfaces:**
- Consumes: `diffLines`。
- Produces: 三个展示组件，供 Task 13 的页面使用。

- [ ] **Step 1: 创建 SceneTextView**

Create `frontend/src/components/writing/SceneTextView.tsx`:

```tsx
interface Props {
  title: string
  value: string
  onChange: (value: string) => void
  disabled: boolean
  placeholder: string
}

export default function SceneTextView({
  title,
  value,
  onChange,
  disabled,
  placeholder,
}: Props) {
  const chars = value.replace(/\s/g, '').length
  return (
    <label className="block space-y-1">
      <span className="text-xs text-slate-500">
        {title} · {chars ? `${chars} 字` : '空'}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={18}
        placeholder={placeholder}
        className="w-full resize-y rounded border border-slate-700 bg-slate-950 p-3 font-mono text-sm leading-7 text-slate-100 outline-none focus:border-indigo-500 disabled:opacity-60"
      />
    </label>
  )
}
```

- [ ] **Step 2: 创建 GenerationStream**

Create `frontend/src/components/writing/GenerationStream.tsx`:

```tsx
interface Props {
  text: string
  generating: boolean
}

export default function GenerationStream({ text, generating }: Props) {
  if (!generating && !text) return null
  return (
    <section className="space-y-2 rounded border border-indigo-900 bg-indigo-950/20 p-3">
      <h3 className="text-sm font-medium text-indigo-200">
        {generating ? '正在生成…' : '本次生成结果'}
      </h3>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-sm leading-7 text-slate-100">
        {text || '等待第一段…'}
      </pre>
    </section>
  )
}
```

- [ ] **Step 3: 创建 DiffPanel**

Create `frontend/src/components/writing/DiffPanel.tsx`:

```tsx
import { diffLines } from '../../lib/diff'

interface Props {
  oldText: string
  newText: string
}

export default function DiffPanel({ oldText, newText }: Props) {
  const rows = diffLines(oldText, newText)
  const added = rows.filter((row) => row.kind === 'add').length
  const removed = rows.filter((row) => row.kind === 'remove').length

  return (
    <section className="space-y-2 rounded border border-slate-800 p-3">
      <h3 className="text-sm font-medium text-slate-300">
        旧稿与新稿对比（+{added} / -{removed}）
      </h3>
      <div className="max-h-80 overflow-auto rounded bg-slate-950 font-mono text-xs leading-6">
        {rows.map((row, index) => (
          <div
            key={index}
            className={
              row.kind === 'add'
                ? 'bg-emerald-950/40 text-emerald-200'
                : row.kind === 'remove'
                  ? 'bg-rose-950/40 text-rose-200'
                  : 'text-slate-400'
            }
          >
            <span className="inline-block w-10 select-none pr-2 text-right text-slate-600">
              {row.kind === 'add' ? '+' : row.kind === 'remove' ? '-' : ' '}
            </span>
            <span className="whitespace-pre-wrap break-words">{row.text || ' '}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 4: 构建并提交**

Run: `cd frontend && pnpm build`
Expected: build 干净。

```bash
git add frontend/src/components/writing/SceneTextView.tsx frontend/src/components/writing/GenerationStream.tsx frontend/src/components/writing/DiffPanel.tsx
git commit -m "feat(frontend): 正文编辑、生成流与 diff 组件"
```

---

### Task 13: 写作台页面、路由与生成交互

**Files:**
- Create: `frontend/src/pages/Writing.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: 以上全部前端组件与 API。
- Produces: `/write` 页面，三栏布局，完整生成 / 编辑 / 采纳 / 修订流程。

- [ ] **Step 1: 创建 Writing 页面**

Create `frontend/src/pages/Writing.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import {
  api,
  streamSceneGeneration,
  type ContextPreview as ContextPreviewData,
  type Project,
  type RevisionDetail,
  type SceneTextState,
  type VolumeNode,
} from '../api/client'
import ContextPreview from '../components/writing/ContextPreview'
import DiffPanel from '../components/writing/DiffPanel'
import GenerationStream from '../components/writing/GenerationStream'
import RevisionHistory from '../components/writing/RevisionHistory'
import SceneTextView from '../components/writing/SceneTextView'
import WritingTree from '../components/writing/WritingTree'

function findScene(volumes: VolumeNode[], sceneId: string) {
  for (const volume of volumes) {
    for (const chapter of volume.chapters) {
      const scene = chapter.scenes.find((item) => item.id === sceneId)
      if (scene) return { volume, chapter, scene }
    }
  }
  return null
}

export default function Writing() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [selectedSceneId, setSelectedSceneId] = useState('')
  const [text, setText] = useState<SceneTextState | null>(null)
  const [preview, setPreview] = useState<ContextPreviewData | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [bodyDraft, setBodyDraft] = useState('')
  const [aiDraft, setAiDraft] = useState('')
  const [mode, setMode] = useState<'body' | 'draft'>('body')
  const [generating, setGenerating] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState<RevisionDetail | null>(null)

  const treeToken = useRef(0)
  const sceneToken = useRef(0)
  const generateToken = useRef(0)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    api
      .listProjects()
      .then((list) => {
        setProjects(list)
        if (list[0]) setProjectId(list[0].id)
      })
      .catch((error) => setNotice((error as Error).message))
  }, [])

  useEffect(() => {
    if (!projectId) return
    const token = ++treeToken.current
    sceneToken.current += 1
    generateToken.current += 1
    abortRef.current?.abort()
    setVolumes([])
    setSelectedSceneId('')
    setText(null)
    setPreview(null)
    setPreviewError('')
    setBodyDraft('')
    setAiDraft('')
    setStreamText('')
    setGenerating(false)
    setRevision(null)
    setNotice('')

    api
      .getChapterTree(projectId)
      .then((data) => {
        if (treeToken.current === token) setVolumes(data.volumes)
      })
      .catch((error) => {
        if (treeToken.current === token) setNotice((error as Error).message)
      })
  }, [projectId])

  const hasUnsaved =
    Boolean(text) &&
    (bodyDraft !== (text?.body ?? '') || aiDraft !== (text?.draft?.content ?? ''))

  const changeProject = (nextId: string) => {
    if (nextId === projectId) return
    if (hasUnsaved && !window.confirm('当前场景有未保存的修改，确定切换项目吗？')) return
    setProjectId(nextId)
  }

  const loadScene = async (sceneId: string) => {
    const token = ++sceneToken.current
    setPreviewLoading(true)
    setPreviewError('')
    setPreview(null)
    try {
      const [stateResult, contextResult] = await Promise.allSettled([
        api.getSceneText(sceneId),
        api.getSceneContextPreview(sceneId),
      ])
      if (sceneToken.current !== token) return
      if (stateResult.status === 'fulfilled') {
        const state = stateResult.value
        setText(state)
        setBodyDraft(state.body ?? '')
        setAiDraft(state.draft?.content ?? '')
        setMode(state.draft ? 'draft' : 'body')
      } else {
        setNotice((stateResult.reason as Error).message)
      }
      if (contextResult.status === 'fulfilled') {
        setPreview(contextResult.value)
      } else {
        setPreviewError((contextResult.reason as Error).message)
      }
    } catch (error) {
      if (sceneToken.current === token) setNotice((error as Error).message)
    } finally {
      if (sceneToken.current === token) setPreviewLoading(false)
    }
  }

  const selectScene = (sceneId: string) => {
    if (sceneId === selectedSceneId) return
    if (hasUnsaved && !window.confirm('当前场景有未保存的修改，确定切换吗？')) return
    abortRef.current?.abort()
    generateToken.current += 1
    setGenerating(false)
    setStreamText('')
    setSelectedSceneId(sceneId)
    void loadScene(sceneId)
  }

  const refreshText = async (sceneId: string): Promise<SceneTextState | null> => {
    const token = sceneToken.current
    const state = await api.getSceneText(sceneId)
    if (sceneToken.current !== token) return null
    setText(state)
    setBodyDraft(state.body ?? '')
    setAiDraft(state.draft?.content ?? '')
    return state
  }

  const saveBody = async () => {
    if (!text) return
    setBusy(true)
    setNotice('')
    try {
      const state = await api.saveSceneBody(text.scene_id, bodyDraft)
      setText(state)
      setBodyDraft(state.body ?? '')
      setNotice('正文已保存')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const saveDraft = async () => {
    if (!text?.draft) return
    setBusy(true)
    setNotice('')
    try {
      const saved = await api.saveSceneDraft(text.scene_id, aiDraft)
      setAiDraft(saved.content)
      setText((current) =>
        current && current.draft
          ? { ...current, draft: { ...current.draft, content: saved.content } }
          : current,
      )
      setNotice('草稿已保存')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const adopt = async () => {
    if (!text?.draft) return
    if (!window.confirm('采纳后会用草稿整份替换已采纳正文，并生成修订快照。继续？')) return
    setBusy(true)
    setNotice('')
    try {
      const state = await api.adoptSceneDraft(text.scene_id)
      setText(state)
      setBodyDraft(state.body ?? '')
      setAiDraft('')
      setMode('body')
      setNotice('已采纳，已生成修订快照')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const discard = async () => {
    if (!text?.draft) return
    if (!window.confirm('丢弃这份 AI 草稿？此操作不可撤销。')) return
    setBusy(true)
    setNotice('')
    try {
      await api.discardSceneDraft(text.scene_id)
      setAiDraft('')
      await refreshText(text.scene_id)
      setMode('body')
      setNotice('草稿已丢弃')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const generate = async () => {
    if (!selectedSceneId || generating) return
    const sceneId = selectedSceneId
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const token = ++generateToken.current
    setGenerating(true)
    setStreamText('')
    setNotice('')

    try {
      await streamSceneGeneration(
        sceneId,
        {
          onDelta: (delta) => {
            if (generateToken.current === token) {
              setStreamText((current) => current + delta)
            }
          },
          onDone: () => {
            if (generateToken.current === token) setNotice('生成完成，草稿已更新')
          },
          onError: (data) => {
            if (generateToken.current === token) {
              setNotice(`${data.message}（已保留 ${data.chars} 字）`)
            }
          },
        },
        controller.signal,
      )
    } catch (error) {
      if ((error as Error).name !== 'AbortError' && generateToken.current === token) {
        setNotice((error as Error).message)
      }
    } finally {
      if (generateToken.current === token) {
        setGenerating(false)
        try {
          const state = await refreshText(sceneId)
          setMode(state?.draft ? 'draft' : 'body')
        } catch (error) {
          setNotice((error as Error).message)
        }
      }
    }
  }

  const stop = () => {
    abortRef.current?.abort()
    setNotice('已请求停止；已生成的内容会尽量保留。')
  }

  const openRevision = async (revisionId: string) => {
    if (!text) return
    setBusy(true)
    setNotice('')
    try {
      setRevision(await api.getSceneRevision(text.scene_id, revisionId))
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const restoreRevision = async (revisionId: string) => {
    if (!text) return
    if (!window.confirm('恢复这个修订？当前正文会被替换，并生成一条新的恢复修订。')) return
    setBusy(true)
    setNotice('')
    try {
      const state = await api.restoreSceneRevision(text.scene_id, revisionId)
      setText(state)
      setBodyDraft(state.body ?? '')
      setMode('body')
      setRevision(null)
      setNotice('已恢复旧版并生成新的修订')
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const selected = findScene(volumes, selectedSceneId)
  const sceneLabel = selected
    ? `第${selected.volume.seq + 1}卷 第${selected.chapter.seq + 1}章 场景${selected.scene.seq + 1}`
    : ''

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">写作台</h2>
        <select
          value={projectId}
          onChange={(event) => changeProject(event.target.value)}
          className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm"
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        {sceneLabel && <span className="text-xs text-slate-500">{sceneLabel}</span>}
      </div>

      {notice && (
        <p className="rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-300">
          {notice}
        </p>
      )}

      {!projectId ? (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
          先创建一个项目。
        </p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <aside className="rounded border border-slate-800 p-3">
            <WritingTree
              volumes={volumes}
              selectedSceneId={selectedSceneId}
              onSelect={selectScene}
            />
          </aside>

          <section className="min-w-0 space-y-3">
            {!selected ? (
              <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
                从左侧选择一个场景开始写作。
              </p>
            ) : (
              <>
                <section className="space-y-1 rounded border border-slate-800 p-3 text-sm">
                  <p className="text-slate-300">
                    目标：{selected.scene.goal || '（未写目标）'}
                  </p>
                  <p className="text-slate-400">冲突：{selected.scene.conflict || '（未写）'}</p>
                  <p className="text-slate-400">转折：{selected.scene.turn || '（未写）'}</p>
                  <p className="text-xs text-slate-500">
                    目标字数：{selected.scene.target_words_min ?? '?'}–
                    {selected.scene.target_words_max ?? '?'} · 正文{' '}
                    {text?.word_count ?? 0} 字
                  </p>
                </section>

                <div className="flex flex-wrap items-center gap-2">
                  {generating ? (
                    <button
                      type="button"
                      onClick={stop}
                      className="rounded bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-500"
                    >
                      停止
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={generate}
                      disabled={busy}
                      className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
                    >
                      生成正文
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={saveBody}
                    disabled={busy || generating || mode !== 'body'}
                    className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                  >
                    保存正文
                  </button>
                  <button
                    type="button"
                    onClick={saveDraft}
                    disabled={busy || generating || !text?.draft || mode !== 'draft'}
                    className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50"
                  >
                    保存草稿
                  </button>
                  <button
                    type="button"
                    onClick={adopt}
                    disabled={busy || generating || !text?.draft}
                    className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    采纳为正文
                  </button>
                  <button
                    type="button"
                    onClick={discard}
                    disabled={busy || generating || !text?.draft}
                    className="rounded border border-amber-800 px-3 py-1.5 text-sm text-amber-300 hover:text-amber-200 disabled:opacity-50"
                  >
                    丢弃草稿
                  </button>
                </div>

                <GenerationStream text={streamText} generating={generating} />

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setMode('body')}
                    className={`rounded px-3 py-1 text-sm ${
                      mode === 'body' ? 'bg-slate-800 text-white' : 'text-slate-400'
                    }`}
                  >
                    已采纳正文
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode('draft')}
                    disabled={!text?.draft}
                    className={`rounded px-3 py-1 text-sm disabled:opacity-40 ${
                      mode === 'draft' ? 'bg-slate-800 text-white' : 'text-slate-400'
                    }`}
                  >
                    AI 草稿
                  </button>
                </div>

                {mode === 'body' ? (
                  <SceneTextView
                    title="已采纳正文"
                    value={bodyDraft}
                    onChange={setBodyDraft}
                    disabled={busy || generating}
                    placeholder="还没有正文。可以先点「生成正文」，也可以直接手写。"
                  />
                ) : (
                  <SceneTextView
                    title="AI 草稿"
                    value={aiDraft}
                    onChange={setAiDraft}
                    disabled={busy || generating}
                    placeholder="AI 草稿会出现在这里，可先修改再采纳。"
                  />
                )}

                {text?.draft && !generating && (
                  <DiffPanel oldText={text.body ?? ''} newText={aiDraft} />
                )}
              </>
            )}
          </section>

          <aside className="min-w-0 space-y-4">
            <ContextPreview
              data={preview}
              loading={previewLoading}
              error={previewError}
            />
            {revision ? (
              <section className="space-y-2 rounded border border-slate-800 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-medium text-slate-300">修订全文</h3>
                  <button
                    type="button"
                    onClick={() => setRevision(null)}
                    className="text-xs text-slate-400 hover:text-white"
                  >
                    关闭
                  </button>
                </div>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-300">
                  {revision.content}
                </pre>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => restoreRevision(revision.id)}
                  className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50"
                >
                  恢复此版本
                </button>
              </section>
            ) : (
              <RevisionHistory
                revisions={text?.revisions ?? []}
                busy={busy}
                onOpen={openRevision}
                onRestore={restoreRevision}
              />
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 注册路由与侧栏**

Modify `frontend/src/App.tsx`：

```tsx
import Writing from './pages/Writing'
```

`NAV` 在「章节设计」后加：

```tsx
  { to: '/write', label: '写作台' },
```

`Routes` 加：

```tsx
          <Route path="/write" element={<Writing />} />
```

- [ ] **Step 3: 构建**

Run: `cd frontend && pnpm build`
Expected: build 干净，无 TypeScript 错误。

- [ ] **Step 4: 前端既有测试**

Run: `cd frontend && pnpm vitest run`
Expected: 30 passed。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Writing.tsx frontend/src/App.tsx
git commit -m "feat(frontend): 写作台页面与流式执笔交互"
```

---

### Task 14: 手工走查、真实模型复验与阶段文档

**Files:**
- Create: `docs/superpowers/plans/2026-10-18-p2a-walkthrough.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- 本任务由控制方 / 实施者手工执行，不新增产品代码；发现缺陷时回到对应任务修复。

- [ ] **Step 1: 跑全量基线**

Run: `uv run --directory backend pytest -q`
Expected: 421 passed。

Run: `cd frontend && pnpm vitest run && pnpm build`
Expected: 30 passed；build 干净。

- [ ] **Step 2: 临时数据目录走查（不调用模型）**

1. 新建临时目录并设 `STORYFORGE_DATA_DIR`；启动后端与前端（端口用现有开发命令）。
2. 建项目 → 建卷 / 章 / 场景（至少两场）。
3. 打开 `/write`：
   - 左侧树显示「未写」；
   - 选场景后右侧上下文预览出现槽位（无模型调用）；
   - 手写正文并保存 → 树变「已写」，修订历史出现「作者保存」；
   - 重复保存同样内容 → 不新增修订；
   - 直接在数据库插入一条 `scene_draft` 或用临时脚本伪造草稿，验证：草稿视图、diff、采纳、丢弃、恢复。
4. 切项目 / 切场景：在途请求不覆盖新选择；有未保存修改时出现确认。
5. 空态：无项目、无卷章、未选场景三种文案正确。
6. 把结果写入 `docs/superpowers/plans/2026-10-18-p2a-walkthrough.md`，逐项勾选并记录发现。

- [ ] **Step 3: 真实模型复验（作者库副本）**

1. **先确认额度**：阿里云百炼免费额度余量；本段建议只用 `qwen3.8-flash`。
2. 用 SQLite 备份 API 复制作者库到临时目录，连同 `secrets.bin`、`settings.json`、`-wal`、`-shm` 一起复制。
3. 以 `STORYFORGE_DATA_DIR=<副本>` 启动后端；确认：
   - 迁移 v4 执行一次并生成 `backups/pre-migration-v4-*`；
   - 原有项目、条目、角色卡一条不少；二次启动不重复迁移；
   - 「执笔」预置出现。
4. 在副本的工作室给执笔绑定模型（服务商与密钥来自副本的 `secrets.bin`）。
5. 若副本没有可用场景，**只在副本里**补建一卷 / 一章 / 两场，并补必要的人物 / 设定。
6. 走通：
   - 上下文预览可见；
   - 生成一场，观察 `delta` 分块到达；
   - 再生成一场并在中途点「停止」，确认运行记录保留部分内容；
   - 编辑草稿 → 查看 diff → 采纳 → 检查正文、字数、修订历史；
   - 手动保存一次、恢复一次，确认修订来源；
   - 用 `GET /api/projects/{id}/search?q=<正文短句>` 检索正文，确认命中场景。
7. 记录实际耗时、估算 token、费用、控制台报错（应为 0）；复验结束后删除副本与临时目录。作者原库哈希前后一致。

- [ ] **Step 4: 更新 CLAUDE.md**

1. 路线图：把 P2 行拆成 **P2a 执笔闭环（本段）** 与后续 P2 项；P2a 状态写明「✅ 完成（2026-10-18 通过真实模型复验）」或如实写明未通过项。
2. 阶段记录追加一段「2026-10-18 · P2a 执笔闭环」，必须包含：
   - 设计与计划路径；
   - 数据变化（`scene.body`、迁移 v4、两张新表、FTS 版本 2）；
   - 流式端点与事件协议；
   - 执笔预置与三个新槽位；
   - 前端写作台；
   - 测试数字（后端 / 前端 / build）；
   - 真实模型复验的实际调用次数、耗时、token 估算与额度；
   - 遗留（检查、回写、批量、导出、精确 usage、段落级 diff 等）。
3. §8 变更记录追加本段裁定：
   - P2 拆为 P2a；
   - 写作台独立页面、Markdown 源码编辑；
   - 逐场景手动生成、整场 diff + 整份采纳；
   - 草稿与正文分离、修订三种来源；
   - 流式 token 用估算；
   - `scene.body` 走迁移 v4、冻结字面量；
   - 正文入 FTS 并升索引版本；
   - `has_body` 派生、不扩展状态词表。
4. 如实记录未完成项；不要把未验证的检查写成已完成。

- [ ] **Step 5: 提交文档**

```bash
git add docs/superpowers/plans/2026-10-18-p2a-walkthrough.md CLAUDE.md
git commit -m "docs: 归档 P2a 走查与阶段记录"
```

---

## 自审记录（计划完成后核对）

- **Spec 覆盖**：数据模型（Task 1）、运行时准备（Task 2）、槽位（Task 3）、执笔预置（Task 4）、草稿 / 正文 / 修订（Task 5、7）、流式与取消（Task 6）、上下文预览（Task 8）、FTS 与 `has_body`（Task 9）、前端纯逻辑（Task 10）、组件与页面（Task 11–13）、验证与文档（Task 14）。
- **明确不做**：检查、回写、批量、导出、TipTap、结果缓存、精确 usage 均未安排任务。
- **类型一致性**：`PreparedPrompt` 字段在各任务中一致；`SceneTextState` / `RevisionSummary` / `ContextPreview` 前后端命名一致；`has_body` 在模型、树、前端类型三处一致。
