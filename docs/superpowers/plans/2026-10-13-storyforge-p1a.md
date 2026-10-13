# StoryForge P1a「故事内核」实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「灵感 → 解析 → 架构推荐并排对比 → 故事圣经」这条故事内核链路，并让智能体运行时的每一次调用都在调试台里完全可见。

**Architecture:** 后端 FastAPI 分四层（api / services / runtime / db），其中 `runtime` 不依赖 FastAPI，可用纯 pytest 覆盖。运行时链路固定为「槽位收集 → 预算裁剪 → 提示词渲染 → 模型调用 → 契约校验 → 落库」，每一步的产物都写进 `generation_run`，调试台只是这张表的只读视图。前端 React 五页直连后端接口。

**Tech Stack:** Python 3.13 + uv + FastAPI + SQLAlchemy 2 + Pydantic 2 + httpx + Jinja2；React + TypeScript + Vite + Tailwind + TipTap（pnpm）。

**Spec:** `docs/superpowers/specs/2026-10-13-storyforge-p1a-design.md`

## Global Constraints

- **权威依据**：`StoryForge-产品设计文档.md` v1.0 是唯一设计依据，冲突时以它为准。
- **数据位置**：一律在程序目录之外，`%LOCALAPPDATA%\StoryForge\`；开发期用环境变量 `STORYFORGE_DATA_DIR` 覆盖。程序本体只读。
- **密钥**：只经 Windows DPAPI 加密存在 `secrets.bin`，任何接口响应只回显屏蔽态（如 `sk-****abcd`），绝不返回明文。
- **分层约束**：`app/api/` 不写业务逻辑；`app/services/` 不 import fastapi；`app/runtime/` 不 import fastapi 或 sqlalchemy。
- **作者原文不可覆盖**：`idea.raw_text` 任何情况下不得被 AI 产出覆写（D-04）。
- **代码风格**：标识符与代码用英文；注释、界面文案、提示词用中文。注释只在「为什么」不明显处写。
- **依赖下限**：fastapi>=0.143、sqlalchemy>=2.1、pydantic>=2.14、httpx>=0.28、jinja2>=3.1、uvicorn>=0.54、pytest>=9.1。
- **不使用重型依赖**：JSON Schema 校验手写子集，不引入 `jsonschema`。

## 关键接口契约（跨任务共用，实现时必须逐字一致）

```python
# app/runtime/schema.py
@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    data: Any | None

def extract_json(text: str) -> Any | None: ...
def validate_json(data: Any, schema: dict) -> tuple[bool, list[str]]: ...
def apply_contract(raw_text: str, schema: dict | None) -> tuple[Any | None, bool, str | None]: ...

# app/runtime/pricing.py
def estimate_tokens(text: str) -> int: ...
def compute_cost(prompt_tokens: int, completion_tokens: int, prices: dict | None) -> float: ...

# app/runtime/context.py
class SlotSource(Protocol):
    def project_core(self) -> str | None: ...
    def parsed_idea(self) -> str | None: ...
    def raw_idea(self) -> str | None: ...
    def story_bible(self) -> str | None: ...
    def architecture(self) -> str | None: ...
    def tool_library(self) -> str | None: ...
    def summarize(self, slot_key: str, text: str) -> str: ...

@dataclass(frozen=True)
class SlotSpec:
    key: str
    label: str
    priority: int
    over_budget: str            # "never" | "summarize" | "drop"
    order: int

SLOT_REGISTRY: dict[str, SlotSpec]

@dataclass(frozen=True)
class ContextBundle:
    contents: dict[str, str]
    trimmed: dict[str, str]     # slot_key -> 动作说明，如 "压缩为要点" / "已丢弃"
    estimated_tokens: int
    over_budget: bool

def build_context(version_slots: list[str], source: SlotSource,
                  token_budget: int, compressor=None) -> ContextBundle: ...

# app/runtime/render.py
def render(template: str, context: dict[str, str]) -> str: ...

# app/runtime/llm.py
@dataclass(frozen=True)
class ChatError:
    kind: str        # network | auth | rate_limit | server | timeout | bad_request
    message: str
    status: int | None = None

@dataclass(frozen=True)
class ChatConfig:
    base_url: str
    api_key: str
    model: str

@dataclass(frozen=True)
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str | None
    partial: bool = False
    error: ChatError | None = None

class ChatClient(Protocol):
    async def complete(self, config, messages, params) -> ChatResult: ...
    def stream(self, config, messages, params) -> AsyncIterator[str]: ...

class HttpxChatClient:
    def __init__(self, transport=None) -> None: ...

# app/runtime/execute.py
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
    prices: dict | None

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
    status: str
    error: dict | None
    trimmed: dict[str, str]

def execute_run(inp: ExecuteInput, source: SlotSource, client: ChatClient) -> RunResult: ...
```

---

### Task 1: 仓库骨架、配置与数据目录

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`、`backend/app/api/__init__.py`、`backend/app/services/__init__.py`、`backend/app/runtime/__init__.py`、`backend/app/db/__init__.py`、`backend/app/db/models/__init__.py`、`backend/app/crypto/__init__.py`、`backend/app/agents/__init__.py`、`backend/app/tests/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_config.py`
- Modify: `CLAUDE.md` §7（阶段记录）

**Interfaces:**
- Consumes: 无
- Produces: `app.config.data_dir() -> Path`、`app.config.db_path() -> Path`、`app.config.secrets_path() -> Path`、`app.config.load_settings() -> dict`、`app.config.save_settings(d) -> None`、`app.main.app`（FastAPI 实例）

> 注意：源码包名为 `app`，测试目录放 `backend/tests/`（与 `app/` 平级），这样 `uv run pytest` 从 `backend/` 起跑能直接 import `app`。

- [ ] **Step 1: 初始化 uv 项目**

```bash
cd backend 2>/dev/null || mkdir -p backend
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv init --name storyforge-backend --python 3.13 --no-workspace --bare
```

- [ ] **Step 2: 写 `backend/pyproject.toml`**

```toml
[project]
name = "storyforge-backend"
version = "0.1.0"
description = "StoryForge 长篇小说创作台后端"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.143",
    "uvicorn[standard]>=0.54",
    "sqlalchemy>=2.1",
    "pydantic>=2.14",
    "httpx>=0.28",
    "jinja2>=3.1",
]

[dependency-groups]
dev = ["pytest>=9.1", "pytest-asyncio>=1.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: 安装依赖**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv sync
```

Expected: 生成 `.venv/` 与 `uv.lock`，无报错。

- [ ] **Step 4: 写失败测试 `backend/tests/test_config.py`**

```python
import json
import os

from app import config


def test_data_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    assert config.data_dir() == tmp_path


def test_data_dir_creates_directory(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "StoryForge"
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(target))
    assert config.data_dir().is_dir()


def test_db_path_lives_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    assert config.db_path().parent == tmp_path
    assert config.db_path().name == "storyforge.db"


def test_secrets_path_lives_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    assert config.secrets_path().parent == tmp_path
    assert config.secrets_path().name == "secrets.bin"


def test_load_settings_returns_defaults_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    settings = config.load_settings()
    assert settings["context_token_budget"] == 8000
    assert settings["default_params"] == {"temperature": 0.7, "max_tokens": 4096}


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    config.save_settings({"context_token_budget": 1234})
    assert config.load_settings()["context_token_budget"] == 1234
    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert on_disk["context_token_budget"] == 1234


def test_missing_keys_are_backfilled_on_load(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYFORGE_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.json").write_text('{"context_token_budget": 500}', encoding="utf-8")
    settings = config.load_settings()
    assert settings["context_token_budget"] == 500
    assert settings["default_params"] == {"temperature": 0.7, "max_tokens": 4096}
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app'` 或 `AttributeError`。

- [ ] **Step 6: 写 `backend/app/config.py`**

```python
"""本机数据目录与全局设置的唯一入口。

程序本体只读，所有可变数据都在 %LOCALAPPDATA%\\StoryForge 之下。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SETTINGS: dict = {
    "context_token_budget": 8000,
    "default_params": {"temperature": 0.7, "max_tokens": 4096},
    "model_routing": {},
    "budget_alert": None,
}


def data_dir() -> Path:
    override = os.environ.get("STORYFORGE_DATA_DIR")
    if override:
        base = Path(override)
    else:
        local_appdata = os.environ.get("LOCALAPPDATA")
        base = (Path(local_appdata) if local_appdata else Path.home() / ".local" / "share") / "StoryForge"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "storyforge.db"


def secrets_path() -> Path:
    return data_dir() / "secrets.bin"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def project_assets_dir(project_id: str) -> Path:
    path = data_dir() / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict:
    path = settings_path()
    stored: dict = {}
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stored = {}
    merged = {**DEFAULT_SETTINGS, **stored}
    # default_params 逐键合并，避免旧设置文件缺键后被整体覆盖
    merged["default_params"] = {**DEFAULT_SETTINGS["default_params"], **stored.get("default_params", {})}
    return merged


def save_settings(values: dict) -> None:
    merged = {**load_settings(), **values}
    settings_path().write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

- [ ] **Step 7: 写 `backend/app/main.py`**

```python
"""FastAPI 装配入口。

P1a 只挂 /api/health；后续任务的 router 依次追加到 include_router 区。
"""

from __future__ import annotations

from fastapi import FastAPI

from app import config

app = FastAPI(title="StoryForge", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_config.py -v
```

Expected: 7 passed。

- [ ] **Step 9: 手工验证服务能起**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run uvicorn app.main:app --port 8756 &
sleep 3
curl -s http://127.0.0.1:8756/api/health
```

Expected: `{"status":"ok","data_dir":"..."}`。验证后停掉该进程。

- [ ] **Step 10: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(backend): 项目骨架、配置与数据目录"
```

---

### Task 2: 数据库层

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models/__init__.py`
- Create: `backend/app/db/models/project.py`、`idea.py`、`architecture.py`、`agent.py`、`run.py`、`config_models.py`、`tool.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`
- Modify: `backend/app/main.py`（启动时建表）

**Interfaces:**
- Consumes: `app.config.db_path()`
- Produces:
  - `app.db.base.Base`（DeclarativeBase）、`app.db.base.new_id() -> str`、`app.db.base.TimestampMixin`
  - `app.db.session.engine`、`app.db.session.SessionLocal`、`app.db.session.init_db() -> None`、`app.db.session.get_session()`（FastAPI 依赖）
  - 模型类：`Project`、`Idea`、`Architecture`、`Act`、`ToolTemplate`、`Agent`、`AgentVersion`、`GenerationRun`、`Provider`、`Setting`

- [ ] **Step 1: 写失败测试 `backend/tests/conftest.py`**

```python
import os
import tempfile

import pytest

# 必须在导入 app.* 之前设好，engine 在 import 时就会读数据目录
_TMP = tempfile.mkdtemp(prefix="storyforge-test-")
os.environ["STORYFORGE_DATA_DIR"] = _TMP


@pytest.fixture(scope="session")
def data_dir_path():
    from app import config

    return config.data_dir()


@pytest.fixture()
def session():
    from app.db import session as db_session

    db_session.init_db()
    with db_session.SessionLocal() as s:
        yield s
```

- [ ] **Step 2: 写失败测试 `backend/tests/test_models.py`**

```python
from app.db.base import new_id
from app.db.models import Agent, AgentVersion, GenerationRun, Idea, Project


def test_new_id_is_unique_string():
    a, b = new_id(), new_id()
    assert isinstance(a, str) and len(a) == 36
    assert a != b


def test_project_roundtrip(session):
    project = Project(name="验尸官", genre="悬疑")
    session.add(project)
    session.commit()
    fetched = session.get(Project, project.id)
    assert fetched.name == "验尸官"
    assert fetched.logic_check_level == "loose"
    assert fetched.created_at is not None


def test_raw_idea_is_stored_separately_from_parsed(session):
    project = Project(name="p")
    session.add(project)
    session.commit()
    idea = Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官", tags_json=["悬疑"])
    session.add(idea)
    session.commit()
    assert idea.raw_text == "能听见死者遗言的验尸官"
    assert idea.parsed_json is None
    idea.parsed_json = {"genre": "悬疑"}
    session.commit()
    assert idea.raw_text == "能听见死者遗言的验尸官"  # 解析不回写原文（D-04）


def test_agent_current_version_pointer(session):
    agent = Agent(name="架构师", task_type="architecture")
    session.add(agent)
    session.commit()
    version = AgentVersion(agent_id=agent.id, version_no=1, system_prompt="你是架构师")
    session.add(version)
    session.commit()
    agent.current_version_id = version.id
    session.commit()
    assert session.get(Agent, agent.id).current_version_id == version.id


def test_generation_run_stores_full_audit_trail(session):
    project = Project(name="p")
    session.add(project)
    session.commit()
    run = GenerationRun(
        project_id=project.id,
        model="test-model",
        rendered_prompt="渲染后的提示词",
        raw_output="原始返回",
        prompt_tokens=10,
        completion_tokens=20,
        cost_estimate=0.0014,
        status="ok",
    )
    session.add(run)
    session.commit()
    assert run.rendered_prompt == "渲染后的提示词"
    assert run.structured is False
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`。

- [ ] **Step 4: 写 `backend/app/db/base.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

- [ ] **Step 5: 写 `backend/app/db/session.py`**

```python
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.db.base import Base

engine = create_engine(
    f"sqlite:///{config.db_path()}",
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:
    # WAL 让读写并发不互相阻塞；外键约束 SQLite 默认关闭，必须显式打开
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app.db import models  # noqa: F401  确保所有模型已注册到 metadata

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

- [ ] **Step 6: 写模型文件**

`backend/app/db/models/project.py`：

```python
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str | None] = mapped_column(String(100), default=None)
    sub_genre: Mapped[str | None] = mapped_column(String(100), default=None)
    tone: Mapped[str | None] = mapped_column(String(200), default=None)
    target_length: Mapped[int | None] = mapped_column(default=None)
    writing_lang: Mapped[str] = mapped_column(String(20), default="zh")
    cover_path: Mapped[str | None] = mapped_column(String(500), default=None)
    # P1a 只存不用，P2 的逻辑自检会读它
    logic_check_level: Mapped[str] = mapped_column(String(20), default="loose")
    summary: Mapped[str | None] = mapped_column(Text, default=None)
```

`backend/app/db/models/idea.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Idea(IdMixin, TimestampMixin, Base):
    __tablename__ = "idea"

    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    # 作者原话。任何 AI 产出都不得写进这个字段（D-04）
    raw_text: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(30), default="raw")
```

`backend/app/db/models/architecture.py`：

```python
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Architecture(IdMixin, TimestampMixin, Base):
    __tablename__ = "architecture"

    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    tool_ref: Mapped[str | None] = mapped_column(String(100), default=None)
    logline: Mapped[str | None] = mapped_column(Text, default=None)
    theme: Mapped[str | None] = mapped_column(Text, default=None)
    premise: Mapped[str | None] = mapped_column(Text, default=None)
    ending_direction: Mapped[str | None] = mapped_column(Text, default=None)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class Act(IdMixin, TimestampMixin, Base):
    __tablename__ = "act"

    architecture_id: Mapped[str] = mapped_column(
        ForeignKey("architecture.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(default=0)
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str | None] = mapped_column(Text, default=None)
    target_word_ratio: Mapped[float | None] = mapped_column(Float, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
```

`backend/app/db/models/tool.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ToolTemplate(IdMixin, TimestampMixin, Base):
    """创作工具库模板。builtin=True 时来自 app/tools_lib，project_id 为空。"""

    __tablename__ = "tool_template"

    key: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checklist_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), default=None
    )
```

`backend/app/db/models/agent.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Agent(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent"

    name: Mapped[str] = mapped_column(String(120))
    role_label: Mapped[str] = mapped_column(String(60), default="")
    color: Mapped[str] = mapped_column(String(20), default="#6366f1")
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36), default=None)


class AgentVersion(IdMixin, TimestampMixin, Base):
    """不可变快照。改提示词 = 插入新版本并移动 Agent.current_version_id（D-06）。"""

    __tablename__ = "agent_version"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(default=1)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model_binding_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    param_profile: Mapped[str] = mapped_column(String(30), default="balanced")
    context_slots_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_schema_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    skills_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    trigger_mode: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
```

`backend/app/db/models/run.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class GenerationRun(IdMixin, TimestampMixin, Base):
    """一次智能体运行的全部审计信息。调试台是这张表的只读视图。"""

    __tablename__ = "generation_run"

    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True, default=None
    )
    agent_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    agent_version_id: Mapped[str | None] = mapped_column(String(36), default=None)
    provider_id: Mapped[str | None] = mapped_column(String(36), default=None)
    model: Mapped[str] = mapped_column(String(120), default="")
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rendered_prompt: Mapped[str] = mapped_column(Text, default="")
    input_digest: Mapped[str] = mapped_column(String(64), default="")
    raw_output: Mapped[str] = mapped_column(Text, default="")
    parsed_json: Mapped[Any | None] = mapped_column(JSON, default=None)
    structured: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    # ok | partial | error
    status: Mapped[str] = mapped_column(String(20), default="ok")
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    trimmed_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
```

`backend/app/db/models/config_models.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Provider(IdMixin, TimestampMixin, Base):
    """服务商接入信息。密钥明文不进这张表，只留 api_key_ref（D-01）。"""

    __tablename__ = "provider"

    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(60), default="custom")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_key_ref: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(default=0)


class Setting(IdMixin, TimestampMixin, Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value_json: Mapped[Any | None] = mapped_column(JSON, default=None)
```

`backend/app/db/models/__init__.py`：

```python
from app.db.models.agent import Agent, AgentVersion
from app.db.models.architecture import Act, Architecture
from app.db.models.config_models import Provider, Setting
from app.db.models.idea import Idea
from app.db.models.project import Project
from app.db.models.run import GenerationRun
from app.db.models.tool import ToolTemplate

__all__ = [
    "Act",
    "Agent",
    "AgentVersion",
    "Architecture",
    "GenerationRun",
    "Idea",
    "Project",
    "Provider",
    "Setting",
    "ToolTemplate",
]
```

- [ ] **Step 7: 在 `backend/app/main.py` 里建表**

把 `main.py` 改为：

```python
from __future__ import annotations

from fastapi import FastAPI

from app import config
from app.db.session import init_db

app = FastAPI(title="StoryForge", version="0.1.0")
init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/ -v
```

Expected: 全部通过（test_config 7 项 + test_models 5 项）。

- [ ] **Step 9: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(db): SQLite 数据层与 P1a 数据模型"
```

---

### Task 3: DPAPI 密钥加密

**Files:**
- Create: `backend/app/crypto/dpapi.py`
- Create: `backend/tests/test_dpapi.py`

**Interfaces:**
- Consumes: `app.config.secrets_path()`
- Produces: `app.crypto.dpapi.set_secret(ref: str, value: str) -> None`、`get_secret(ref: str) -> str | None`、`delete_secret(ref: str) -> bool`、`list_refs() -> list[str]`、`mask(value: str) -> str`、`is_encryption_available() -> bool`

- [ ] **Step 1: 写失败测试 `backend/tests/test_dpapi.py`**

```python
import pytest

from app.crypto import dpapi


def test_set_then_get_roundtrip():
    dpapi.set_secret("provider:openai", "sk-test-1234567890")
    assert dpapi.get_secret("provider:openai") == "sk-test-1234567890"


def test_get_missing_ref_returns_none():
    assert dpapi.get_secret("provider:nope") is None


def test_delete_removes_secret():
    dpapi.set_secret("provider:temp", "sk-temp")
    assert dpapi.delete_secret("provider:temp") is True
    assert dpapi.get_secret("provider:temp") is None
    assert dpapi.delete_secret("provider:temp") is False


def test_overwrite_replaces_value():
    dpapi.set_secret("provider:x", "first")
    dpapi.set_secret("provider:x", "second")
    assert dpapi.get_secret("provider:x") == "second"


def test_list_refs_never_leaks_values():
    dpapi.set_secret("provider:a", "sk-aaaa")
    refs = dpapi.list_refs()
    assert "provider:a" in refs
    assert all("sk-" not in r for r in refs)


def test_secrets_file_does_not_contain_plaintext():
    from app import config

    dpapi.set_secret("provider:plain", "sk-SUPER-SECRET-VALUE")
    raw = config.secrets_path().read_bytes()
    assert b"SUPER-SECRET-VALUE" not in raw


def test_mask_keeps_only_tail():
    assert dpapi.mask("sk-1234567890abcdef") == "sk-****cdef"
    assert dpapi.mask("ab") == "****"


def test_mask_of_empty_is_empty():
    assert dpapi.mask("") == ""
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_dpapi.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.crypto.dpapi'`。

- [ ] **Step 3: 写 `backend/app/crypto/dpapi.py`**

```python
"""Windows DPAPI 密钥加密（D-01：密钥只在本机加密存储）。

非 Windows 平台降级为明文存储并返回 is_encryption_available() == False，
以便在开发机上跑通测试；打包产物只在 Windows 运行。
"""

from __future__ import annotations

import base64
import ctypes
import json
import sys
from ctypes import wintypes

from app import config

_IS_WINDOWS = sys.platform == "win32"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_ENTROPY = b"StoryForge-v1"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def is_encryption_available() -> bool:
    return _IS_WINDOWS


def _protect(plaintext: str) -> str:
    data = plaintext.encode("utf-8")
    if not _IS_WINDOWS:
        return "plain:" + base64.b64encode(data).decode("ascii")
    out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(_blob(data)),
        "StoryForge",
        ctypes.byref(_blob(_ENTROPY)),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out),
    )
    if not ok:
        raise OSError("CryptProtectData 失败，无法加密密钥")
    try:
        raw = ctypes.string_at(out.pbData, out.cbData)
        return "dpapi:" + base64.b64encode(raw).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _unprotect(stored: str) -> str:
    scheme, _, payload = stored.partition(":")
    raw = base64.b64decode(payload)
    if scheme == "plain":
        return raw.decode("utf-8")
    if scheme != "dpapi":
        raise ValueError(f"无法识别的密钥存储格式: {scheme}")
    out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(_blob(raw)),
        None,
        ctypes.byref(_blob(_ENTROPY)),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out),
    )
    if not ok:
        raise OSError("CryptUnprotectData 失败，密钥可能来自其他机器或用户")
    try:
        return ctypes.string_at(out.pbData, out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _read_store() -> dict[str, str]:
    path = config.secrets_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_store(store: dict[str, str]) -> None:
    config.secrets_path().write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_secret(ref: str, value: str) -> None:
    store = _read_store()
    store[ref] = _protect(value)
    _write_store(store)


def get_secret(ref: str) -> str | None:
    stored = _read_store().get(ref)
    return None if stored is None else _unprotect(stored)


def delete_secret(ref: str) -> bool:
    store = _read_store()
    if ref not in store:
        return False
    del store[ref]
    _write_store(store)
    return True


def list_refs() -> list[str]:
    return sorted(_read_store().keys())


def mask(value: str) -> str:
    """界面只回显屏蔽态，绝不回显明文。"""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    head = "sk-" if value.startswith("sk-") else ""
    return f"{head}****{value[-4:]}"
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_dpapi.py -v
```

Expected: 8 passed。

- [ ] **Step 5: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(crypto): Windows DPAPI 密钥加密与屏蔽回显"
```

---

### Task 4: 输出契约校验器与费用计算

这两个都是纯函数，且都是运行时后续任务的前置，合并为一个任务。

**Files:**
- Create: `backend/app/runtime/__init__.py`（空文件已在 Task 1 建，此处确认存在）
- Create: `backend/app/runtime/schema.py`
- Create: `backend/app/runtime/pricing.py`
- Create: `backend/tests/test_schema.py`
- Create: `backend/tests/test_pricing.py`

**Interfaces:**
- Consumes: 无（纯函数）
- Produces: 见「关键接口契约」中的 `ValidationResult`、`extract_json`、`validate_json`、`apply_contract`、`estimate_tokens`、`compute_cost`

- [ ] **Step 1: 写失败测试 `backend/tests/test_schema.py`**

```python
from app.runtime.schema import apply_contract, extract_json, validate_json

SCHEMA = {
    "type": "object",
    "required": ["genre", "open_questions"],
    "properties": {
        "genre": {"type": "string"},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "fit_score": {"type": "number"},
        "tone": {"type": "string", "enum": ["冷峻", "温暖"]},
    },
}


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_from_markdown_fence():
    text = '好的，这是结果：\n```json\n{"a": 1}\n```\n希望有用。'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_leading_prose_no_fence():
    assert extract_json('以下是解析卡：{"a": 1} 完毕') == {"a": 1}


def test_extract_returns_none_for_garbage():
    assert extract_json("完全不是 JSON") is None


def test_validate_accepts_conforming_object():
    ok, errors = validate_json(
        {"genre": "悬疑", "open_questions": ["主要对手是谁"], "fit_score": 0.8, "tone": "冷峻"},
        SCHEMA,
    )
    assert ok is True and errors == []


def test_validate_reports_missing_required():
    ok, errors = validate_json({"genre": "悬疑"}, SCHEMA)
    assert ok is False
    assert any("open_questions" in e for e in errors)


def test_validate_reports_wrong_type():
    ok, errors = validate_json({"genre": 3, "open_questions": []}, SCHEMA)
    assert ok is False
    assert any("genre" in e for e in errors)


def test_validate_reports_enum_violation():
    ok, errors = validate_json({"genre": "x", "open_questions": [], "tone": "阴沉"}, SCHEMA)
    assert ok is False
    assert any("tone" in e for e in errors)


def test_validate_ignores_unknown_properties():
    ok, _ = validate_json({"genre": "x", "open_questions": [], "extra": 1}, SCHEMA)
    assert ok is True


def test_validate_array_item_type():
    ok, errors = validate_json({"genre": "x", "open_questions": [1, 2]}, SCHEMA)
    assert ok is False
    assert any("open_questions" in e for e in errors)


def test_apply_contract_success_path():
    data, structured, err = apply_contract('```json\n{"genre": "悬疑", "open_questions": []}\n```', SCHEMA)
    assert data == {"genre": "悬疑", "open_questions": []}
    assert structured is True and err is None


def test_apply_contract_degrades_on_bad_json():
    data, structured, err = apply_contract("模型没按格式返回", SCHEMA)
    assert data is None and structured is False
    assert err is not None


def test_apply_contract_degrades_on_schema_violation():
    data, structured, err = apply_contract('{"genre": 5}', SCHEMA)
    assert data is None and structured is False
    assert "genre" in (err or "")


def test_apply_contract_without_schema_marks_unstructured():
    data, structured, err = apply_contract("自由文本", None)
    assert data is None and structured is False
    assert err == "该智能体未定义输出结构"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_schema.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.runtime.schema'`。

- [ ] **Step 3: 写 `backend/app/runtime/schema.py`**

```python
"""输出契约校验（上位文档 §5.5）。

只实现 JSON Schema 的实用子集，不引入 jsonschema 依赖。
解析失败时降级为纯文本并标记「未结构化」，不阻塞作者。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    data: Any | None


def _try_parse(candidate: str) -> Any | None:
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_json(text: str) -> Any | None:
    """从可能带 Markdown 围栏或前后废话的返回里取出 JSON 对象。

    围栏取最后一个可解析的块：模型常在正式答案前先复述一个模板示例，
    取第一个会把示例当成结果，静默返回「格式合法但内容错」的数据。
    宁可解析失败降级为纯文本，也不接受看似合法的错数据。
    """
    if text is None:
        return None
    stripped = text.strip()
    parsed = _try_parse(stripped)
    if parsed is not None:
        return parsed

    for match in reversed(list(_FENCE_RE.finditer(text))):
        parsed = _try_parse(match.group(1).strip())
        if parsed is not None:
            return parsed

    # 没有围栏：取第一个 { 到最后一个 } 之间的片段
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return _try_parse(text[start : end + 1])
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        return _try_parse(text[start : end + 1])
    return None


def _check_type(value: Any, expected: str) -> bool:
    types = _TYPE_MAP.get(expected)
    if types is None:
        return True  # 未知类型不做校验，避免误报
    if expected in ("number", "integer") and isinstance(value, bool):
        return False  # bool 是 int 的子类，但语义上不是数字
    return isinstance(value, types)


def _validate_node(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected and not _check_type(value, expected):
        errors.append(f"{path} 类型应为 {expected}，实际为 {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} 的取值 {value!r} 不在允许范围 {schema['enum']!r} 内")

    if expected == "object" or isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path} 缺少必填字段 {key}")
        for key, sub_schema in properties.items():
            if key in value:
                _validate_node(value[key], sub_schema, f"{path}.{key}", errors)

    if expected == "array" or isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{index}]", errors)
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path} 至少需要 {schema['minItems']} 项，实际 {len(value)} 项")


def validate_json(data: Any, schema: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    _validate_node(data, schema, "$", errors)
    return (not errors), errors


def apply_contract(raw_text: str, schema: dict | None) -> tuple[Any | None, bool, str | None]:
    """返回 (解析结果, 是否结构化, 失败原因)。"""
    if not schema:
        return None, False, "该智能体未定义输出结构"
    data = extract_json(raw_text)
    if data is None:
        return None, False, "返回内容不是合法 JSON"
    ok, errors = validate_json(data, schema)
    if not ok:
        return None, False, "；".join(errors)
    return data, True, None
```

- [ ] **Step 4: 写失败测试 `backend/tests/test_pricing.py`**

```python
from app.runtime.pricing import compute_cost, estimate_tokens


def test_estimate_tokens_empty_string():
    assert estimate_tokens("") == 0


def test_estimate_tokens_counts_cjk_as_one_each():
    assert estimate_tokens("一二三四五六七八九十") == 10


def test_estimate_tokens_counts_latin_as_quarter():
    assert estimate_tokens("abcdefgh") == 2


def test_estimate_tokens_mixed_text():
    text = "一二三四" + "abcd"
    assert estimate_tokens(text) == 5  # 4 CJK + ceil(4/4)


def test_estimate_tokens_is_at_least_one_for_nonempty():
    assert estimate_tokens("a") == 1


def test_compute_cost_with_both_prices():
    prices = {"input": 1.0, "output": 2.0}  # 每百万 token 单价
    cost = compute_cost(1_000_000, 500_000, prices)
    assert cost == 2.0


def test_compute_cost_zero_when_no_usage():
    assert compute_cost(0, 0, {"input": 1.0, "output": 2.0}) == 0.0


def test_compute_cost_zero_when_prices_missing():
    assert compute_cost(1000, 1000, None) == 0.0


def test_compute_cost_partial_prices_uses_zero_for_missing_side():
    assert compute_cost(1_000_000, 1_000_000, {"input": 3.0}) == 3.0
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_pricing.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.runtime.pricing'`。

- [ ] **Step 6: 写 `backend/app/runtime/pricing.py`**

```python
"""token 估算与费用计算。

估算用于「生成前预估」与流式返回缺 usage 时的兜底；
真实 usage 由模型返回并覆盖估算值。
"""

from __future__ import annotations

import math

_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x3040, 0x30FF),
    (0xAC00, 0xD7AF),
)


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _CJK_RANGES)


def estimate_tokens(text: str) -> int:
    """中日韩字符约 1 token/字，其余约 4 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    return max(1, cjk + math.ceil(other / 4))


def compute_cost(prompt_tokens: int, completion_tokens: int, prices: dict | None) -> float:
    """prices 为每百万 token 单价：{"input": x, "output": y}。"""
    if not prices:
        return 0.0
    input_price = float(prices.get("input") or 0.0)
    output_price = float(prices.get("output") or 0.0)
    return (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
```

- [ ] **Step 7: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_schema.py tests/test_pricing.py -v
```

Expected: 14 + 9 = 23 passed。

- [ ] **Step 8: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(runtime): 输出契约校验器与 token 费用计算"
```

---

### Task 5: 上下文组装器（槽位 + 预算 + 裁剪）

**Files:**
- Create: `backend/app/runtime/context.py`
- Create: `backend/tests/test_context.py`

**Interfaces:**
- Consumes: `app.runtime.pricing.estimate_tokens`
- Produces: `SlotSpec`、`SLOT_REGISTRY`、`SlotSource`、`ContextBundle`、`build_context(version_slots, source, token_budget, compressor=None) -> ContextBundle`

- [ ] **Step 1: 写失败测试 `backend/tests/test_context.py`**

```python
from app.runtime.context import SLOT_REGISTRY, build_context


class FakeSource:
    def __init__(self, **fields):
        self._fields = fields

    def project_core(self):
        return self._fields.get("project_core")

    def parsed_idea(self):
        return self._fields.get("parsed_idea")

    def raw_idea(self):
        return self._fields.get("raw_idea")

    def story_bible(self):
        return self._fields.get("story_bible")

    def architecture(self):
        return self._fields.get("architecture")

    def tool_library(self):
        return self._fields.get("tool_library")

    def summarize(self, slot_key, text):
        return f"[摘要]{text[:5]}"


def test_registry_priority_order_matches_spec():
    assert SLOT_REGISTRY["project_core"].priority > SLOT_REGISTRY["parsed_idea"].priority
    assert SLOT_REGISTRY["parsed_idea"].priority > SLOT_REGISTRY["tool_library"].priority
    assert SLOT_REGISTRY["tool_library"].priority > SLOT_REGISTRY["style_samples"].priority


def test_never_trim_slots_are_marked_never():
    assert SLOT_REGISTRY["project_core"].over_budget == "never"


def test_build_context_returns_requested_slots():
    source = FakeSource(project_core="项目：验尸官", parsed_idea="题材：悬疑")
    bundle = build_context(["parsed_idea", "project_core"], source, token_budget=10_000)
    assert bundle.contents == {"project_core": "项目：验尸官", "parsed_idea": "题材：悬疑"}
    assert bundle.trimmed == {}
    assert bundle.over_budget is False


def test_missing_slot_is_skipped_not_errored():
    source = FakeSource(project_core="项目：验尸官")
    bundle = build_context(["project_core", "story_bible"], source, token_budget=10_000)
    assert "story_bible" not in bundle.contents
    assert "story_bible" not in bundle.trimmed


def test_unknown_slot_key_is_skipped():
    source = FakeSource(project_core="项目：验尸官")
    bundle = build_context(["project_core", "不存在的槽位"], source, token_budget=10_000)
    assert list(bundle.contents) == ["project_core"]


def test_under_budget_content_is_untouched():
    source = FakeSource(parsed_idea="题材：悬疑", raw_idea="一个能听见死者遗言的验尸官")
    bundle = build_context(["parsed_idea", "raw_idea"], source, token_budget=1_000_000)
    assert bundle.contents["raw_idea"] == "一个能听见死者遗言的验尸官"
    assert bundle.over_budget is False


def test_lowest_priority_slot_is_dropped_first_when_over_budget():
    # estimate_tokens 对 CJK 约 1 token/字
    source = FakeSource(
        project_core="短",
        parsed_idea="解析卡" * 20,      # 60 tokens
        raw_idea="灵感原话" * 50,        # 200 tokens
    )
    bundle = build_context(
        ["parsed_idea", "raw_idea", "project_core"], source, token_budget=80
    )
    # over_budget 表示「裁完之后仍然超预算」，不是「裁过」。裁掉了什么由 trimmed 记录。
    assert bundle.over_budget is False
    assert "project_core" in bundle.contents        # 最高优先级保留
    assert "raw_idea" not in bundle.contents        # 最低优先级丢弃
    assert bundle.trimmed["raw_idea"] == "已丢弃"
    assert bundle.estimated_tokens <= 80


def test_summarizable_slot_is_compressed_before_dropping():
    source = FakeSource(
        project_core="短",
        parsed_idea="解析卡" * 100,     # 300 tokens
    )
    bundle = build_context(["parsed_idea", "project_core"], source, token_budget=60)
    # FakeSource.summarize 返回 f"[摘要]{text[:5]}"，"解析卡"*100 的前 5 字是 "解析卡解析"
    assert bundle.contents["parsed_idea"] == "[摘要]解析卡解析"
    assert bundle.trimmed["parsed_idea"] == "压缩为要点"


def test_drop_is_preferred_over_summarize_for_drop_slots():
    source = FakeSource(project_core="短", tool_library="工具库" * 200)
    bundle = build_context(["tool_library", "project_core"], source, token_budget=60)
    assert "tool_library" not in bundle.contents
    assert bundle.trimmed["tool_library"] == "已丢弃"


def test_trimmed_records_are_populated_for_ui_to_display():
    source = FakeSource(project_core="短", raw_idea="灵感" * 500)
    bundle = build_context(["raw_idea", "project_core"], source, token_budget=50)
    assert set(bundle.trimmed) == {"raw_idea"}


def test_estimated_tokens_is_reported():
    source = FakeSource(project_core="项目" * 10)
    bundle = build_context(["project_core"], source, token_budget=10_000)
    assert bundle.estimated_tokens == 20


def test_build_context_with_no_slots():
    bundle = build_context([], FakeSource(), token_budget=100)
    assert bundle.contents == {} and bundle.trimmed == {} and bundle.estimated_tokens == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_context.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.runtime.context'`。

- [ ] **Step 3: 写 `backend/app/runtime/context.py`**

```python
"""上下文组装（上位文档 §5.4、D-09）。

槽位按优先级取值，超预算时从最低优先级开始裁剪，
裁剪结果必须能被界面明示「这次砍掉了什么」。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.runtime.pricing import estimate_tokens

# 优先级数值越大越优先。100 段永不裁剪。
P_NEVER = 100
P_HIGH = 80
P_MID = 50
P_LOW = 20


class SlotSource(Protocol):
    """项目态只读视图。runtime 只依赖这个协议，不依赖数据库。"""

    def project_core(self) -> str | None: ...
    def parsed_idea(self) -> str | None: ...
    def raw_idea(self) -> str | None: ...
    def story_bible(self) -> str | None: ...
    def architecture(self) -> str | None: ...
    def tool_library(self) -> str | None: ...
    def summarize(self, slot_key: str, text: str) -> str: ...


@dataclass(frozen=True)
class SlotSpec:
    key: str
    label: str
    priority: int
    over_budget: str  # "never" | "summarize" | "drop"


SLOT_REGISTRY: dict[str, SlotSpec] = {
    spec.key: spec
    for spec in (
        SlotSpec("project_core", "项目核心信息", P_NEVER, "never"),
        SlotSpec("story_bible", "故事圣经摘要", P_HIGH, "summarize"),
        SlotSpec("architecture", "幕/卷骨架", P_HIGH, "summarize"),
        SlotSpec("parsed_idea", "灵感解析卡", P_HIGH, "summarize"),
        SlotSpec("raw_idea", "灵感原话", P_MID, "drop"),
        SlotSpec("tool_library", "创作工具库摘要", P_MID, "drop"),
        SlotSpec("style_samples", "风格样本", P_LOW, "drop"),
    )
}


@dataclass(frozen=True)
class ContextBundle:
    contents: dict[str, str] = field(default_factory=dict)
    trimmed: dict[str, str] = field(default_factory=dict)
    estimated_tokens: int = 0
    over_budget: bool = False


def _tokens_of(contents: dict[str, str]) -> int:
    return sum(estimate_tokens(text) for text in contents.values())


def build_context(
    version_slots: list[str],
    source: SlotSource,
    token_budget: int,
    compressor: Callable[[str, str], str] | None = None,
) -> ContextBundle:
    summarize = compressor or source.summarize

    contents: dict[str, str] = {}
    for key in version_slots:
        spec = SLOT_REGISTRY.get(key)
        if spec is None:
            continue  # 未注册的槽位键（如 P1b 才有的场景卡）静默跳过
        value = getattr(source, key)()
        if value:
            contents[key] = value

    trimmed: dict[str, str] = {}
    if _tokens_of(contents) <= token_budget:
        return ContextBundle(contents=contents, estimated_tokens=_tokens_of(contents))

    # 从最低优先级开始依次处理，直到落进预算
    for spec in sorted((SLOT_REGISTRY[k] for k in contents), key=lambda s: s.priority):
        if _tokens_of(contents) <= token_budget:
            break
        if spec.over_budget == "never":
            continue
        if spec.over_budget == "summarize":
            compressed = summarize(spec.key, contents[spec.key])
            trimmed[spec.key] = "压缩为要点"
        else:
            compressed = ""
            trimmed[spec.key] = "已丢弃"
        if compressed:
            contents[spec.key] = compressed
        else:
            del contents[spec.key]

    final_tokens = _tokens_of(contents)
    return ContextBundle(
        contents=contents,
        trimmed=trimmed,
        estimated_tokens=final_tokens,
        over_budget=final_tokens > token_budget,
    )
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_context.py -v
```

Expected: 12 passed。

- [ ] **Step 5: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(runtime): 上下文组装器（槽位 + 预算 + 裁剪明示）"
```

---

### Task 6: 提示词渲染与 LLM 适配器

**Files:**
- Create: `backend/app/runtime/render.py`
- Create: `backend/app/runtime/llm.py`
- Create: `backend/tests/test_render.py`
- Create: `backend/tests/test_llm.py`

**Interfaces:**
- Consumes: `app.runtime.pricing.estimate_tokens`
- Produces:
  - `app.runtime.render.render(template: str, context: dict[str, str]) -> str`、`MissingVariableError`
  - `app.runtime.llm.ChatConfig`、`ChatResult`、`ChatError`、`ChatClient`（Protocol）、`HttpxChatClient(transport=None)`

- [ ] **Step 1: 写失败测试 `backend/tests/test_render.py`**

```python
import pytest

from app.runtime.render import MissingVariableError, render


def test_render_substitutes_variable():
    assert render("解析卡：{{ parsed_idea }}", {"parsed_idea": "题材：悬疑"}) == "解析卡：题材：悬疑"


def test_render_leaves_unknown_braces_alone():
    assert render("字面量 {{ 未注册 }}") == "字面量 {{ 未注册 }}"


def test_render_raises_on_missing_declared_variable():
    with pytest.raises(MissingVariableError) as exc:
        render("解析卡：{{ parsed_idea }}", {})
    assert "parsed_idea" in str(exc.value)


def test_render_with_no_variables_is_identity():
    assert render("你是长篇小说结构顾问。", {}) == "你是长篇小说结构顾问。"


def test_render_handles_multiple_variables():
    out = render("{{ a }} 和 {{ b }}", {"a": "甲", "b": "乙"})
    assert out == "甲 和 乙"
```

- [ ] **Step 2: 写失败测试 `backend/tests/test_llm.py`**

```python
import httpx
import pytest

from app.runtime.llm import ChatConfig, ChatFailure, HttpxChatClient

CONFIG = ChatConfig(base_url="https://api.example.com/v1", api_key="sk-test", model="m1")
MESSAGES = [{"role": "user", "content": "你好"}]


def _client(handler):
    return HttpxChatClient(transport=httpx.MockTransport(handler))


async def test_complete_returns_text_and_usage():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "结果"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 11},
            },
        )

    result = await _client(handler).complete(CONFIG, MESSAGES, {"temperature": 0.3})
    assert result.text == "结果"
    assert result.prompt_tokens == 7 and result.completion_tokens == 11
    assert result.partial is False and result.error is None
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert '"model": "m1"' in captured["body"].replace("'", '"')


async def test_complete_missing_usage_falls_back_to_estimate():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "一二三四"}}]})

    result = await _client(handler).complete(CONFIG, MESSAGES, {})
    assert result.text == "一二三四"
    assert result.completion_tokens == 4  # CJK 估算


@pytest.mark.parametrize(
    ("status", "expected_kind"),
    [(401, "auth"), (403, "auth"), (429, "rate_limit"), (500, "server"), (503, "server")],
)
async def test_error_classification_by_status(status, expected_kind):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "boom"}})

    with pytest.raises(ChatFailure) as exc:
        await _client(handler).complete(CONFIG, MESSAGES, {})
    assert exc.value.error.kind == expected_kind
    assert str(status) in exc.value.error.message or "boom" in exc.value.error.message


async def test_network_error_is_classified():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ChatFailure) as exc:
        await _client(handler).complete(CONFIG, MESSAGES, {})
    assert exc.value.error.kind == "network"


async def test_timeout_is_classified():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(ChatFailure) as exc:
        await _client(handler).complete(CONFIG, MESSAGES, {})
    assert exc.value.error.kind == "timeout"


async def test_stream_yields_content_chunks():
    body = (
        'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request):
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    chunks = [c async for c in _client(handler).stream(CONFIG, MESSAGES, {})]
    assert chunks == ["你", "好"]
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_render.py tests/test_llm.py -v
```

Expected: FAIL — `ModuleNotFoundError`。

- [ ] **Step 4: 写 `backend/app/runtime/render.py`**

```python
"""提示词渲染。

用 Jinja2 之外的轻量替换：模板里只有 `{{ 变量名 }}` 一种语法，
变量名用英文且必须与槽位键一致。缺变量直接报错，不静默留空。
"""

from __future__ import annotations

import re

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class MissingVariableError(ValueError):
    """模板引用了未提供的变量。渲染失败不静默，让作者看到缺了什么。"""


def render(template: str, context: dict[str, str]) -> str:
    missing: list[str] = []

    def _substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in context:
            missing.append(name)
            return match.group(0)
        return context[name]

    rendered = _VAR_RE.sub(_substitute, template)
    if missing:
        raise MissingVariableError(f"提示词引用了未提供的变量：{'、'.join(sorted(set(missing)))}")
    return rendered
```

- [ ] **Step 5: 写 `backend/app/runtime/llm.py`**

```python
"""OpenAI 兼容的 LLM 适配器。

只实现一套协议：DeepSeek、Moonshot、智谱、Ollama、LM Studio、自建代理
都提供 OpenAI 兼容端点，接入新服务商 = 加一行预设（上位文档 §4.10）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.runtime.pricing import estimate_tokens

_ERROR_KINDS = {
    400: "bad_request",
    401: "auth",
    403: "auth",
    404: "bad_request",
    429: "rate_limit",
}


@dataclass(frozen=True)
class ChatError:
    kind: str  # network | auth | rate_limit | server | timeout | bad_request
    message: str
    status: int | None = None


class ChatFailure(Exception):
    """带已分类原因与已收内容的调用失败。已收内容不丢。"""

    def __init__(self, error: ChatError, partial_text: str = "") -> None:
        super().__init__(error.message)
        self.error = error
        self.partial_text = partial_text


@dataclass(frozen=True)
class ChatConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str | None = None
    partial: bool = False
    error: ChatError | None = None


class ChatClient:
    """适配器接口。测试用假实现替换，编排代码不感知 HTTP。"""

    async def complete(self, config: ChatConfig, messages: list[dict], params: dict) -> ChatResult:
        raise NotImplementedError

    def stream(self, config: ChatConfig, messages: list[dict], params: dict) -> AsyncIterator[str]:
        raise NotImplementedError


def _classify(status: int) -> str:
    return _ERROR_KINDS.get(status, "server" if status >= 500 else "bad_request")


def _read_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text[:200] or "服务商未返回可读原因"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if error:
            return str(error)
    return response.text[:200] or "服务商未返回可读原因"


class HttpxChatClient(ChatClient):
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 120.0):
        self._transport = transport
        self._timeout = timeout

    def _endpoint(self, config: ChatConfig) -> str:
        return config.base_url.rstrip("/") + "/chat/completions"

    def _headers(self, config: ChatConfig) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if config.api_key:
            headers["authorization"] = f"Bearer {config.api_key}"
        return headers

    def _body(self, config: ChatConfig, messages: list[dict], params: dict, stream: bool) -> dict:
        body = {"model": config.model, "messages": messages, "stream": stream}
        body.update(params or {})
        return body

    def _wrap_transport_error(self, exc: Exception) -> ChatFailure:
        if isinstance(exc, httpx.TimeoutException):
            return ChatFailure(ChatError("timeout", f"请求超时：{exc}"))
        if isinstance(exc, httpx.TransportError):
            return ChatFailure(ChatError("network", f"网络错误：{exc}"))
        return ChatFailure(ChatError("network", f"调用失败：{exc}"))

    async def complete(self, config: ChatConfig, messages: list[dict], params: dict) -> ChatResult:
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
            try:
                response = await client.post(
                    self._endpoint(config),
                    headers=self._headers(config),
                    json=self._body(config, messages, params, stream=False),
                )
            except Exception as exc:  # noqa: BLE001 — 统一转成可读原因
                raise self._wrap_transport_error(exc) from exc

            if response.status_code >= 400:
                raise ChatFailure(
                    ChatError(
                        _classify(response.status_code),
                        _read_error_message(response),
                        response.status_code,
                    )
                )

            payload = response.json()

        choices = payload.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage = payload.get("usage") or {}
        return ChatResult(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or estimate_tokens(
                "\n".join(m.get("content", "") for m in messages)
            )),
            completion_tokens=int(usage.get("completion_tokens") or estimate_tokens(text)),
            finish_reason=choices[0].get("finish_reason"),
        )

    async def stream(
        self, config: ChatConfig, messages: list[dict], params: dict
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    self._endpoint(config),
                    headers=self._headers(config),
                    json=self._body(config, messages, params, stream=True),
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise ChatFailure(
                            ChatError(
                                _classify(response.status_code),
                                _read_error_message(response),
                                response.status_code,
                            )
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
            except ChatFailure:
                raise
            except Exception as exc:  # noqa: BLE001
                raise self._wrap_transport_error(exc) from exc
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_render.py tests/test_llm.py -v
```

Expected: 15 passed（test_render 5 项 + test_llm 10 项，其中错误分类是 5 个参数化用例）。

- [ ] **Step 7: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(runtime): 提示词渲染与 OpenAI 兼容 LLM 适配器"
```

---

### Task 7: 运行时编排与落库

**Files:**
- Create: `backend/app/runtime/execute.py`
- Create: `backend/tests/test_execute.py`

**Interfaces:**
- Consumes: `build_context`、`render`、`apply_contract`、`compute_cost`、`ChatClient`
- Produces: `ExecuteInput`、`RunResult`、`execute_run(inp, source, client) -> RunResult`（async）

- [ ] **Step 1: 写失败测试 `backend/tests/test_execute.py`**

```python
import httpx
import pytest

from app.runtime.execute import ExecuteInput, execute_run
from app.runtime.llm import HttpxChatClient

SCHEMA = {
    "type": "object",
    "required": ["genre"],
    "properties": {"genre": {"type": "string"}},
}


class FakeSource:
    def __init__(self, **fields):
        self._fields = fields

    def project_core(self):
        return self._fields.get("project_core")

    def parsed_idea(self):
        return self._fields.get("parsed_idea")

    def raw_idea(self):
        return self._fields.get("raw_idea")

    def story_bible(self):
        return self._fields.get("story_bible")

    def architecture(self):
        return self._fields.get("architecture")

    def tool_library(self):
        return self._fields.get("tool_library")

    def summarize(self, slot_key, text):
        return text[:3]


def _input(**overrides) -> ExecuteInput:
    base = dict(
        project_id="p1",
        agent_id="a1",
        version_id="v1",
        provider_id="pr1",
        model="m1",
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        params={"temperature": 0.5},
        system_prompt="解析这段灵感：{{ raw_idea }}",
        context_slots=["raw_idea"],
        output_schema=SCHEMA,
        token_budget=8000,
        prices={"input": 1.0, "output": 2.0},
    )
    base.update(overrides)
    return ExecuteInput(**base)


def _client(handler):
    return HttpxChatClient(transport=httpx.MockTransport(handler))


def _ok_handler(content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            },
        )

    return handler


async def test_successful_run_is_fully_recorded():
    source = FakeSource(raw_idea="能听见死者遗言的验尸官")
    client = _client(_ok_handler('```json\n{"genre": "悬疑"}\n```'))
    result = await execute_run(_input(), source, client)

    assert result.status == "ok"
    assert result.raw_output == '```json\n{"genre": "悬疑"}\n```'
    assert result.parsed == {"genre": "悬疑"}
    assert result.structured is True and result.parse_error is None
    assert result.prompt_tokens == 100 and result.completion_tokens == 50
    assert result.cost_estimate == pytest.approx(0.0002)
    assert result.duration_ms >= 0
    assert result.error is None


async def test_rendered_prompt_reflects_context_and_template():
    source = FakeSource(raw_idea="能听见死者遗言的验尸官")
    result = await execute_run(_input(), source, _client(_ok_handler('{"genre":"悬疑"}')))
    assert result.rendered_prompt == "解析这段灵感：能听见死者遗言的验尸官"


async def test_unstructured_output_degrades_without_error_status():
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(), source, _client(_ok_handler("模型没按格式返回")))
    assert result.status == "ok"
    assert result.structured is False
    assert result.parsed is None
    assert result.parse_error is not None
    assert result.raw_output == "模型没按格式返回"


async def test_schema_violation_degrades_with_reason():
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(), source, _client(_ok_handler('{"genre": 5}')))
    assert result.structured is False
    assert "genre" in (result.parse_error or "")


async def test_provider_error_marks_status_error_and_keeps_reason():
    def handler(request):
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    result = await execute_run(_input(), FakeSource(raw_idea="灵感"), _client(handler))
    assert result.status == "error"
    assert result.error is not None
    assert result.error["kind"] == "rate_limit"
    assert result.raw_output == ""


async def test_trimmed_records_survive_into_result():
    source = FakeSource(raw_idea="灵感" * 500)
    result = await execute_run(
        _input(context_slots=["raw_idea"], token_budget=10), source, _client(_ok_handler("{}"))
    )
    assert result.trimmed  # 非空，界面据此显示「这次砍掉了什么」


async def test_missing_template_variable_is_reported_as_error():
    source = FakeSource(raw_idea=None)  # raw_idea 槽位取不到值
    result = await execute_run(_input(), source, _client(_ok_handler("{}")))
    assert result.status == "error"
    assert "raw_idea" in (result.error or {}).get("message", "")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_execute.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.runtime.execute'`。

- [ ] **Step 3: 写 `backend/app/runtime/execute.py`**

```python
"""运行时编排：槽位收集 → 预算裁剪 → 提示词渲染 → 模型调用 → 契约校验 → 落库产物。

这里不碰数据库、不碰 FastAPI，只产出一个 RunResult，由 services 层负责写库。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.runtime.context import SlotSource, build_context
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


def _failure(
    inp: ExecuteInput,
    started: float,
    message: str,
    *,
    kind: str = "runtime",
    status: str = "error",
    rendered_prompt: str = "",
    raw_output: str = "",
    trimmed: dict[str, str] | None = None,
) -> RunResult:
    prompt_tokens = estimate_tokens(rendered_prompt)
    completion_tokens = estimate_tokens(raw_output)
    return RunResult(
        rendered_prompt=rendered_prompt,
        raw_output=raw_output,
        parsed=None,
        structured=False,
        parse_error=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_estimate=compute_cost(prompt_tokens, completion_tokens, inp.prices),
        duration_ms=int((time.monotonic() - started) * 1000),
        status=status,
        error={"kind": kind, "message": message},
        trimmed=trimmed or {},
    )


async def execute_run(inp: ExecuteInput, source: SlotSource, client: ChatClient) -> RunResult:
    started = time.monotonic()

    bundle = build_context(inp.context_slots, source, inp.token_budget)
    try:
        rendered_prompt = render(inp.system_prompt, bundle.contents)
    except MissingVariableError as exc:
        return _failure(inp, started, str(exc), kind="template", trimmed=bundle.trimmed)

    messages = [{"role": "user", "content": rendered_prompt}]
    config = ChatConfig(base_url=inp.base_url, api_key=inp.api_key, model=inp.model)

    try:
        chat = await client.complete(config, messages, inp.params)
    except ChatFailure as exc:
        # 失败不丢内容：已收到的片段照样返回给作者（上位文档 §4.10）
        return _failure(
            inp,
            started,
            exc.error.message,
            kind=exc.error.kind,
            status="partial" if exc.partial_text else "error",
            rendered_prompt=rendered_prompt,
            raw_output=exc.partial_text,
            trimmed=bundle.trimmed,
        )

    parsed, structured, parse_error = apply_contract(chat.text, inp.output_schema)
    return RunResult(
        rendered_prompt=rendered_prompt,
        raw_output=chat.text,
        parsed=parsed,
        structured=structured,
        parse_error=parse_error,
        prompt_tokens=chat.prompt_tokens,
        completion_tokens=chat.completion_tokens,
        cost_estimate=compute_cost(chat.prompt_tokens, chat.completion_tokens, inp.prices),
        duration_ms=int((time.monotonic() - started) * 1000),
        status="ok",
        error=None,
        trimmed=bundle.trimmed,
    )
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_execute.py -v
```

Expected: 7 passed。

- [ ] **Step 5: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(runtime): 运行时编排（组装→渲染→调用→校验→产出）"
```

---

### Task 8: 项目态槽位源与运行时服务层

把运行时接上数据库：`DbSlotSource` 从项目态取值，`RuntimeService` 负责组装 `ExecuteInput`、调用 `execute_run`、把结果写进 `generation_run`。

**Files:**
- Create: `backend/app/services/__init__.py`（Task 1 已建，确认存在）
- Create: `backend/app/services/slot_source.py`
- Create: `backend/app/services/runtime_service.py`
- Create: `backend/app/services/agent_service.py`
- Create: `backend/tests/test_slot_source.py`
- Create: `backend/tests/test_runtime_service.py`

**Interfaces:**
- Consumes: `app.db.models.*`、`app.runtime.execute.execute_run`、`app.runtime.context.SlotSource`
- Produces:
  - `app.services.slot_source.DbSlotSource(session, project_id, tool_summary="")`
  - `app.services.runtime_service.RuntimeService(session, client=None)`，方法：
    - `execute(project_id, agent_id, extra: dict | None = None) -> tuple[GenerationRun, RunResult]`
    - `resolve_provider(agent_version) -> tuple[Provider | None, str, str, dict]`（provider, base_url, api_key, prices）
  - `app.services.agent_service.list_agents(session) -> list[Agent]`、`create_version(session, agent_id, **fields) -> AgentVersion`、`rollback_to(session, agent_id, version_id) -> Agent`

- [ ] **Step 1: 写失败测试 `backend/tests/test_slot_source.py`**

```python
from app.db.models import Act, Architecture, Idea, Project, ToolTemplate
from app.services.slot_source import DbSlotSource


def _seed(session):
    project = Project(name="验尸官", genre="悬疑", tone="冷峻")
    session.add(project)
    session.commit()
    session.add(Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官"))
    arch = Architecture(
        project_id=project.id, tool_ref="three_act", logline="一个验尸官听见了母亲的话"
    )
    session.add(arch)
    session.commit()
    session.add(Act(architecture_id=arch.id, seq=1, name="第一幕", purpose="建立禁令世界"))
    session.add(ToolTemplate(key="three_act", category="通用结构", name="三幕剧"))
    session.commit()
    return project


def test_raw_idea_returns_author_original(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert source.raw_idea() == "能听见死者遗言的验尸官"


def test_project_core_includes_name_and_genre(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    core = source.project_core()
    assert "验尸官" in core and "悬疑" in core


def test_architecture_renders_act_skeleton(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    text = source.architecture()
    assert "three_act" in text
    assert "第一幕" in text


def test_story_bible_includes_logline(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert "听见了母亲的话" in source.story_bible()


def test_parsed_idea_is_none_before_parsing(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert source.parsed_idea() is None


def test_parsed_idea_returns_json_text_after_parsing(session):
    project = _seed(session)
    idea = session.query(Idea).filter_by(project_id=project.id).one()
    idea.parsed_json = {"genre": "悬疑", "open_questions": ["对手是谁"]}
    session.commit()
    text = DbSlotSource(session, project.id).parsed_idea()
    assert "悬疑" in text and "对手是谁" in text


def test_tool_library_empty_when_no_tools(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    assert "三幕剧" in source.tool_library()


def test_summarize_truncates_long_text(session):
    project = _seed(session)
    source = DbSlotSource(session, project.id)
    summarized = source.summarize("raw_idea", "字" * 300)
    assert len(summarized) < 300
    assert summarized.endswith("……")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_slot_source.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.slot_source'`。

- [ ] **Step 3: 写 `backend/app/services/slot_source.py`**

```python
"""项目态的只读槽位视图。

runtime 只依赖 SlotSource 协议，这个类负责把数据库里的项目态
翻译成槽位文本。P1b/P1c 新增槽位时只扩展这里，不动编排。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Act, Architecture, Idea, Project, ToolTemplate

_SUMMARY_LIMIT = 120


class DbSlotSource:
    def __init__(self, session: Session, project_id: str, tool_summary: str = "") -> None:
        self._session = session
        self._project_id = project_id
        self._tool_summary = tool_summary

    def _project(self) -> Project | None:
        return self._session.get(Project, self._project_id)

    def _idea(self) -> Idea | None:
        return self._session.scalars(
            select(Idea).where(Idea.project_id == self._project_id).order_by(Idea.created_at)
        ).first()

    def _architecture(self) -> Architecture | None:
        return self._session.scalars(
            select(Architecture)
            .where(Architecture.project_id == self._project_id)
            .order_by(Architecture.created_at)
        ).first()

    def project_core(self) -> str | None:
        project = self._project()
        if project is None:
            return None
        lines = [f"项目名称：{project.name}"]
        if project.genre:
            lines.append(f"题材：{project.genre}")
        if project.sub_genre:
            lines.append(f"子类型：{project.sub_genre}")
        if project.tone:
            lines.append(f"调性：{project.tone}")
        if project.target_length:
            lines.append(f"目标字数：{project.target_length}")
        if project.summary:
            lines.append(f"项目简介：{project.summary}")
        return "\n".join(lines)

    def raw_idea(self) -> str | None:
        """作者原话，只读不改（D-04）。"""
        idea = self._idea()
        return idea.raw_text if idea else None

    def parsed_idea(self) -> str | None:
        idea = self._idea()
        if idea is None or not idea.parsed_json:
            return None
        return json.dumps(idea.parsed_json, ensure_ascii=False, indent=2)

    def story_bible(self) -> str | None:
        arch = self._architecture()
        if arch is None:
            return None
        lines = []
        if arch.logline:
            lines.append(f"logline：{arch.logline}")
        if arch.theme:
            lines.append(f"主题句：{arch.theme}")
        if arch.premise:
            lines.append(f"前提：{arch.premise}")
        if arch.ending_direction:
            lines.append(f"结局方向：{arch.ending_direction}")
        return "\n".join(lines) or None

    def architecture(self) -> str | None:
        arch = self._architecture()
        if arch is None:
            return None
        lines = [f"结构工具：{arch.tool_ref or '未指定'}"]
        acts = self._session.scalars(
            select(Act).where(Act.architecture_id == arch.id).order_by(Act.seq)
        ).all()
        for act in acts:
            purpose = f"（{act.purpose}）" if act.purpose else ""
            lines.append(f"第{act.seq}幕 {act.name}{purpose}")
        return "\n".join(lines)

    def tool_library(self) -> str | None:
        if self._tool_summary:
            return self._tool_summary
        tools = self._session.scalars(
            select(ToolTemplate).order_by(ToolTemplate.category, ToolTemplate.key)
        ).all()
        if not tools:
            return None
        return "\n".join(f"[{t.category}] {t.name}：{t.description}" for t in tools)

    def style_samples(self) -> str | None:
        return None  # P2 接入风格样本

    def summarize(self, slot_key: str, text: str) -> str:
        """超预算时的降级压缩。P1a 只截断，不调用模型，避免额外花钱。"""
        collapsed = " ".join(text.split())
        if len(collapsed) <= _SUMMARY_LIMIT:
            return collapsed
        return collapsed[:_SUMMARY_LIMIT] + "……"
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_slot_source.py -v
```

Expected: 8 passed。

- [ ] **Step 5: 写失败测试 `backend/tests/test_runtime_service.py`**

```python
import httpx
import pytest

from app.db.models import Agent, AgentVersion, GenerationRun, Idea, Project, Provider
from app.runtime.llm import HttpxChatClient
from app.services.runtime_service import RuntimeService

ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["genre"],
    "properties": {"genre": {"type": "string"}},
}


def _ok_handler(content='{"genre": "悬疑"}'):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 20},
            },
        )

    return handler


def _seed(session, client_handler=None):
    project = Project(name="验尸官")
    session.add(project)
    provider = Provider(name="测试服务商", base_url="https://api.example.com/v1", api_key_ref="")
    session.add(provider)
    session.commit()
    agent = Agent(name="灵感解析", task_type="idea_parse")
    session.add(agent)
    session.commit()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt="解析这段灵感：{{ raw_idea }}",
        context_slots_json=["raw_idea"],
        output_schema_json=ANALYSIS_SCHEMA,
    )
    session.add(version)
    session.commit()
    agent.current_version_id = version.id
    session.add(Idea(project_id=project.id, raw_text="能听见死者遗言的验尸官"))
    session.commit()
    return project, provider, agent, version


def test_execute_writes_generation_run(session):
    project, provider, agent, version = _seed(session)
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))

    run, result = service.execute(project.id, agent.id)

    assert result.status == "ok"
    stored = session.get(GenerationRun, run.id)
    assert stored.rendered_prompt == "解析这段灵感：能听见死者遗言的验尸官"
    assert stored.raw_output == '{"genre": "悬疑"}'
    assert stored.parsed_json == {"genre": "悬疑"}
    assert stored.structured is True
    assert stored.prompt_tokens == 40
    assert stored.agent_version_id == version.id
    assert stored.model  # 落库时记下实际模型


def test_execute_uses_agent_current_version(session):
    project, provider, agent, version = _seed(session)
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))
    run, _ = service.execute(project.id, agent.id)
    assert session.get(GenerationRun, run.id).agent_version_id == agent.current_version_id


def test_execute_records_provider_error_without_raising(session):
    project, provider, agent, version = _seed(session)

    def handler(request):
        return httpx.Response(500, json={"error": {"message": "内部错误"}})

    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(handler)))
    run, result = service.execute(project.id, agent.id)

    assert result.status == "error"
    assert session.get(GenerationRun, run.id).status == "error"


def test_execute_raises_when_agent_has_no_version(session):
    project, provider, agent, version = _seed(session)
    agent.current_version_id = None
    session.commit()
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))
    with pytest.raises(ValueError, match="没有可用版本"):
        service.execute(project.id, agent.id)


def test_execute_raises_when_no_provider_configured(session):
    project, provider, agent, version = _seed(session)
    session.query(Provider).delete()
    session.commit()
    service = RuntimeService(session, client=HttpxChatClient(transport=httpx.MockTransport(_ok_handler())))
    with pytest.raises(ValueError, match="没有可用的服务商"):
        service.execute(project.id, agent.id)
```

- [ ] **Step 6: 写 `backend/app/services/agent_service.py`**

```python
"""智能体角色卡与版本管理（D-06）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentVersion


def list_agents(session: Session) -> list[Agent]:
    return list(session.scalars(select(Agent).order_by(Agent.created_at)))


def get_version(session: Session, version_id: str) -> AgentVersion | None:
    return session.get(AgentVersion, version_id)


def create_version(session: Session, agent_id: str, **fields) -> AgentVersion:
    """插入新版本并移动 current_version_id。旧版本保留，可回滚。"""
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")

    latest = session.scalars(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.version_no.desc())
    ).first()
    version = AgentVersion(
        agent_id=agent_id,
        version_no=(latest.version_no + 1) if latest else 1,
        system_prompt=fields.get("system_prompt", latest.system_prompt if latest else ""),
        model_binding_json=fields.get(
            "model_binding_json", latest.model_binding_json if latest else {}
        ),
        param_profile=fields.get("param_profile", latest.param_profile if latest else "balanced"),
        context_slots_json=fields.get(
            "context_slots_json", latest.context_slots_json if latest else []
        ),
        output_schema_json=fields.get(
            "output_schema_json", latest.output_schema_json if latest else None
        ),
        skills_json=fields.get("skills_json", latest.skills_json if latest else []),
        trigger_mode=fields.get("trigger_mode", latest.trigger_mode if latest else "manual"),
        note=fields.get("note", ""),
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return version


def rollback_to(session: Session, agent_id: str, version_id: str) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")
    version = session.get(AgentVersion, version_id)
    if version is None or version.agent_id != agent_id:
        raise ValueError(f"版本不属于该智能体：{version_id}")
    agent.current_version_id = version_id
    session.commit()
    return agent


def list_versions(session: Session, agent_id: str) -> list[AgentVersion]:
    return list(
        session.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_no.desc())
        )
    )
```

- [ ] **Step 7: 写 `backend/app/services/runtime_service.py`**

```python
"""把运行时接上数据库：组装 ExecuteInput → execute_run → 写 generation_run。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.crypto import dpapi
from app.db.models import Agent, AgentVersion, GenerationRun, Provider
from app.runtime.execute import ExecuteInput, RunResult, execute_run
from app.runtime.llm import ChatClient, HttpxChatClient
from app.services.slot_source import DbSlotSource


class RuntimeService:
    def __init__(self, session: Session, client: ChatClient | None = None) -> None:
        self._session = session
        self._client = client

    def _resolve_client(self) -> ChatClient:
        """单独成一个方法，测试可以替换它以注入假传输层。"""
        if self._client is None:
            self._client = HttpxChatClient()
        return self._client

    def resolve_provider(
        self, version: AgentVersion
    ) -> tuple[Provider, str, str, dict]:
        """返回 (provider, base_url, api_key, prices)。密钥从 DPAPI 取，不进数据库。"""
        binding = version.model_binding_json or {}
        provider_id = binding.get("provider_id")

        provider: Provider | None = None
        if provider_id:
            provider = self._session.get(Provider, provider_id)
        if provider is None:
            provider = self._session.scalars(
                select(Provider).where(Provider.enabled.is_(True)).order_by(Provider.priority)
            ).first()
        if provider is None:
            raise ValueError("没有可用的服务商，请先在「模型与费用」里配置并启用一家")

        api_key = dpapi.get_secret(provider.api_key_ref) if provider.api_key_ref else ""
        if api_key is None:
            api_key = ""
        prices = binding.get("prices") or {}
        return provider, provider.base_url, api_key, prices

    def execute(
        self, project_id: str, agent_id: str, extra: dict | None = None
    ) -> tuple[GenerationRun, RunResult]:
        agent = self._session.get(Agent, agent_id)
        if agent is None:
            raise ValueError(f"智能体不存在：{agent_id}")
        if not agent.current_version_id:
            raise ValueError(f"智能体「{agent.name}」没有可用版本")

        version = self._session.get(AgentVersion, agent.current_version_id)
        if version is None:
            raise ValueError(f"智能体「{agent.name}」的当前版本已丢失")

        provider, base_url, api_key, prices = self.resolve_provider(version)
        binding = version.model_binding_json or {}
        settings = config.load_settings()

        source = DbSlotSource(self._session, project_id)
        inp = ExecuteInput(
            project_id=project_id,
            agent_id=agent.id,
            version_id=version.id,
            provider_id=provider.id,
            model=binding.get("model") or settings.get("default_model") or provider.name,
            base_url=base_url,
            api_key=api_key,
            params={**settings.get("default_params", {}), **(binding.get("params") or {})},
            system_prompt=version.system_prompt,
            context_slots=version.context_slots_json or [],
            output_schema=version.output_schema_json,
            token_budget=int(settings.get("context_token_budget", 8000)),
            prices=prices,
        )

        result = _run_sync(execute_run, inp, source, self._resolve_client())

        run = GenerationRun(
            project_id=project_id,
            agent_id=agent.id,
            agent_version_id=version.id,
            provider_id=provider.id,
            model=inp.model,
            params_json=inp.params,
            rendered_prompt=result.rendered_prompt,
            raw_output=result.raw_output,
            parsed_json=result.parsed,
            structured=result.structured,
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
        return run, result


def _run_sync(coro_factory, *args):
    """运行 async 运行时。

    services 层被 FastAPI 同步路由与 pytest 同步测试同时调用，
    因此这里按「是否已有事件循环」分派，不强制调用方改成 async。
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory(*args))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro_factory(*args)).result()
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_runtime_service.py -v
```

Expected: 5 passed。

- [ ] **Step 9: 全量测试与提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest -v
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(services): 项目态槽位源与运行时服务层"
```

---

### Task 9: 默认智能体阵容与提示词

**Files:**
- Create: `backend/app/agents/roster.py`
- Create: `backend/app/agents/__init__.py`（Task 1 已建，确认存在）
- Create: `backend/app/services/seed_service.py`
- Create: `backend/tests/test_roster.py`
- Create: `backend/tests/test_seed_service.py`

**Interfaces:**
- Consumes: `app.db.models.Agent`、`AgentVersion`
- Produces:
  - `app.agents.roster.TASK_TYPES`、`DEFAULT_ROSTER: list[dict]`
  - `app.services.seed_service.seed_agents(session) -> int`（幂等：已存在同名智能体则跳过）、`seed_tools(session) -> int`

- [ ] **Step 1: 写失败测试 `backend/tests/test_roster.py`**

```python
from app.agents.roster import DEFAULT_ROSTER, TASK_TYPES


def test_task_types_cover_documented_roster():
    for task in (
        "idea_parse",
        "architecture",
        "worldbuilding",
        "chapter_plan",
        "write",
        "polish",
        "continuity",
        "logic_check",
        "reader",
        "assistant",
    ):
        assert task in TASK_TYPES


def test_roster_defines_the_two_p1a_agents():
    keys = {entry["key"] for entry in DEFAULT_ROSTER}
    assert {"idea_parser", "architect"} <= keys


def test_every_roster_entry_has_required_fields():
    for entry in DEFAULT_ROSTER:
        assert entry["key"] and entry["name"] and entry["task_type"]
        assert entry["system_prompt"].strip()
        assert isinstance(entry["context_slots"], list) and entry["context_slots"]
        assert entry["param_profile"] in {"strict", "balanced", "creative"}


def test_architect_prompt_forbids_deciding_for_the_author():
    architect = next(e for e in DEFAULT_ROSTER if e["key"] == "architect")
    prompt = architect["system_prompt"]
    assert "不替作者决定" in prompt or "只作建议" in prompt


def test_parser_prompt_requires_asking_instead_of_inventing():
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    assert "不许编" in parser["system_prompt"] or "编造" in parser["system_prompt"]


def test_parser_output_schema_lists_documented_fields():
    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    props = parser["output_schema"]["properties"]
    for field in (
        "genre",
        "sub_genre",
        "premise",
        "protagonist_desire",
        "conflict_source",
        "emotional_core",
        "tone",
        "length_expectation",
        "comparable_works",
        "open_questions",
    ):
        assert field in props


def test_architect_output_schema_has_options_and_bible():
    architect = next(e for e in DEFAULT_ROSTER if e["key"] == "architect")
    props = architect["output_schema"]["properties"]
    assert "options" in props and "story_bible_v0" in props
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_roster.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.roster'`。

- [ ] **Step 3: 写 `backend/app/agents/roster.py`**

```python
"""默认智能体阵容（上位文档 §5.2 与附录 A）。

P1a 只预置跑得通故事内核的两个；其余任务类型先登记常量，
P1b/P1c 落地时往 DEFAULT_ROSTER 里追加即可，不改任何运行时代码。
"""

from __future__ import annotations

TASK_TYPES = [
    "idea_parse",
    "architecture",
    "worldbuilding",
    "chapter_plan",
    "write",
    "polish",
    "continuity",
    "logic_check",
    "reader",
    "assistant",
]

IDEA_PARSE_SCHEMA = {
    "type": "object",
    "required": ["genre", "premise", "protagonist_desire", "conflict_source", "open_questions"],
    "properties": {
        "genre": {"type": "string"},
        "sub_genre": {"type": "string"},
        "premise": {"type": "string"},
        "protagonist_desire": {"type": "string"},
        "conflict_source": {"type": "string"},
        "emotional_core": {"type": "string"},
        "tone": {"type": "string"},
        "length_expectation": {"type": "string"},
        "comparable_works": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
}

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["tool", "reason", "fit_score", "risks"],
                "properties": {
                    "tool": {"type": "string"},
                    "reason": {"type": "string"},
                    "fit_score": {"type": "number"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "length_plan": {"type": "string"},
                    "rhythm_shape": {"type": "string"},
                },
            },
        },
        "story_bible_v0": {
            "type": "object",
            "properties": {
                "logline": {"type": "string"},
                "theme": {"type": "string"},
                "premise": {"type": "string"},
                "acts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "purpose": {"type": "string"},
                            "target_word_ratio": {"type": "number"},
                        },
                    },
                },
                "main_characters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "desire": {"type": "string"},
                        },
                    },
                },
                "ending_direction": {"type": "string"},
            },
        },
    },
}

IDEA_PARSER_PROMPT = """你是长篇小说灵感解析师，服务对象是作者。你的产出是结构化的解析卡，不是改写。

【作者原话】
{{ raw_idea }}

要求：
1. 逐项填写解析卡：题材、子类型、一句话前提、主角欲望、核心冲突源、情感内核、调性、篇幅预期、可能参考坐标；
2. 主角欲望要写成「他/她想要什么」，不是「他/她是什么人」；
3. 核心冲突源要指出对撞的两股力量，而不是罗列敌人；
4. 可能参考坐标只写气质相近的作品，不写抄袭对象；
5. 你没把握的地方一律写进 open_questions 向作者提问，不许编造设定填空；
6. 不要改写作者的原话，也不要在返回里复述它。

输出：符合解析卡 schema 的 JSON。"""

ARCHITECT_PROMPT = """你是长篇小说结构顾问，服务对象是作者。你的产出是候选方案加理由，不是最终决定。

【灵感解析卡】
{{ parsed_idea }}

【项目信息】
{{ project_core }}

【可用结构工具】
{{ tool_library }}

要求：
1. 给出 2–3 套适配结构，每套必须引用解析卡中的具体要素说明适配理由，不许泛泛而谈「符合三幕剧」；
2. 每套写明适配度（0–1 的小数）、风险、篇幅分配与节奏形态；
3. 明确写出每套结构的不适用情形；
4. 允许并鼓励杂交方案（如三幕骨架、第二幕内部走七点结构），杂交时要说清是哪两层杂交；
5. 结局方向只作建议，不替作者决定；
6. 同时给出故事圣经 v0：logline、主题句、前提、幕骨架、主要人物、结局方向；
7. 信息不足时在 reason 里说明缺什么，不要编造设定。

输出：符合架构推荐 schema 的 JSON。"""

DEFAULT_ROSTER: list[dict] = [
    {
        "key": "idea_parser",
        "name": "灵感解析师",
        "role_label": "解析",
        "color": "#6366f1",
        "task_type": "idea_parse",
        "system_prompt": IDEA_PARSER_PROMPT,
        "context_slots": ["raw_idea"],
        "output_schema": IDEA_PARSE_SCHEMA,
        "param_profile": "strict",
        "note": "灵感变结构化解析卡，没把握就问，不编。",
    },
    {
        "key": "architect",
        "name": "架构师",
        "role_label": "架构",
        "color": "#0ea5e9",
        "task_type": "architecture",
        "system_prompt": ARCHITECT_PROMPT,
        "context_slots": ["parsed_idea", "project_core", "tool_library"],
        "output_schema": ARCHITECTURE_SCHEMA,
        "param_profile": "strict",
        "note": "推荐结构并并排比较，生成故事圣经 v0。",
    },
]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_roster.py -v
```

Expected: 7 passed。

- [ ] **Step 5: 写失败测试 `backend/tests/test_seed_service.py`**

```python
from app.db.models import Agent, AgentVersion, ToolTemplate
from app.services.seed_service import seed_agents, seed_tools


def test_seed_agents_creates_roster_with_versions(session):
    count = seed_agents(session)
    assert count >= 2
    agent = session.query(Agent).filter_by(name="架构师").one()
    assert agent.current_version_id is not None
    version = session.get(AgentVersion, agent.current_version_id)
    assert "不替作者决定" in version.system_prompt


def test_seed_agents_is_idempotent(session):
    first = seed_agents(session)
    second = seed_agents(session)
    assert second == 0
    assert session.query(Agent).filter_by(name="架构师").count() == 1


def test_seed_tools_loads_builtin_library(session):
    count = seed_tools(session)
    assert count > 0
    keys = {t.key for t in session.query(ToolTemplate).all()}
    assert "three_act" in keys
    assert "save_the_cat" in keys


def test_seed_tools_is_idempotent(session):
    seed_tools(session)
    assert seed_tools(session) == 0


def test_every_seeded_tool_has_a_checklist(session):
    seed_tools(session)
    for tool in session.query(ToolTemplate).all():
        assert tool.checklist_json, f"{tool.key} 缺少校验问题清单"
```

- [ ] **Step 6: 写 `backend/app/services/seed_service.py`**

```python
"""预置数据落库。幂等：已存在则跳过，方便每次启动调用。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion, ToolTemplate

TOOLS_LIB_DIR = Path(__file__).resolve().parent.parent / "tools_lib"


def seed_agents(session: Session) -> int:
    created = 0
    for entry in DEFAULT_ROSTER:
        existing = session.scalars(select(Agent).where(Agent.name == entry["name"])).first()
        if existing is not None:
            continue
        agent = Agent(
            name=entry["name"],
            role_label=entry["role_label"],
            color=entry["color"],
            task_type=entry["task_type"],
            builtin=True,
        )
        session.add(agent)
        session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version_no=1,
            system_prompt=entry["system_prompt"],
            context_slots_json=entry["context_slots"],
            output_schema_json=entry["output_schema"],
            param_profile=entry["param_profile"],
            note=entry.get("note", ""),
        )
        session.add(version)
        session.flush()
        agent.current_version_id = version.id
        created += 1
    session.commit()
    return created


def seed_tools(session: Session) -> int:
    if not TOOLS_LIB_DIR.is_dir():
        return 0
    created = 0
    for path in sorted(TOOLS_LIB_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = payload["key"]
        existing = session.scalars(
            select(ToolTemplate).where(ToolTemplate.key == key, ToolTemplate.builtin.is_(True))
        ).first()
        if existing is not None:
            continue
        session.add(
            ToolTemplate(
                key=key,
                category=payload["category"],
                name=payload["name"],
                description=payload.get("description", ""),
                definition_json=payload.get("definition", {}),
                checklist_json=payload.get("checklist", []),
                builtin=True,
            )
        )
        created += 1
    session.commit()
    return created
```

- [ ] **Step 7: 运行测试**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_roster.py tests/test_seed_service.py -v
```

Expected: `test_seed_agents_*` 通过；`test_seed_tools_*` 在 Task 10 建好工具库前会失败 —— 这是预期的，先做 Task 10。

- [ ] **Step 8: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(agents): 默认智能体阵容与预置服务"
```

---

### Task 10: 创作工具库内置模板

**Files:**
- Create: `backend/app/tools_lib/__init__.py`
- Create: `backend/app/tools_lib/*.json`（下表每个工具一个文件）
- Create: `backend/tests/test_tools_lib.py`

**Interfaces:**
- Consumes: `app.services.seed_service.seed_tools`
- Produces: `backend/app/tools_lib/` 下的 JSON 文件，每份含 `key`、`category`、`name`、`description`、`definition`、`checklist`

> 覆盖上位文档 §4.3 那张表的全部条目。`definition` 用统一的通用骨架（`slots` 列表 + `notes`），不为每套结构手写具体节拍 —— 节拍由作者或 AI 填充，模板只提供结构容器。

- [ ] **Step 1: 写失败测试 `backend/tests/test_tools_lib.py`**

```python
import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "app" / "tools_lib"

# 上位文档 §4.3 的完整清单
EXPECTED_KEYS = {
    "three_act", "four_act", "five_act", "hero_journey", "save_the_cat",
    "seven_point", "qi_cheng_zhuan_he", "jo_ha_kyu", "fichtean_curve",
    "golden_three_chapters", "volume_climax_layout", "hook_density", "chapter_payoff_beats",
    "character_arc", "want_vs_need", "trauma_backstory", "antagonist_mirror", "relationship_map",
    "tension_curve", "scene_sequel", "chapter_end_hooks",
    "theme_sentence", "motif", "symbol", "recurring_imagery",
}

VALID_CATEGORIES = {"通用结构", "长篇连载结构", "人物", "节奏", "主题"}


def _load_all():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TOOLS_DIR.glob("*.json"))]


def test_every_documented_tool_exists():
    assert {t["key"] for t in _load_all()} == EXPECTED_KEYS


def test_every_tool_has_required_fields():
    for tool in _load_all():
        assert tool["key"] and tool["name"] and tool["category"]
        assert tool["description"].strip()
        assert tool["category"] in VALID_CATEGORIES
        assert isinstance(tool["definition"], dict) and tool["definition"]
        assert isinstance(tool["checklist"], list) and tool["checklist"]


def test_every_tool_defines_slots():
    for tool in _load_all():
        slots = tool["definition"].get("slots")
        assert isinstance(slots, list) and slots, f"{tool['key']} 缺少 slots"
        for slot in slots:
            assert slot.get("key") and slot.get("label")


def test_all_categories_are_represented():
    assert {t["category"] for t in _load_all()} == VALID_CATEGORIES


def test_keys_are_unique():
    keys = [t["key"] for t in _load_all()]
    assert len(keys) == len(set(keys))
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_tools_lib.py -v
```

Expected: FAIL — 目录或文件不存在。

- [ ] **Step 3: 建目录与包标记**

```bash
mkdir -p "d:/Practical Project/AIProject/Experiment/StoryForge/backend/app/tools_lib"
touch "d:/Practical Project/AIProject/Experiment/StoryForge/backend/app/tools_lib/__init__.py"
```

- [ ] **Step 4: 写五个通用结构工具**

每个文件形如 `three_act.json`：

```json
{
  "key": "three_act",
  "category": "通用结构",
  "name": "三幕剧",
  "description": "最稳的长篇骨架：建置、对抗、解决。适合首次尝试长篇或需要强因果链的故事。",
  "definition": {
    "slots": [
      {"key": "act1", "label": "第一幕 · 建置", "hint": "主人公的日常与缺口；激励事件把它打碎", "word_ratio": 0.25},
      {"key": "act2", "label": "第二幕 · 对抗", "hint": "升级的阻碍；中点转折；跌入谷底", "word_ratio": 0.5},
      {"key": "act3", "label": "第三幕 · 解决", "hint": "主人公带着代价做出最终选择", "word_ratio": 0.25}
    ],
    "notes": "第二幕最易塌陷，务必安排中点转折与谷底。"
  },
  "checklist": [
    "激励事件是否在第一幕内发生，且由主人公的选择引向第二幕？",
    "第二幕中点是否发生了不可逆的身份或目标转折？",
    "第二幕结尾是否跌入谷底，且谷底由主人公自身的缺陷造成？",
    "第三幕的最终选择是否呼应了第一幕的缺口？"
  ]
}
```

按同一形状写齐这五个（`four_act`、`five_act`、`hero_journey`、`save_the_cat`），各自 slots 数按结构本身：

- `four_act.json`：启程 / 试炼 / 危机 / 解决，word_ratio 各 0.25。
- `five_act.json`：呈现 / 上升 / 高潮 / 下降 / 结局，ratio 0.2/0.3/0.2/0.2/0.1。
- `hero_journey.json`：12 个 stage 各一个 slot（平凡世界、冒险的召唤、拒绝召唤、遇见导师、跨越第一道门槛、试炼/盟友/敌人、接近最深的洞穴、磨难、奖赏、归途、复活、带着灵药回归），ratio 不细分（省略 `word_ratio`）。
- `save_the_cat.json`：15 个 beat 各一个 slot（开场画面、主题呈现、铺垫、催化剂、争执、第二幕转折、B 故事、游戏、中点、坏人逼近、一无所有、灵魂暗夜、第三幕转折、结局、终场画面）。

每个工具的 `checklist` 至少 3 条该结构特有的校验问题。

- [ ] **Step 5: 写其余工具**

同样的形状，按类别：

`seven_point.json`（通用结构）：钩子 / 第一情节点 / 第一夹点 / 中点 / 第二夹点 / 第二情节点 / 结局。
`qi_cheng_zhuan_he.json`（通用结构）：起 / 承 / 转 / 合，ratio 0.25 各。
`jo_ha_kyu.json`（通用结构）：序 / 破 / 急。
`fichtean_curve.json`（通用结构）：说明这是「无第二幕塌陷」的递升冲突曲线，slots 为「冲突序列 1–5」+「高潮」。

`golden_three_chapters.json`（长篇连载结构）：第一章 / 第二章 / 第三章，hint 分别写「立人设与钩子」「给第一个爽点或悬念回报」「建立长期追读动力」。
`volume_climax_layout.json`（长篇连载结构）：卷首铺垫 / 卷内升级 / 卷末高潮。
`hook_density.json`（长篇连载结构）：章首钩子 / 章中钩子 / 章末钩子，并按「每 1500–2000 字至少一个钩子」写 notes。
`chapter_payoff_beats.json`（长篇连载结构）：爽点前置 / 爽点兑现 / 小反转。

`character_arc.json`（人物）：起始状态 / 触发 / 挣扎 / 转变 / 终态，并让 `checklist` 覆盖正向、负向、扁平三种弧光。
`want_vs_need.json`（人物）：Want（表层目标）/ Need（真实需求）/ 冲突点。
`trauma_backstory.json`（人物）：创伤事件 / 当时的应对 / 遗留的信念 / 被触发的场景。
`antagonist_mirror.json`（人物）：对手欲望 / 对手与主角的镜像点 / 对手的正确之处。
`relationship_map.json`（人物）：关系对（双向），notes 说明一期用表格呈现。

`tension_curve.json`（节奏）：张力峰值点 / 谷底点 / 上升段 / 下降段。
`scene_sequel.json`（节奏）：Scene（目标-冲突-转折）/ Sequel（反应-困境-决定）。
`chapter_end_hooks.json`（节奏）：钩子类型库，slots 为「悬念钩」「情绪钩」「信息钩」「动作钩」四类，每类一条 checklist。

`theme_sentence.json`（主题）：主题句 / 反主题句 / 主题的呈现方式。
`motif.json`（主题）：母题 / 出现场景 / 变奏。
`symbol.json`（主题）：象征物 / 所指 / 首次出现 / 回收。
`recurring_imagery.json`（主题）：意象 / 节奏 / 与主题的关联。

- [ ] **Step 6: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_tools_lib.py tests/test_seed_service.py -v
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(tools): 创作工具库内置模板"
```

---

### Task 11: 后端 API 层

**Files:**
- Create: `backend/app/api/schemas.py`
- Create: `backend/app/api/projects.py`、`ideas.py`、`architecture.py`、`agents.py`、`providers.py`、`runs.py`、`tools.py`
- Create: `backend/app/services/project_service.py`、`idea_service.py`、`architecture_service.py`、`provider_service.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: 全部 services 与 runtime
- Produces: `/api` 下的 REST 接口（见下表）

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 健康检查（已有） |
| GET/POST | `/api/projects` | 列表 / 新建 |
| GET/PATCH/DELETE | `/api/projects/{id}` | 读取 / 更新 / 删除 |
| GET/POST | `/api/projects/{id}/ideas` | 列出 / 新建灵感（只写 `raw_text`） |
| POST | `/api/projects/{id}/ideas/{idea_id}/parse` | 跑灵感解析，写 `parsed_json` |
| GET | `/api/projects/{id}/architecture` | 读取当前架构与幕 |
| POST | `/api/projects/{id}/architecture/recommend` | 跑架构推荐，落 `generation_run` |
| PUT | `/api/projects/{id}/architecture` | 采纳：写入 architecture + acts |
| GET | `/api/agents` | 智能体列表（含当前版本） |
| GET | `/api/agents/{id}/versions` | 版本列表 |
| POST | `/api/agents/{id}/versions` | 新建版本 |
| POST | `/api/agents/{id}/rollback/{version_id}` | 回滚 |
| POST | `/api/runs` | 跑一次智能体（调试台用） |
| GET | `/api/runs` | 运行历史（可按 project/agent 过滤） |
| GET | `/api/runs/{id}` | 单次运行详情 |
| GET | `/api/tools` | 工具库列表 |
| GET/POST/PATCH/DELETE | `/api/providers` | 服务商 CRUD（永不返回密钥明文） |
| POST | `/api/providers/{id}/test` | 连通性测试 |
| GET/PUT | `/api/settings` | 全局设置 |

- [ ] **Step 1: 写失败测试 `backend/tests/test_api.py`**

```python
import httpx
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal, init_db
from app.main import app
from app.runtime.llm import HttpxChatClient
from app.services.seed_service import seed_agents, seed_tools


@pytest.fixture()
def client():
    init_db()
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_create_and_list_project(client):
    created = client.post("/api/projects", json={"name": "验尸官", "genre": "悬疑"}).json()
    assert created["name"] == "验尸官"
    listing = client.get("/api/projects").json()
    assert any(p["id"] == created["id"] for p in listing)


def test_idea_raw_text_is_preserved_on_parse(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    idea = client.post(
        f"/api/projects/{project['id']}/ideas", json={"raw_text": "能听见死者遗言的验尸官"}
    ).json()

    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')
    client.post(f"/api/projects/{project['id']}/ideas/{idea['id']}/parse")

    refreshed = client.get(f"/api/projects/{project['id']}/ideas").json()[0]
    assert refreshed["raw_text"] == "能听见死者遗言的验尸官"
    assert refreshed["parsed_json"]["genre"] == "悬疑"


def test_parse_returns_run_for_debug_console(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "灵感"})
    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')

    ideas = client.get(f"/api/projects/{project['id']}/ideas").json()
    resp = client.post(f"/api/projects/{project['id']}/ideas/{ideas[0]['id']}/parse")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run"]["rendered_prompt"]
    assert payload["run"]["raw_output"]


def test_agents_listed_with_current_version(client):
    agents = client.get("/api/agents").json()
    names = {a["name"] for a in agents}
    assert "架构师" in names
    assert "灵感解析师" in names
    architect = next(a for a in agents if a["name"] == "架构师")
    assert architect["current_version"]["system_prompt"]


def test_agent_version_creation_and_rollback(client):
    agents = client.get("/api/agents").json()
    agent = agents[0]
    v1 = agent["current_version"]["id"]

    created = client.post(
        f"/api/agents/{agent['id']}/versions",
        json={"system_prompt": "新提示词", "note": "试一版"},
    ).json()
    assert created["version_no"] == agent["current_version"]["version_no"] + 1

    client.post(f"/api/agents/{agent['id']}/rollback/{v1}")
    refreshed = next(a for a in client.get("/api/agents").json() if a["id"] == agent["id"])
    assert refreshed["current_version"]["id"] == v1


def test_provider_never_returns_plaintext_key(client):
    created = client.post(
        "/api/providers",
        json={"name": "测试", "kind": "custom", "base_url": "https://api.example.com/v1", "api_key": "sk-secret-123456"},
    ).json()
    assert "sk-secret-123456" not in str(created)
    assert created["api_key_masked"].startswith("sk-****")

    listing = client.get("/api/providers").json()
    assert "sk-secret-123456" not in str(listing)


def test_tools_listed(client):
    tools = client.get("/api/tools").json()
    assert any(t["key"] == "three_act" for t in tools)


def test_runs_history_is_filterable(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "灵感"})
    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')
    ideas = client.get(f"/api/projects/{project['id']}/ideas").json()
    client.post(f"/api/projects/{project['id']}/ideas/{ideas[0]['id']}/parse")

    runs = client.get("/api/runs", params={"project_id": project["id"]}).json()
    assert len(runs) == 1
    assert runs[0]["status"] == "ok"


def test_debug_run_endpoint_returns_full_trail(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "p"}).json()
    client.post(f"/api/projects/{project['id']}/ideas", json={"raw_text": "灵感"})
    _patch_client(monkeypatch, '{"genre": "悬疑", "premise": "x", "protagonist_desire": "y", "conflict_source": "z", "open_questions": []}')
    agents = client.get("/api/agents").json()
    parser = next(a for a in agents if a["name"] == "灵感解析师")

    resp = client.post("/api/runs", json={"project_id": project["id"], "agent_id": parser["id"]})
    body = resp.json()
    assert body["run"]["rendered_prompt"]
    assert body["run"]["raw_output"]
    assert "prompt_tokens" in body["run"]


def _patch_client(monkeypatch, content: str) -> None:
    """把运行时用的 HTTP 客户端换成固定响应的假实现。

    替换的是 RuntimeService._resolve_client 而不是 HttpxChatClient：
    后者在模块 import 时已被绑定，patch 模块属性不会影响已绑定的名字。
    """
    from app.services.runtime_service import RuntimeService

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 15},
            },
        )

    fake = HttpxChatClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self: fake)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_api.py -v
```

Expected: FAIL — 多数路由 404。

- [ ] **Step 3: 写 `backend/app/api/schemas.py`**

```python
"""接口出入参模型。api 层只做参数校验，业务在 services。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    genre: str | None = None
    sub_genre: str | None = None
    tone: str | None = None
    target_length: int | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    genre: str | None = None
    sub_genre: str | None = None
    tone: str | None = None
    target_length: int | None = None
    summary: str | None = None
    logic_check_level: str | None = None


class IdeaCreate(BaseModel):
    raw_text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class ActPayload(BaseModel):
    seq: int
    name: str
    purpose: str | None = None
    target_word_ratio: float | None = None
    summary: str | None = None


class ArchitectureAdopt(BaseModel):
    tool_ref: str | None = None
    logline: str | None = None
    theme: str | None = None
    premise: str | None = None
    ending_direction: str | None = None
    acts: list[ActPayload] = Field(default_factory=list)
    run_id: str | None = None


class VersionCreate(BaseModel):
    system_prompt: str | None = None
    model_binding_json: dict[str, Any] | None = None
    param_profile: str | None = None
    context_slots_json: list[str] | None = None
    output_schema_json: dict[str, Any] | None = None
    skills_json: list[str] | None = None
    trigger_mode: str | None = None
    note: str = ""


class RunRequest(BaseModel):
    project_id: str
    agent_id: str


class ProviderCreate(BaseModel):
    name: str
    kind: str = "custom"
    base_url: str = ""
    api_key: str | None = None
    enabled: bool = True
    priority: int = 0


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class SettingsUpdate(BaseModel):
    values: dict[str, Any]
```

- [ ] **Step 4: 写服务层**

`backend/app/services/project_service.py`：

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project


def list_projects(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc())))


def create_project(session: Session, **fields) -> Project:
    project = Project(**fields)
    session.add(project)
    session.commit()
    return project


def update_project(session: Session, project_id: str, **fields) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    for key, value in fields.items():
        if value is not None:
            setattr(project, key, value)
    session.commit()
    return project


def delete_project(session: Session, project_id: str) -> None:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    session.delete(project)
    session.commit()
```

`backend/app/services/idea_service.py`：

```python
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Idea


def list_ideas(session: Session, project_id: str) -> list[Idea]:
    return list(session.scalars(select(Idea).where(Idea.project_id == project_id).order_by(Idea.created_at)))


def create_idea(session: Session, project_id: str, raw_text: str, tags: list[str]) -> Idea:
    idea = Idea(project_id=project_id, raw_text=raw_text, tags_json=tags)
    session.add(idea)
    session.commit()
    return idea


def write_parsed(session: Session, idea_id: str, parsed: dict | None) -> Idea:
    """把解析结果写进 parsed_json。raw_text 永不触碰（D-04）。"""
    idea = session.get(Idea, idea_id)
    if idea is None:
        raise ValueError(f"灵感条目不存在：{idea_id}")
    if parsed is not None:
        idea.parsed_json = parsed
        idea.status = "parsed"
    else:
        idea.status = "parse_failed"
    session.commit()
    return idea


def parsed_as_text(session: Session, idea_id: str) -> str | None:
    idea = session.get(Idea, idea_id)
    if idea is None or not idea.parsed_json:
        return None
    return json.dumps(idea.parsed_json, ensure_ascii=False, indent=2)
```

`backend/app/services/architecture_service.py`：

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Act, Architecture


def get_architecture(session: Session, project_id: str) -> tuple[Architecture | None, list[Act]]:
    arch = session.scalars(
        select(Architecture).where(Architecture.project_id == project_id).order_by(Architecture.created_at)
    ).first()
    if arch is None:
        return None, []
    acts = list(session.scalars(select(Act).where(Act.architecture_id == arch.id).order_by(Act.seq)))
    return arch, acts


def adopt(session: Session, project_id: str, payload: dict) -> tuple[Architecture, list[Act]]:
    """作者确认故事圣经后写入项目结构。重复采纳则原地更新。"""
    arch, existing_acts = get_architecture(session, project_id)
    if arch is None:
        arch = Architecture(project_id=project_id)
        session.add(arch)
        session.flush()
    for key in ("tool_ref", "logline", "theme", "premise", "ending_direction"):
        if payload.get(key) is not None:
            setattr(arch, key, payload[key])
    for act in existing_acts:
        session.delete(act)
    session.flush()

    acts: list[Act] = []
    for item in payload.get("acts", []):
        act = Act(
            architecture_id=arch.id,
            seq=item["seq"],
            name=item["name"],
            purpose=item.get("purpose"),
            target_word_ratio=item.get("target_word_ratio"),
            summary=item.get("summary"),
        )
        session.add(act)
        acts.append(act)
    session.commit()
    return arch, acts
```

`backend/app/services/provider_service.py`：

```python
"""服务商管理。密钥只经 DPAPI 存取，接口只回显屏蔽态（D-01）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import dpapi
from app.db.models import GenerationRun, Provider
from app.runtime.llm import ChatConfig, HttpxChatClient


def list_providers(session: Session) -> list[Provider]:
    return list(session.scalars(select(Provider).order_by(Provider.priority)))


def _key_ref(provider_id: str) -> str:
    return f"provider:{provider_id}"


def create_provider(session: Session, *, api_key: str | None, **fields) -> Provider:
    provider = Provider(**fields)
    session.add(provider)
    session.commit()
    if api_key:
        provider.api_key_ref = _key_ref(provider.id)
        dpapi.set_secret(provider.api_key_ref, api_key)
        session.commit()
    return provider


def update_provider(session: Session, provider_id: str, *, api_key: str | None, **fields) -> Provider:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise ValueError(f"服务商不存在：{provider_id}")
    for key, value in fields.items():
        if value is not None:
            setattr(provider, key, value)
    if api_key:
        provider.api_key_ref = _key_ref(provider.id)
        dpapi.set_secret(provider.api_key_ref, api_key)
    session.commit()
    return provider


def delete_provider(session: Session, provider_id: str) -> None:
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise ValueError(f"服务商不存在：{provider_id}")
    if provider.api_key_ref:
        dpapi.delete_secret(provider.api_key_ref)
    session.delete(provider)
    session.commit()


def masked_key(provider: Provider) -> str:
    if not provider.api_key_ref:
        return ""
    return dpapi.mask(dpapi.get_secret(provider.api_key_ref) or "")


def test_connection(session: Session, provider_id: str) -> dict:
    """一键连通性测试。失败给出可读原因，不抛异常给界面。"""
    provider = session.get(Provider, provider_id)
    if provider is None:
        return {"ok": False, "message": f"服务商不存在：{provider_id}"}
    if not provider.base_url:
        return {"ok": False, "message": "尚未填写接口地址"}

    api_key = dpapi.get_secret(provider.api_key_ref) if provider.api_key_ref else ""
    client = HttpxChatClient()
    config = ChatConfig(base_url=provider.base_url, api_key=api_key or "", model="")
    try:
        _sync_probe(client, config)
    except Exception as exc:  # noqa: BLE001 — 界面要看到原因而不是堆栈
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": "连接正常"}


def _sync_probe(client: HttpxChatClient, config: ChatConfig) -> None:
    import asyncio

    async def probe() -> None:
        # 用一个必然失败的极短请求探测连通性；401/404 说明地址可达，
        # 网络类错误才是真的连不上。
        from app.runtime.llm import ChatFailure

        try:
            await client.complete(config, [{"role": "user", "content": "ping"}], {"max_tokens": 1})
        except ChatFailure as exc:
            if exc.error.kind == "network" or exc.error.kind == "timeout":
                raise

    asyncio.run(probe())


def project_cost_summary(session: Session, project_id: str) -> dict:
    runs = session.scalars(
        select(GenerationRun).where(GenerationRun.project_id == project_id)
    ).all()
    return {
        "runs": len(runs),
        "prompt_tokens": sum(r.prompt_tokens for r in runs),
        "completion_tokens": sum(r.completion_tokens for r in runs),
        "cost_estimate": round(sum(r.cost_estimate for r in runs), 6),
    }
```

- [ ] **Step 5: 写路由文件**

`backend/app/api/projects.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import IdeaCreate, ProjectCreate, ProjectUpdate
from app.db.session import get_session
from app.services import idea_service, project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _idea_out(idea) -> dict:
    return {
        "id": idea.id,
        "project_id": idea.project_id,
        "raw_text": idea.raw_text,
        "tags": idea.tags_json,
        "parsed_json": idea.parsed_json,
        "status": idea.status,
    }


def _project_out(project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "genre": project.genre,
        "sub_genre": project.sub_genre,
        "tone": project.tone,
        "target_length": project.target_length,
        "summary": project.summary,
        "writing_lang": project.writing_lang,
        "logic_check_level": project.logic_check_level,
        "created_at": project.created_at.isoformat(),
    }


@router.get("")
def list_projects(session: Session = Depends(get_session)) -> list[dict]:
    return [_project_out(p) for p in project_service.list_projects(session)]


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> dict:
    return _project_out(project_service.create_project(session, **payload.model_dump()))


@router.get("/{project_id}")
def get_project(project_id: str, session: Session = Depends(get_session)) -> dict:
    project = project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _project_out(project)


@router.patch("/{project_id}")
def update_project(
    project_id: str, payload: ProjectUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        project = project_service.update_project(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_session)) -> None:
    try:
        project_service.delete_project(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/ideas")
def list_ideas(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_idea_out(i) for i in idea_service.list_ideas(session, project_id)]


@router.post("/{project_id}/ideas", status_code=201)
def create_idea(project_id: str, payload: IdeaCreate, session: Session = Depends(get_session)) -> dict:
    return _idea_out(idea_service.create_idea(session, project_id, payload.raw_text, payload.tags))
```

在 `backend/app/services/project_service.py` 里补一个 `get_project`：

```python
def get_project(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)
```

`backend/app/api/ideas.py`（灵感解析）：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import idea_service, project_service
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/projects", tags=["ideas"])


def _idea_out(idea) -> dict:
    return {
        "id": idea.id,
        "project_id": idea.project_id,
        "raw_text": idea.raw_text,
        "tags": idea.tags_json,
        "parsed_json": idea.parsed_json,
        "status": idea.status,
    }


def _run_out(run) -> dict:
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "agent_version_id": run.agent_version_id,
        "model": run.model,
        "rendered_prompt": run.rendered_prompt,
        "raw_output": run.raw_output,
        "parsed_json": run.parsed_json,
        "structured": run.structured,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "cost_estimate": run.cost_estimate,
        "duration_ms": run.duration_ms,
        "status": run.status,
        "error": run.error_json,
        "trimmed": run.trimmed_json,
    }


@router.post("/{project_id}/ideas/{idea_id}/parse")
def parse_idea(project_id: str, idea_id: str, session: Session = Depends(get_session)) -> dict:
    """跑灵感解析并写回 parsed_json。返回 run 供调试台展示完整链路。"""
    parsed_text = idea_service.parsed_as_text(session, idea_id)
    if parsed_text is None:
        idea = idea_service.get_idea(session, idea_id)
        if idea is None:
            raise HTTPException(status_code=404, detail="灵感条目不存在")
        if not idea.raw_text.strip():
            raise HTTPException(status_code=400, detail="灵感原话为空，无法解析")

    parser = _find_agent_by_task(session, "idea_parse")
    if parser is None:
        raise HTTPException(status_code=500, detail="找不到灵感解析智能体，请重新预置阵容")

    service = RuntimeService(session)
    try:
        run, result = service.execute(project_id, parser.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    idea_service.write_parsed(session, idea_id, result.parsed if result.structured else None)
    return {
        "run": _run_out(run),
        "structured": result.structured,
        "parse_error": result.parse_error,
        "idea": _idea_out(idea_service.get_idea(session, idea_id)),
    }


def _find_agent_by_task(session: Session, task_type: str):
    from sqlalchemy import select

    from app.db.models import Agent

    return session.scalars(
        select(Agent).where(Agent.task_type == task_type, Agent.enabled.is_(True))
    ).first()
```

在 `backend/app/services/idea_service.py` 补：

```python
def get_idea(session: Session, idea_id: str) -> Idea | None:
    return session.get(Idea, idea_id)
```

`backend/app/api/architecture.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ArchitectureAdopt
from app.db.models import Agent
from app.db.session import get_session
from app.services import architecture_service
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/projects", tags=["architecture"])


@router.get("/{project_id}/architecture")
def get_architecture(project_id: str, session: Session = Depends(get_session)) -> dict:
    arch, acts = architecture_service.get_architecture(session, project_id)
    return {
        "architecture": _arch_out(arch),
        "acts": [_act_out(a) for a in acts],
    }


@router.post("/{project_id}/architecture/recommend")
def recommend(project_id: str, session: Session = Depends(get_session)) -> dict:
    architect = session.scalars(
        select(Agent).where(Agent.task_type == "architecture", Agent.enabled.is_(True))
    ).first()
    if architect is None:
        raise HTTPException(status_code=500, detail="找不到架构师智能体，请重新预置阵容")

    service = RuntimeService(session)
    try:
        run, result = service.execute(project_id, architect.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "run": {
            "id": run.id,
            "rendered_prompt": run.rendered_prompt,
            "raw_output": run.raw_output,
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "cost_estimate": run.cost_estimate,
            "duration_ms": run.duration_ms,
            "status": run.status,
            "error": run.error_json,
            "trimmed": run.trimmed_json,
        },
        "options": (result.parsed or {}).get("options", []) if result.structured else [],
        "story_bible_v0": (result.parsed or {}).get("story_bible_v0", {}) if result.structured else {},
        "structured": result.structured,
        "parse_error": result.parse_error,
        "raw_text": result.raw_output,
    }


@router.put("/{project_id}/architecture")
def adopt(project_id: str, payload: ArchitectureAdopt, session: Session = Depends(get_session)) -> dict:
    """作者确认后写入项目结构。这是「AI 出候选、作者拍板」的落点。"""
    arch, acts = architecture_service.adopt(session, project_id, payload.model_dump())
    return {"architecture": _arch_out(arch), "acts": [_act_out(a) for a in acts]}


def _arch_out(arch) -> dict | None:
    if arch is None:
        return None
    return {
        "id": arch.id,
        "tool_ref": arch.tool_ref,
        "logline": arch.logline,
        "theme": arch.theme,
        "premise": arch.premise,
        "ending_direction": arch.ending_direction,
        "locked": arch.locked,
    }


def _act_out(act) -> dict:
    return {
        "id": act.id,
        "seq": act.seq,
        "name": act.name,
        "purpose": act.purpose,
        "target_word_ratio": act.target_word_ratio,
        "summary": act.summary,
    }
```

`backend/app/api/agents.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import VersionCreate
from app.db.session import get_session
from app.services import agent_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _version_out(version) -> dict | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "version_no": version.version_no,
        "system_prompt": version.system_prompt,
        "model_binding_json": version.model_binding_json,
        "param_profile": version.param_profile,
        "context_slots_json": version.context_slots_json,
        "output_schema_json": version.output_schema_json,
        "skills_json": version.skills_json,
        "trigger_mode": version.trigger_mode,
        "note": version.note,
        "created_at": version.created_at.isoformat(),
    }


def _agent_out(agent, version) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "role_label": agent.role_label,
        "color": agent.color,
        "task_type": agent.task_type,
        "enabled": agent.enabled,
        "builtin": agent.builtin,
        "current_version": _version_out(version),
    }


@router.get("")
def list_agents(session: Session = Depends(get_session)) -> list[dict]:
    out = []
    for agent in agent_service.list_agents(session):
        version = agent_service.get_version(session, agent.current_version_id) if agent.current_version_id else None
        out.append(_agent_out(agent, version))
    return out


@router.get("/{agent_id}/versions")
def list_versions(agent_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_version_out(v) for v in agent_service.list_versions(session, agent_id)]


@router.post("/{agent_id}/versions", status_code=201)
def create_version(agent_id: str, payload: VersionCreate, session: Session = Depends(get_session)) -> dict:
    try:
        version = agent_service.create_version(
            session, agent_id, **payload.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _version_out(version)


@router.post("/{agent_id}/rollback/{version_id}")
def rollback(agent_id: str, version_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        agent = agent_service.rollback_to(session, agent_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    version = agent_service.get_version(session, agent.current_version_id)
    return _agent_out(agent, version)
```

`backend/app/api/runs.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import RunRequest
from app.db.models import GenerationRun
from app.db.session import get_session
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_out(run: GenerationRun) -> dict:
    return {
        "id": run.id,
        "project_id": run.project_id,
        "agent_id": run.agent_id,
        "agent_version_id": run.agent_version_id,
        "provider_id": run.provider_id,
        "model": run.model,
        "params": run.params_json,
        "rendered_prompt": run.rendered_prompt,
        "raw_output": run.raw_output,
        "parsed_json": run.parsed_json,
        "structured": run.structured,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "cost_estimate": run.cost_estimate,
        "duration_ms": run.duration_ms,
        "status": run.status,
        "error": run.error_json,
        "trimmed": run.trimmed_json,
        "created_at": run.created_at.isoformat(),
    }


@router.get("")
def list_runs(
    project_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
) -> list[dict]:
    stmt = select(GenerationRun).order_by(GenerationRun.created_at.desc()).limit(limit)
    if project_id:
        stmt = stmt.where(GenerationRun.project_id == project_id)
    if agent_id:
        stmt = stmt.where(GenerationRun.agent_id == agent_id)
    return [_run_out(r) for r in session.scalars(stmt)]


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return _run_out(run)


@router.post("", status_code=201)
def run_agent(payload: RunRequest, session: Session = Depends(get_session)) -> dict:
    """调试台入口：跑一次智能体，返回完整链路。"""
    service = RuntimeService(session)
    try:
        run, result = service.execute(payload.project_id, payload.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": _run_out(run), "parse_error": result.parse_error, "trimmed": result.trimmed}
```

`backend/app/api/tools.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ToolTemplate
from app.db.session import get_session

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools(
    category: str | None = None, session: Session = Depends(get_session)
) -> list[dict]:
    stmt = select(ToolTemplate).order_by(ToolTemplate.category, ToolTemplate.key)
    if category:
        stmt = stmt.where(ToolTemplate.category == category)
    return [
        {
            "id": t.id,
            "key": t.key,
            "category": t.category,
            "name": t.name,
            "description": t.description,
            "definition": t.definition_json,
            "checklist": t.checklist_json,
            "builtin": t.builtin,
        }
        for t in session.scalars(stmt)
    ]
```

`backend/app/api/providers.py`：

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import config
from app.api.schemas import ProviderCreate, ProviderUpdate, SettingsUpdate
from app.db.session import get_session
from app.services import provider_service

router = APIRouter(prefix="/api", tags=["providers"])


def _provider_out(session: Session, provider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "kind": provider.kind,
        "base_url": provider.base_url,
        # 只回显屏蔽态，永不返回明文（D-01）
        "api_key_masked": provider_service.masked_key(provider),
        "enabled": provider.enabled,
        "priority": provider.priority,
    }


@router.get("/providers")
def list_providers(session: Session = Depends(get_session)) -> list[dict]:
    return [_provider_out(session, p) for p in provider_service.list_providers(session)]


@router.post("/providers", status_code=201)
def create_provider(payload: ProviderCreate, session: Session = Depends(get_session)) -> dict:
    fields = payload.model_dump(exclude={"api_key"})
    provider = provider_service.create_provider(session, api_key=payload.api_key, **fields)
    return _provider_out(session, provider)


@router.patch("/providers/{provider_id}")
def update_provider(
    provider_id: str, payload: ProviderUpdate, session: Session = Depends(get_session)
) -> dict:
    fields = payload.model_dump(exclude={"api_key"}, exclude_none=True)
    try:
        provider = provider_service.update_provider(
            session, provider_id, api_key=payload.api_key, **fields
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _provider_out(session, provider)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, session: Session = Depends(get_session)) -> None:
    try:
        provider_service.delete_provider(session, provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/test")
def test_provider(provider_id: str, session: Session = Depends(get_session)) -> dict:
    return provider_service.test_connection(session, provider_id)


@router.get("/settings")
def get_settings() -> dict:
    return config.load_settings()


@router.put("/settings")
def update_settings(payload: SettingsUpdate) -> dict:
    config.save_settings(payload.values)
    return config.load_settings()


@router.get("/projects/{project_id}/cost")
def project_cost(project_id: str, session: Session = Depends(get_session)) -> dict:
    return provider_service.project_cost_summary(session, project_id)
```

- [ ] **Step 6: 改 `backend/app/main.py` 挂载全部路由并预置数据**

```python
from __future__ import annotations

from fastapi import FastAPI

from app import config
from app.api import agents, architecture, ideas, projects, providers, runs, tools
from app.db.session import SessionLocal, init_db
from app.services.seed_service import seed_agents, seed_tools

app = FastAPI(title="StoryForge", version="0.1.0")


@app.on_event("startup")
def _bootstrap() -> None:
    init_db()
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_dir": str(config.data_dir())}


for module in (projects, ideas, architecture, agents, runs, tools, providers):
    app.include_router(module.router)
```

> 同源托管前端构建产物的 StaticFiles 挂载留到 P1c 加 pywebview 外壳时再写，P1a 开发期走 Vite 代理，现在挂了反而会遮住 5173 的调试。

- [ ] **Step 7: 运行测试，确认通过**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest tests/test_api.py -v
```

Expected: 10 passed。

> 实现提醒：`backend/app/api/projects.py` 里的 `create_idea` 与 `list_ideas` 需要 `from app.api.schemas import IdeaCreate, ProjectCreate, ProjectUpdate` 一行 import；`_idea_out` 定义在同文件内（与 `ideas.py` 各自持有一份，因为两处返回结构略有不同，不共用）。

- [ ] **Step 8: 全量测试**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest -v
```

Expected: 全部通过。

- [ ] **Step 9: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add backend/
git commit -m "feat(api): 项目/灵感/架构/智能体/运行/工具/服务商接口"
```

---

### Task 12: 前端骨架与五页

**Files:**
- Create: `frontend/`（Vite 脚手架）
- Create: `frontend/vite.config.ts`、`tailwind.config.js`、`postcss.config.js`
- Create: `frontend/src/lib/format.ts` + `frontend/src/lib/format.test.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/`
- Create: `frontend/src/pages/Dashboard.tsx`、`Idea.tsx`、`Architecture.tsx`、`Studio.tsx`、`Models.tsx`
- Create: `frontend/src/App.tsx`、`main.tsx`、`index.css`
- Create: `scripts/dev.ps1`

**Interfaces:**
- Consumes: Task 11 的 REST 接口
- Produces: 可运行的开发前端

- [ ] **Step 1: 脚手架**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
pnpm create vite frontend --template react-ts
cd frontend
pnpm install
pnpm add -D tailwindcss@^3 postcss autoprefixer vitest @testing-library/react jsdom
pnpm add react-router-dom
pnpm add @tiptap/react @tiptap/starter-kit @tiptap/pm
pnpm add -D @types/node
pnpm exec tailwindcss init -p
```

- [ ] **Step 2: 写 `frontend/vite.config.ts`**

```ts
/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8756', changeOrigin: true } },
  },
  test: { environment: 'jsdom', globals: true },
})
```

- [ ] **Step 3: 写 `frontend/tailwind.config.js` 与 `frontend/src/index.css`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
```

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-slate-950 text-slate-100 antialiased;
}
```

- [ ] **Step 4: 写失败测试 `frontend/src/lib/format.test.ts`**

```ts
import { describe, expect, it } from 'vitest'
import { costLabel, durationLabel, maskPreview, tokensLabel } from './format'

describe('costLabel', () => {
  it('显示至多四位小数的美元金额', () => {
    expect(costLabel(0.00024)).toBe('$0.0002')
  })
  it('零金额显示为 $0', () => {
    expect(costLabel(0)).toBe('$0')
  })
  it('较大金额保留两位小数', () => {
    expect(costLabel(1.23456)).toBe('$1.23')
  })
})

describe('durationLabel', () => {
  it('毫秒以下按毫秒显示', () => {
    expect(durationLabel(840)).toBe('840 ms')
  })
  it('秒级按秒显示', () => {
    expect(durationLabel(2400)).toBe('2.4 s')
  })
})

describe('tokensLabel', () => {
  it('合并输入输出 token', () => {
    expect(tokensLabel(120, 340)).toBe('120 + 340 tokens')
  })
})

describe('maskPreview', () => {
  it('长文本截断并加省略号', () => {
    expect(maskPreview('一二三四五六七八九十', 4)).toBe('一二三四…')
  })
  it('短文本原样返回', () => {
    expect(maskPreview('短', 4)).toBe('短')
  })
})
```

- [ ] **Step 5: 运行测试，确认失败**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/frontend"
pnpm vitest run src/lib/format.test.ts
```

Expected: FAIL — `Failed to resolve import './format'`。

- [ ] **Step 6: 写 `frontend/src/lib/format.ts`**

```ts
export function costLabel(cost: number): string {
  if (!cost) return '$0'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

export function durationLabel(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function tokensLabel(prompt: number, completion: number): string {
  return `${prompt} + ${completion} tokens`
}

export function maskPreview(text: string | null | undefined, limit = 4): string {
  if (!text) return ''
  return text.length <= limit ? text : `${text.slice(0, limit)}…`
}
```

- [ ] **Step 7: 写 `frontend/src/api/client.ts`**

```ts
const JSON_HEADERS = { 'content-type': 'application/json' }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(detail.detail ?? `请求失败：${response.status}`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  health: () => request<{ status: string; data_dir: string }>('/api/health'),

  listProjects: () => request<Project[]>('/api/projects'),
  createProject: (body: { name: string; genre?: string; tone?: string }) =>
    request<Project>('/api/projects', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }),

  listIdeas: (projectId: string) => request<Idea[]>(`/api/projects/${projectId}/ideas`),
  createIdea: (projectId: string, rawText: string) =>
    request<Idea>(`/api/projects/${projectId}/ideas`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ raw_text: rawText }),
    }),
  parseIdea: (projectId: string, ideaId: string) =>
    request<{ run: RunView; structured: boolean; parse_error: string | null; idea: Idea }>(
      `/api/projects/${projectId}/ideas/${ideaId}/parse`,
      { method: 'POST' },
    ),

  getArchitecture: (projectId: string) =>
    request<{ architecture: Architecture | null; acts: Act[] }>(`/api/projects/${projectId}/architecture`),
  recommendArchitecture: (projectId: string) =>
    request<RecommendResponse>(`/api/projects/${projectId}/architecture/recommend`, { method: 'POST' }),
  adoptArchitecture: (projectId: string, body: AdoptPayload) =>
    request<{ architecture: Architecture; acts: Act[] }>(`/api/projects/${projectId}/architecture`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),

  listAgents: () => request<Agent[]>('/api/agents'),
  listVersions: (agentId: string) => request<AgentVersion[]>(`/api/agents/${agentId}/versions`),
  createVersion: (agentId: string, body: Record<string, unknown>) =>
    request<AgentVersion>(`/api/agents/${agentId}/versions`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  rollback: (agentId: string, versionId: string) =>
    request<Agent>(`/api/agents/${agentId}/rollback/${versionId}`, { method: 'POST' }),

  listRuns: (projectId?: string) =>
    request<RunView[]>(`/api/runs${projectId ? `?project_id=${projectId}` : ''}`),
  runAgent: (projectId: string, agentId: string) =>
    request<{ run: RunView; parse_error: string | null; trimmed: Record<string, string> }>('/api/runs', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ project_id: projectId, agent_id: agentId }),
    }),

  listTools: () => request<Tool[]>('/api/tools'),

  listProviders: () => request<ProviderView[]>('/api/providers'),
  createProvider: (body: Record<string, unknown>) =>
    request<ProviderView>('/api/providers', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  testProvider: (id: string) =>
    request<{ ok: boolean; message: string }>(`/api/providers/${id}/test`, { method: 'POST' }),

  getSettings: () => request<Settings>('/api/settings'),
  updateSettings: (values: Record<string, unknown>) =>
    request<Settings>('/api/settings', {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ values }),
    }),
  projectCost: (projectId: string) => request<CostSummary>(`/api/projects/${projectId}/cost`),
}

export interface Project {
  id: string
  name: string
  genre: string | null
  tone: string | null
  target_length: number | null
  logic_check_level: string
}

export interface Idea {
  id: string
  project_id: string
  raw_text: string
  tags: string[]
  parsed_json: Record<string, unknown> | null
  status: string
}

export interface RunView {
  id: string
  agent_id: string
  model: string
  rendered_prompt: string
  raw_output: string
  parsed_json: Record<string, unknown> | null
  structured: boolean
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
  duration_ms: number
  status: string
  error: { kind: string; message: string } | null
  trimmed: Record<string, string>
}

export interface ArchitectureOption {
  tool: string
  reason: string
  fit_score: number
  risks: string[]
  length_plan?: string
  rhythm_shape?: string
}

export interface StoryBibleV0 {
  logline?: string
  theme?: string
  premise?: string
  acts?: { name: string; purpose?: string; target_word_ratio?: number }[]
  main_characters?: { name: string; role?: string; desire?: string }[]
  ending_direction?: string
}

export interface RecommendResponse {
  run: RunView
  options: ArchitectureOption[]
  story_bible_v0: StoryBibleV0
  structured: boolean
  parse_error: string | null
  raw_text: string
}

export interface Architecture {
  id: string
  tool_ref: string | null
  logline: string | null
  theme: string | null
  premise: string | null
  ending_direction: string | null
  locked: boolean
}

export interface Act {
  id: string
  seq: number
  name: string
  purpose: string | null
  target_word_ratio: number | null
  summary: string | null
}

export interface AdoptPayload {
  tool_ref?: string
  logline?: string
  theme?: string
  premise?: string
  ending_direction?: string
  acts: { seq: number; name: string; purpose?: string; target_word_ratio?: number }[]
}

export interface AgentVersion {
  id: string
  version_no: number
  system_prompt: string
  model_binding_json: Record<string, unknown>
  param_profile: string
  context_slots_json: string[]
  output_schema_json: Record<string, unknown> | null
  skills_json: string[]
  trigger_mode: string
  note: string
}

export interface Agent {
  id: string
  name: string
  role_label: string
  color: string
  task_type: string
  enabled: boolean
  builtin: boolean
  current_version: AgentVersion | null
}

export interface Tool {
  id: string
  key: string
  category: string
  name: string
  description: string
  definition: { slots?: { key: string; label: string; hint?: string }[] }
  checklist: string[]
}

export interface ProviderView {
  id: string
  name: string
  kind: string
  base_url: string
  api_key_masked: string
  enabled: boolean
  priority: number
}

export interface Settings {
  context_token_budget: number
  default_params: { temperature: number; max_tokens: number }
  model_routing: Record<string, string>
  budget_alert: number | null
}

export interface CostSummary {
  runs: number
  prompt_tokens: number
  completion_tokens: number
  cost_estimate: number
}
```

- [ ] **Step 8: 写 `frontend/src/App.tsx` 与路由**

```tsx
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Architecture from './pages/Architecture'
import Dashboard from './pages/Dashboard'
import Idea from './pages/Idea'
import Models from './pages/Models'
import Studio from './pages/Studio'

const NAV = [
  { to: '/dashboard', label: '故事仪表盘' },
  { to: '/idea', label: '灵感与解析' },
  { to: '/architecture', label: '架构推荐' },
  { to: '/studio', label: '智能体工作室' },
  { to: '/models', label: '模型与费用' },
]

export default function App() {
  return (
    <div className="flex h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-800 p-4">
        <h1 className="mb-6 text-lg font-semibold tracking-wide">StoryForge</h1>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-900'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/idea" element={<Idea />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/models" element={<Models />} />
        </Routes>
      </main>
    </div>
  )
}
```

`frontend/src/main.tsx`：

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 9: 写 `frontend/src/components/RunTrace.tsx`（调试台复用的运行详情面板）**

```tsx
import { costLabel, durationLabel, tokensLabel } from '../lib/format'
import type { RunView } from '../api/client'

export default function RunTrace({ run }: { run: RunView }) {
  return (
    <div className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-400">
        <span>模型：{run.model || '未指定'}</span>
        <span>{tokensLabel(run.prompt_tokens, run.completion_tokens)}</span>
        <span>{costLabel(run.cost_estimate)}</span>
        <span>{durationLabel(run.duration_ms)}</span>
        <span>状态：{run.status}</span>
      </div>

      {Object.keys(run.trimmed ?? {}).length > 0 && (
        <div className="rounded bg-amber-950/40 p-2 text-amber-300">
          这次砍掉了：
          {Object.entries(run.trimmed).map(([slot, action]) => (
            <span key={slot} className="ml-2">
              {slot}（{action}）
            </span>
          ))}
        </div>
      )}

      {run.error && (
        <div className="rounded bg-red-950/40 p-2 text-red-300">
          {run.error.kind}：{run.error.message}
        </div>
      )}

      <details open>
        <summary className="cursor-pointer text-slate-300">渲染后的完整提示词</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">{run.rendered_prompt}</pre>
      </details>

      <details>
        <summary className="cursor-pointer text-slate-300">原始返回</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">{run.raw_output}</pre>
      </details>

      <details>
        <summary className="cursor-pointer text-slate-300">解析结果</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">
          {run.structured ? JSON.stringify(run.parsed_json, null, 2) : '未结构化'}
        </pre>
      </details>
    </div>
  )
}
```

- [ ] **Step 10: 写 `frontend/src/pages/Dashboard.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, type CostSummary, type Project } from '../api/client'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<Project | null>(null)
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [name, setName] = useState('')

  useEffect(() => {
    api.listProjects().then(setProjects)
  }, [])

  useEffect(() => {
    if (selected) api.projectCost(selected.id).then(setCost)
  }, [selected])

  async function create() {
    if (!name.trim()) return
    const project = await api.createProject({ name: name.trim() })
    setProjects((prev) => [project, ...prev])
    setSelected(project)
    setName('')
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">故事仪表盘</h2>

      <div className="flex gap-2">
        <input
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="新项目名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={create}>
          新建项目
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <section className="col-span-2 space-y-2">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelected(p)}
              className={`block w-full rounded border px-4 py-3 text-left ${
                selected?.id === p.id ? 'border-indigo-500 bg-slate-900' : 'border-slate-800'
              }`}
            >
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-slate-500">
                {p.genre ?? '未定题材'} · {p.tone ?? '未定调性'}
              </div>
            </button>
          ))}
          {projects.length === 0 && <p className="text-sm text-slate-500">还没有项目，先建一个。</p>}
        </section>

        <section className="rounded border border-slate-800 p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">体检单</h3>
          {selected ? (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">字数</dt>
                <dd>0</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">结构完整度</dt>
                <dd>待 P1c</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">未处理告警</dt>
                <dd>待 P2</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">累计调用</dt>
                <dd>{cost?.runs ?? 0} 次</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">累计费用</dt>
                <dd>${(cost?.cost_estimate ?? 0).toFixed(4)}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">选一个项目看体检单。</p>
          )}
        </section>
      </div>
    </div>
  )
}
```

- [ ] **Step 11: 写 `frontend/src/pages/Idea.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, type Idea as IdeaRow, type Project, type RunView } from '../api/client'
import RunTrace from '../components/RunTrace'

const FIELD_LABELS: Record<string, string> = {
  genre: '题材',
  sub_genre: '子类型',
  premise: '一句话前提',
  protagonist_desire: '主角欲望',
  conflict_source: '核心冲突源',
  emotional_core: '情感内核',
  tone: '调性',
  length_expectation: '篇幅预期',
  comparable_works: '可能参考坐标',
}

export default function Idea() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [ideas, setIdeas] = useState<IdeaRow[]>([])
  const [draft, setDraft] = useState('')
  const [run, setRun] = useState<RunView | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (projectId) api.listIdeas(projectId).then(setIdeas)
  }, [projectId])

  const current = ideas[ideas.length - 1]

  async function addIdea() {
    if (!draft.trim() || !projectId) return
    const idea = await api.createIdea(projectId, draft.trim())
    setIdeas((prev) => [...prev, idea])
    setDraft('')
  }

  async function parse() {
    if (!current || !projectId) return
    setBusy(true)
    try {
      const response = await api.parseIdea(projectId, current.id)
      setRun(response.run)
      setParseError(response.parse_error)
      setIdeas((prev) => prev.map((i) => (i.id === response.idea.id ? response.idea : i)))
    } catch (error) {
      setParseError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">灵感与解析</h2>

      <select
        className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        value={projectId}
        onChange={(e) => setProjectId(e.target.value)}
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>

      <section className="space-y-2">
        <div className="text-xs text-amber-400">这段文字 AI 不会改，解析结果只会另起一份。</div>
        <textarea
          className="h-28 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
          placeholder="丢一段话、几个标签、一句「我想写个什么」"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex gap-2">
          <button className="rounded border border-slate-700 px-4 py-2 text-sm" onClick={addIdea}>
            存为灵感
          </button>
          <button
            className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
            onClick={parse}
            disabled={busy || !current}
          >
            {busy ? '解析中…' : '解析'}
          </button>
        </div>
      </section>

      {current && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <div className="mb-2 text-xs text-slate-500">作者原话（不会被覆盖）</div>
          <p className="whitespace-pre-wrap text-slate-200">{current.raw_text}</p>
        </section>
      )}

      {parseError && (
        <div className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">
          未结构化：{parseError}
        </div>
      )}

      {current?.parsed_json && (
        <section className="space-y-3 rounded border border-slate-800 p-4">
          <h3 className="text-sm font-medium text-slate-300">解析卡（可逐项编辑）</h3>
          {Object.entries(FIELD_LABELS).map(([key, label]) => (
            <div key={key}>
              <div className="text-xs text-slate-500">{label}</div>
              <div className="text-slate-200">
                {Array.isArray(current.parsed_json![key])
                  ? (current.parsed_json![key] as string[]).join('、')
                  : String(current.parsed_json![key] ?? '—')}
              </div>
            </div>
          ))}
          {Array.isArray(current.parsed_json.open_questions) &&
            (current.parsed_json.open_questions as string[]).length > 0 && (
              <div className="rounded bg-slate-900 p-3">
                <div className="mb-1 text-xs text-slate-500">它没把握的问题，等你补</div>
                <ul className="list-disc space-y-1 pl-5">
                  {(current.parsed_json.open_questions as string[]).map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            )}
        </section>
      )}

      {run && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">这次运行</h3>
          <RunTrace run={run} />
        </section>
      )}
    </div>
  )
}
```

- [ ] **Step 12: 写 `frontend/src/pages/Architecture.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, type Act, type ArchitectureOption, type Project, type RecommendResponse } from '../api/client'
import RunTrace from '../components/RunTrace'

export default function Architecture() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [recommendation, setRecommendation] = useState<RecommendResponse | null>(null)
  const [chosen, setChosen] = useState<ArchitectureOption | null>(null)
  const [acts, setActs] = useState<Act[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    api.getArchitecture(projectId).then((data) => setActs(data.acts))
  }, [projectId])

  async function recommend() {
    setBusy(true)
    setMessage('')
    try {
      setRecommendation(await api.recommendArchitecture(projectId))
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function adopt() {
    if (!recommendation || !chosen) return
    const bible = recommendation.story_bible_v0
    const actPayload =
      acts.length > 0
        ? acts.map((a) => ({
            seq: a.seq,
            name: a.name,
            purpose: a.purpose ?? undefined,
            target_word_ratio: a.target_word_ratio ?? undefined,
          }))
        : (bible.acts ?? []).map((a, index) => ({
            seq: index + 1,
            name: a.name,
            purpose: a.purpose,
            target_word_ratio: a.target_word_ratio,
          }))

    const saved = await api.adoptArchitecture(projectId, {
      tool_ref: chosen.tool,
      logline: bible.logline,
      theme: bible.theme,
      premise: bible.premise,
      ending_direction: bible.ending_direction,
      acts: actPayload,
    })
    setActs(saved.acts)
    setMessage('已写入项目结构')
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">架构推荐</h2>

      <div className="flex items-center gap-3">
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm disabled:opacity-50"
          onClick={recommend}
          disabled={busy || !projectId}
        >
          {busy ? '生成中…' : '推荐结构'}
        </button>
        {message && <span className="text-sm text-slate-400">{message}</span>}
      </div>

      {recommendation && !recommendation.structured && (
        <div className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">
          未结构化：{recommendation.parse_error}
          <pre className="mt-2 whitespace-pre-wrap text-xs">{recommendation.raw_text}</pre>
        </div>
      )}

      {recommendation?.structured && (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            {recommendation.options.map((option) => (
              <button
                key={option.tool}
                onClick={() => setChosen(option)}
                className={`rounded border p-4 text-left text-sm ${
                  chosen?.tool === option.tool ? 'border-indigo-500 bg-slate-900' : 'border-slate-800'
                }`}
              >
                <div className="mb-2 font-medium text-slate-100">{option.tool}</div>
                <div className="mb-2 text-xs text-slate-400">适配度 {option.fit_score}</div>
                <p className="mb-2 text-slate-300">{option.reason}</p>
                {option.length_plan && (
                  <p className="mb-2 text-xs text-slate-500">篇幅：{option.length_plan}</p>
                )}
                {option.rhythm_shape && (
                  <p className="mb-2 text-xs text-slate-500">节奏：{option.rhythm_shape}</p>
                )}
                <ul className="list-disc space-y-1 pl-4 text-xs text-amber-300">
                  {option.risks.map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </button>
            ))}
          </section>

          <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
            <h3 className="text-sm font-medium text-slate-300">故事圣经 v0</h3>
            <p>
              <span className="text-slate-500">logline：</span>
              {recommendation.story_bible_v0.logline ?? '—'}
            </p>
            <p>
              <span className="text-slate-500">主题句：</span>
              {recommendation.story_bible_v0.theme ?? '—'}
            </p>
            <p>
              <span className="text-slate-500">结局方向：</span>
              {recommendation.story_bible_v0.ending_direction ?? '—'}
            </p>
            <div>
              <div className="text-slate-500">幕骨架</div>
              <ul className="list-disc space-y-1 pl-5">
                {(recommendation.story_bible_v0.acts ?? []).map((act, index) => (
                  <li key={`${act.name}-${index}`}>
                    {act.name}
                    {act.purpose ? ` —— ${act.purpose}` : ''}
                  </li>
                ))}
              </ul>
            </div>
            <button
              className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
              onClick={adopt}
              disabled={!chosen}
            >
              采纳并写入项目
            </button>
          </section>
        </>
      )}

      {acts.length > 0 && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <h3 className="mb-2 text-sm font-medium text-slate-300">已写入的结构</h3>
          <ul className="list-disc space-y-1 pl-5">
            {acts.map((act) => (
              <li key={act.id}>
                第{act.seq}幕 {act.name}
                {act.purpose ? ` —— ${act.purpose}` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}

      {recommendation && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">这次运行</h3>
          <RunTrace run={recommendation.run} />
        </section>
      )}
    </div>
  )
}
```

- [ ] **Step 13: 写 `frontend/src/pages/Studio.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, type Agent, type AgentVersion, type Project, type RunView } from '../api/client'
import RunTrace from '../components/RunTrace'

export default function Studio() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [selected, setSelected] = useState<Agent | null>(null)
  const [versions, setVersions] = useState<AgentVersion[]>([])
  const [draftPrompt, setDraftPrompt] = useState('')
  const [run, setRun] = useState<RunView | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listAgents().then(setAgents)
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!selected) return
    setDraftPrompt(selected.current_version?.system_prompt ?? '')
    api.listVersions(selected.id).then(setVersions)
  }, [selected])

  async function saveVersion() {
    if (!selected) return
    await api.createVersion(selected.id, { system_prompt: draftPrompt, note: '手动编辑' })
    const refreshed = await api.listAgents()
    setAgents(refreshed)
    setSelected(refreshed.find((a) => a.id === selected.id) ?? null)
    setNotice('已保存为新版本')
  }

  async function rollback(versionId: string) {
    if (!selected) return
    await api.rollback(selected.id, versionId)
    const refreshed = await api.listAgents()
    setAgents(refreshed)
    setSelected(refreshed.find((a) => a.id === selected.id) ?? null)
    setNotice('已回滚')
  }

  async function runOnce() {
    if (!selected || !projectId) return
    try {
      const response = await api.runAgent(projectId, selected.id)
      setRun(response.run)
      setNotice('')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">智能体工作室</h2>

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav className="space-y-1">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelected(agent)}
              className={`block w-full rounded px-3 py-2 text-left text-sm ${
                selected?.id === agent.id ? 'bg-slate-800' : 'hover:bg-slate-900'
              }`}
            >
              <span className="mr-2">{agent.role_label}</span>
              {agent.name}
            </button>
          ))}
        </nav>

        {selected ? (
          <div className="space-y-4">
            <div className="text-sm text-slate-400">
              任务类型：{selected.task_type} · 当前版本 v{selected.current_version?.version_no}
            </div>

            <section className="space-y-2">
              <label className="text-sm text-slate-300">系统提示词</label>
              <textarea
                className="h-64 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
                value={draftPrompt}
                onChange={(e) => setDraftPrompt(e.target.value)}
              />
              <div className="flex gap-2">
                <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={saveVersion}>
                  保存为新版本
                </button>
                <button
                  className="rounded border border-slate-700 px-4 py-2 text-sm"
                  onClick={runOnce}
                  disabled={!projectId}
                >
                  单次运行
                </button>
              </div>
              {notice && <p className="text-sm text-slate-400">{notice}</p>}
            </section>

            <section className="text-sm">
              <h3 className="mb-2 font-medium text-slate-300">版本历史</h3>
              <ul className="space-y-1">
                {versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-3">
                    <span className="text-slate-400">v{v.version_no}</span>
                    <span className="text-slate-500">{v.note || '—'}</span>
                    <button className="text-xs text-indigo-400" onClick={() => rollback(v.id)}>
                      回滚到此版本
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            {run && (
              <section className="space-y-2">
                <h3 className="text-sm font-medium text-slate-300">调试台</h3>
                <RunTrace run={run} />
              </section>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">左边挑一个智能体。</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 14: 写 `frontend/src/pages/Models.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, type CostSummary, type Project, type ProviderView, type Settings, type Tool } from '../api/client'
import { costLabel } from '../lib/format'

export default function Models() {
  const [providers, setProviders] = useState<ProviderView[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [tools, setTools] = useState<Tool[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [cost, setCost] = useState<CostSummary | null>(null)
  const [form, setForm] = useState({ name: '', base_url: '', api_key: '' })
  const [notice, setNotice] = useState('')

  useEffect(() => {
    api.listProviders().then(setProviders)
    api.getSettings().then(setSettings)
    api.listTools().then(setTools)
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (projectId) api.projectCost(projectId).then(setCost)
  }, [projectId])

  async function addProvider() {
    if (!form.name.trim() || !form.base_url.trim()) {
      setNotice('名称与接口地址都要填')
      return
    }
    const created = await api.createProvider({
      name: form.name.trim(),
      kind: 'custom',
      base_url: form.base_url.trim(),
      api_key: form.api_key || undefined,
    })
    setProviders((prev) => [...prev, created])
    setForm({ name: '', base_url: '', api_key: '' })
    setNotice('已添加。接口地址填到 /v1 为止，例如 https://api.deepseek.com/v1')
  }

  async function test(id: string) {
    const result = await api.testProvider(id)
    setNotice(`${result.ok ? '正常' : '失败'}：${result.message}`)
  }

  async function saveBudget(value: number) {
    if (!settings) return
    const updated = await api.updateSettings({ context_token_budget: value })
    setSettings(updated)
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">模型与费用</h2>
      {notice && <p className="rounded bg-slate-900 p-3 text-sm text-slate-300">{notice}</p>}

      <section className="space-y-3 rounded border border-slate-800 p-4">
        <h3 className="text-sm font-medium text-slate-300">服务商</h3>
        <div className="flex flex-wrap gap-2">
          <input
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className="w-80 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="接口地址 /v1"
            value={form.base_url}
            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
          />
          <input
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            type="password"
            placeholder="API Key（加密存本机）"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
          />
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={addProvider}>
            添加
          </button>
        </div>

        <ul className="space-y-2 text-sm">
          {providers.map((p) => (
            <li key={p.id} className="flex items-center gap-4">
              <span className="w-32">{p.name}</span>
              <span className="w-64 truncate text-slate-500">{p.base_url}</span>
              <span className="font-mono text-xs text-slate-500">{p.api_key_masked || '未设密钥'}</span>
              <button className="text-xs text-indigo-400" onClick={() => test(p.id)}>
                测试连通性
              </button>
            </li>
          ))}
          {providers.length === 0 && <li className="text-slate-500">还没配置服务商。</li>}
        </ul>
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">上下文预算</h3>
        <div className="flex items-center gap-3">
          <input
            type="number"
            className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={settings?.context_token_budget ?? 8000}
            onChange={(e) => saveBudget(Number(e.target.value))}
          />
          <span className="text-slate-500">tokens。超预算时按优先级裁剪，并明示砍掉了什么。</span>
        </div>
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">费用</h3>
        <select
          className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        {cost && (
          <p className="text-slate-400">
            {cost.runs} 次调用 · {cost.prompt_tokens + cost.completion_tokens} tokens ·{' '}
            {costLabel(cost.cost_estimate)}
          </p>
        )}
      </section>

      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">创作工具库</h3>
        <ul className="space-y-1">
          {tools.map((t) => (
            <li key={t.id}>
              <span className="text-slate-500">[{t.category}]</span> {t.name}
              <span className="ml-2 text-xs text-slate-600">{t.description}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
```

- [ ] **Step 15: 跑前端测试与构建**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/frontend"
pnpm vitest run
pnpm build
```

Expected: 4 项测试通过；构建成功（无 TypeScript 报错）。

- [ ] **Step 16: 写 `scripts/dev.ps1`**

```powershell
# 同时起后端与前端开发服务
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\backend'; uv run uvicorn app.main:app --port 8756 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\frontend'; pnpm dev"
```

- [ ] **Step 17: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add frontend/ scripts/ .gitignore
git commit -m "feat(frontend): 五页应用与接口接通"
```

---

### Task 13: 端到端验收

**Files:**
- Create: `docs/superpowers/plans/2026-10-13-p1a-acceptance.md`（验收记录）
- Modify: `CLAUDE.md` §7（阶段记录与路线图状态）

**Interfaces:**
- Consumes: 全部已完成任务
- Produces: 验收记录

- [ ] **Step 1: 全量后端测试**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/backend"
uv run pytest -v
```

Expected: 全部通过，0 失败。

- [ ] **Step 2: 前端测试与构建**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge/frontend"
pnpm vitest run
pnpm build
```

Expected: 通过。

- [ ] **Step 3: 起服务**

```bash
powershell -File "d:/Practical Project/AIProject/Experiment/StoryForge/scripts/dev.ps1"
```

浏览器打开 `http://127.0.0.1:5173`。

- [ ] **Step 4: 在「模型与费用」配置服务商**

填名称、接口地址（到 `/v1`）与 API Key，点「测试连通性」。若没有真实密钥，可先用 Ollama 或 LM Studio 的本地地址（如 `http://127.0.0.1:11434/v1`）。
验证：密钥输入框在保存后不再回显明文，列表里只显示 `sk-****xxxx` 形式的屏蔽值。

- [ ] **Step 5: 走验收清单**

依次操作并逐条确认：

| # | 操作 | 通过标准 |
|---|---|---|
| 1 | 仪表盘新建项目 | 项目出现在列表，选中后右侧体检单显示 |
| 2 | 灵感页输入原话并「存为灵感」 | 灵感栏出现原话，上方提示「这段文字 AI 不会改」 |
| 3 | 点「解析」 | 解析卡返回；原话一字未变；未把握的问题单列 |
| 4 | 切到架构推荐页，点「推荐结构」 | 出现 2–3 张并排方案卡，每张带理由、适配度、风险 |
| 5 | 选一套，点「采纳并写入项目」 | 「已写入的结构」列出各幕 |
| 6 | 回仪表盘 | 累计调用次数与费用更新 |
| 7 | 打开智能体工作室，选中「架构师」，点「单次运行」 | 调试台显示渲染后完整提示词、原始返回、解析结果、token、耗时、花费 |
| 8 | 改提示词后「保存为新版本」 | 版本号 +1；「回滚到此版本」可切回旧版 |
| 9 | 在模型与费用页调小上下文预算后重跑 | 调试台出现「这次砍掉了：xxx（已丢弃）」提示 |

- [ ] **Step 6: 写验收记录**

把上表的实际结果、遇到的问题与偏差写进 `docs/superpowers/plans/2026-10-13-p1a-acceptance.md`。**任何一项未通过必须如实记录，不得勾选通过。**

- [ ] **Step 7: 更新 `CLAUDE.md`**

- §7 路线图：P1a 状态改为「✅ 已完成」；
- §7 阶段记录追加一条，写清本阶段产出、验证方式与遗留问题；
- §8 变更记录追加（如本阶段产生了新的决策）。

- [ ] **Step 8: 提交**

```bash
cd "d:/Practical Project/AIProject/Experiment/StoryForge"
git add docs/ CLAUDE.md
git commit -m "docs: P1a 验收记录与进度更新"
```

---

## 附：不在本计划范围内

世界观与人物（P1b）、卷章纲与场景卡（P1c）、正文生成与两道检查（P2）、管线编排与 A/B 生成（P3）、影响面分析与快照分支（P4）、阅读器与打包（P5）。spec §1.3 已列明，本计划不建相关表、接口与页面。
