# P1a 收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修掉真实模型验证暴露的三个阻断级缺陷与两处 spec 承诺缺口，让 P1a 在真实模型下端到端可用。

**Architecture:** 三处机制性修复 —— ①字段中文名搬进输出契约的 `title`，渲染层据此自动生成契约说明块，消灭「提示词与契约两份清单」；②超时改为三层解析（角色卡 → 全局设置 → 默认 300 秒）；③版本继承源改为 `current_version_id`。其余是补齐服务商与角色卡的管理界面、故事圣经的编辑能力。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy / pytest；React + TypeScript + Vite + Tailwind；uv 与 pnpm（`CLAUDE.md` §6）。

**Spec:** `docs/superpowers/specs/2026-10-14-p1a-hardening-design.md`

**发现来源:** `docs/superpowers/plans/2026-10-14-real-model-verification-findings.md`

## Global Constraints

- **分层硬约束**：`api` 不写业务逻辑；`services` 不碰 HTTP；`runtime` 不依赖 FastAPI（`CLAUDE.md` §5）。
- **标识符与代码用英文；注释、界面文案、提示词用中文**（`CLAUDE.md` §9）。
- **不引入重型依赖。** JSON Schema 校验与字段说明都用自写子集，不加 `jsonschema`。
- **纯逻辑必须测（pytest），UI 不写自动化测试**（`CLAUDE.md` §9）。
- 测试命令在 `backend/` 下：`uv run pytest`；单测：`uv run pytest tests/<file>::<test> -v`。
- 前端命令在 `frontend/` 下：`pnpm vitest run`、`pnpm build`。
- 后端测试数据目录由 `backend/tests/conftest.py` 用 `STORYFORGE_DATA_DIR` 指向临时目录，`session` 夹具每个用例重建表。
- 数据库类型：`AgentVersion.model_binding_json` / `context_slots_json` / `output_schema_json` / `skills_json` 是 JSON 列；`Agent.enabled` 是布尔。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/runtime/contract.py` | 由输出契约生成给模型看的字段说明 | 新建 |
| `backend/app/runtime/execute.py` | 编排：渲染后追加契约说明块 | 改 |
| `backend/app/agents/roster.py` | 预置阵容：契约加 `title`、提示词删手写字段清单 | 改 |
| `backend/app/config.py` | 全局设置默认值（加超时） | 改 |
| `backend/app/runtime/llm.py` | 超时文案带上限值 | 改 |
| `backend/app/services/runtime_service.py` | 解析超时并注入客户端 | 改 |
| `backend/app/services/agent_service.py` | 版本继承源；agent 级字段更新 | 改 |
| `backend/app/services/provider_service.py` | 连通性测试收紧 | 改 |
| `backend/app/api/schemas.py` | 出入参模型（加 `AgentUpdate`、`ProviderTest`） | 改 |
| `backend/app/api/agents.py` | 加 `PATCH /api/agents/{id}` | 改 |
| `backend/app/api/slots.py` | 槽位清单投影 | 新建 |
| `backend/app/api/providers.py` | 连通性测试接受模型名 | 改 |
| `backend/app/main.py` | 注册 slots 路由 | 改 |
| `frontend/src/api/client.ts` | 接口封装与类型 | 改 |
| `frontend/src/pages/Studio.tsx` | 角色卡全字段编辑 + 模型绑定 | 重写 |
| `frontend/src/pages/Architecture.tsx` | 故事圣经可编辑 + L1 手动录入 + 空态 | 重写 |
| `frontend/src/pages/Models.tsx` | 服务商改删 + 超时设置 + 测试用模型名 | 改 |
| `frontend/index.html` | 标题与 lang | 改 |

---

### Task 1: 契约说明生成器

**Files:**
- Create: `backend/app/runtime/contract.py`
- Test: `backend/tests/test_contract.py`

**Interfaces:**
- Consumes: 无（纯函数，不依赖其余模块）
- Produces: `describe_contract(schema: dict | None) -> str`。空 schema 或 `None` 返回空串 `""`。生成的文本里，每个字段键以小写英文字母开头、紧跟 `（中文名）` 或 `：`，形如 `- genre（题材）：字符串，必填`；嵌套对象缩进两格。

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_contract.py`：

```python
from app.runtime.contract import describe_contract

SIMPLE = {
    "type": "object",
    "required": ["genre", "open_questions"],
    "properties": {
        "genre": {"type": "string", "title": "题材"},
        "sub_genre": {"type": "string", "title": "子类型"},
        "open_questions": {"type": "array", "items": {"type": "string"}, "title": "它没把握的问题"},
    },
}

NESTED = {
    "type": "object",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "minItems": 2,
            "title": "候选方案",
            "items": {
                "type": "object",
                "required": ["tool", "fit_score"],
                "properties": {
                    "tool": {"type": "string", "title": "结构名"},
                    "fit_score": {"type": "number", "title": "适配度"},
                    "risks": {"type": "array", "items": {"type": "string"}, "title": "风险"},
                },
            },
        },
    },
}


def test_empty_schema_returns_empty_string():
    assert describe_contract(None) == ""
    assert describe_contract({}) == ""


def test_describes_top_level_keys_with_chinese_titles():
    block = describe_contract(SIMPLE)
    assert "- genre（题材）：字符串，必填" in block
    assert "- sub_genre（子类型）：字符串" in block
    assert "必填" not in block.split("- sub_genre（子类型）")[1].split("\n")[0]


def test_describes_array_element_type_and_min_items():
    block = describe_contract(SIMPLE)
    assert "- open_questions（它没把握的问题）：数组" in block
    assert "元素是字符串" in block


def test_describes_nested_object_fields():
    block = describe_contract(NESTED)
    assert "- options（候选方案）：数组" in block
    assert "至少 2 项" in block
    # 元素对象的字段要出现在 options 之后、且缩进更深
    assert "  - tool（结构名）：字符串，必填" in block
    assert "  - fit_score（适配度）：数字，必填" in block
    assert "  - risks（风险）：数组" in block


def test_key_without_title_has_no_parentheses():
    block = describe_contract(
        {"type": "object", "properties": {"bare_key": {"type": "string"}}}
    )
    assert "- bare_key：字符串" in block


def test_enum_values_are_listed():
    block = describe_contract(
        {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["loose", "strict"], "title": "严格度"}
            },
        }
    )
    assert "取值：loose、strict" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.runtime.contract'`

- [ ] **Step 3: Write minimal implementation**

创建 `backend/app/runtime/contract.py`：

```python
"""由输出契约生成给模型看的字段说明。

契约为字段名与中文名的唯一真相：中文名写在属性的 `title` 上（JSON Schema
标准关键字，校验器不读它）。渲染层据此自动生成说明块追加到提示词之后，
于是提示词里不必再手抄一份字段清单 —— 两份独立维护的清单正是键名不一致的根源。
"""

from __future__ import annotations

_TYPE_LABELS = {
    "object": "对象",
    "array": "数组",
    "string": "字符串",
    "number": "数字",
    "integer": "整数",
    "boolean": "布尔值",
}

_HEADER = "【输出契约】返回一个 JSON 对象，键名一律用英文。字段如下："


def describe_contract(schema: dict | None) -> str:
    """空 schema 返回空串：不定义契约的智能体不该被塞一段空说明。"""
    if not schema:
        return ""
    lines: list[str] = [_HEADER]
    _describe_object(schema, lines, depth=1)
    return "\n".join(lines)


def _describe_object(node: dict, lines: list[str], depth: int) -> None:
    required = set(node.get("required") or [])
    for key, sub in (node.get("properties") or {}).items():
        _describe_field(key, sub, key in required, lines, depth)


def _describe_field(
    key: str, node: dict, required: bool, lines: list[str], depth: int
) -> None:
    pad = "  " * depth
    title = node.get("title")
    name = f"{key}（{title}）" if title else key

    parts = [_type_label(node)]
    if node.get("type") == "array":
        item = node.get("items") or {}
        if node.get("minItems"):
            parts.append(f"至少 {node['minItems']} 项")
        if item.get("properties"):
            parts.append("每项是一个对象")
        else:
            parts.append(f"元素是{_type_label(item)}")
    if node.get("enum"):
        parts.append("取值：" + "、".join(str(v) for v in node["enum"]))
    if required:
        parts.append("必填")

    lines.append(f"{pad}- {name}：{'，'.join(parts)}")
    _describe_children(node, lines, depth)


def _describe_children(node: dict, lines: list[str], depth: int) -> None:
    if node.get("type") == "object" and node.get("properties"):
        _describe_object(node, lines, depth + 1)
        return
    if node.get("type") == "array":
        item = node.get("items") or {}
        if item.get("type") == "object" and item.get("properties"):
            _describe_object(item, lines, depth + 1)


def _type_label(node: dict) -> str:
    return _TYPE_LABELS.get(node.get("type") or "", "值")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_contract.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/contract.py backend/tests/test_contract.py
git commit -m "feat(runtime): 由输出契约生成字段说明块"
```

---

### Task 2: 编排层追加契约说明块

**Files:**
- Modify: `backend/app/runtime/execute.py:81-91`
- Test: `backend/tests/test_execute.py`

**Interfaces:**
- Consumes: `describe_contract(schema) -> str`（Task 1）
- Produces: `execute_run` 发出的 prompt 与 `RunResult.rendered_prompt` 均为「渲染后的提示词 + 空行 + 契约说明块」（无 schema 时不追加）。下游 Task 7 的调试台因此看到的就是真发出去的那份。

- [ ] **Step 1: Write the failing test**

本文件已有 `FakeSource`、`_input(**overrides)`、`_client(handler)`、`_ok_handler(...)` 四个辅助件，直接复用。

**先改两条会被这次改动打破的既有测试 —— 它们在两个不同的文件里，别只改一个。**

两处都是「渲染结果**等于**纯提示词」的等值断言；加了契约块之后必然失败（两处的 `output_schema` 都非空）。

`backend/tests/test_execute.py`，`test_rendered_prompt_reflects_context_and_template`（约第 92-95 行）：

```python
async def test_rendered_prompt_reflects_context_and_template():
    source = FakeSource(raw_idea="能听见死者遗言的验尸官")
    result = await execute_run(_input(), source, _client(_ok_handler('{"genre":"悬疑"}')))
    assert result.rendered_prompt.startswith("解析这段灵感：能听见死者遗言的验尸官")
```

`backend/tests/test_runtime_service.py`，`test_execute_writes_generation_run`（约第 60 行），把

```python
    assert stored.rendered_prompt == "解析这段灵感：能听见死者遗言的验尸官"
```

改为

```python
    assert stored.rendered_prompt.startswith("解析这段灵感：能听见死者遗言的验尸官")
    assert "【输出契约】" in stored.rendered_prompt
```

**再加两条新测试**，追加到 `backend/tests/test_execute.py` 末尾：

```python
async def test_contract_block_is_appended_to_the_sent_prompt():
    """契约说明块必须真的发出去，且落库的 rendered_prompt 就是发出那份（D-03）。"""
    sent: dict = {}

    def handler(request):
        sent["body"] = json.loads(request.read().decode())
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    schema = {
        "type": "object",
        "required": ["genre"],
        "properties": {"genre": {"type": "string", "title": "题材"}},
    }
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(output_schema=schema), source, _client(handler))

    assert result.rendered_prompt.startswith("解析这段灵感：灵感")
    assert "- genre（题材）：字符串，必填" in result.rendered_prompt
    # 落库的必须与发出去的一字不差 —— 用解析后的 JSON 比，不能拿原始 body 做子串匹配
    # （body 里的换行是转义过的 \n，跟真字符串对不上）。
    assert sent["body"]["messages"][0]["content"] == result.rendered_prompt


async def test_no_contract_block_when_schema_is_absent():
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(output_schema=None), source, _client(_ok_handler("{}")))

    assert result.rendered_prompt == "解析这段灵感：灵感"
    assert "【输出契约】" not in result.rendered_prompt
```

文件顶部需要补 `import json`。

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_execute.py -v -k contract_block`
Expected: FAIL — `assert '- genre（题材）：字符串，必填' in result.rendered_prompt`

- [ ] **Step 3: Write minimal implementation**

`backend/app/runtime/execute.py`：加导入并在渲染之后追加。

```python
from app.runtime.contract import describe_contract
```

把 `execute_run` 里这三行：

```python
    bundle = build_context(inp.context_slots, source, inp.token_budget)
    try:
        rendered_prompt = render(inp.system_prompt, bundle.contents)
    except MissingVariableError as exc:
        return _failure(inp, started, str(exc), kind="template", trimmed=bundle.trimmed)
```

改为：

```python
    bundle = build_context(inp.context_slots, source, inp.token_budget)
    try:
        rendered_prompt = render(inp.system_prompt, bundle.contents)
    except MissingVariableError as exc:
        return _failure(inp, started, str(exc), kind="template", trimmed=bundle.trimmed)

    # 契约说明块在渲染之后追加：块里没有模板变量，而落库的 rendered_prompt
    # 必须是真正发出去的那一份，调试台才对得上（D-03）。
    contract_block = describe_contract(inp.output_schema)
    if contract_block:
        rendered_prompt = f"{rendered_prompt}\n\n{contract_block}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_execute.py -v`
Expected: 新增两条 PASS，原有全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/execute.py backend/tests/test_execute.py backend/tests/test_runtime_service.py
git commit -m "feat(runtime): 提示词渲染后追加契约说明块"
```

---

### Task 3: 预置阵容改用 title 承载中文名

**Files:**
- Modify: `backend/app/agents/roster.py`（两个 schema 加 `title`；两段提示词删掉手写字段清单）
- Test: `backend/tests/test_roster.py`

**Interfaces:**
- Consumes: `describe_contract`（Task 1）
- Produces: `IDEA_PARSE_SCHEMA` 与 `ARCHITECTURE_SCHEMA` 的每个 property 都带中文 `title`；两段预置提示词里不再出现任何 snake_case 字段键（槽位变量除外）。

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_roster.py` 末尾追加：

```python
import re

from app.runtime.contract import describe_contract

_KEY_IN_BLOCK = re.compile(r"^\s*- ([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def _property_keys(schema: dict) -> set[str]:
    """递归收集契约里出现过的全部字段键。"""
    keys: set[str] = set()
    for key, sub in (schema.get("properties") or {}).items():
        keys.add(key)
        if sub.get("type") == "object":
            keys |= _property_keys(sub)
        elif sub.get("type") == "array":
            item = sub.get("items") or {}
            if item.get("type") == "object":
                keys |= _property_keys(item)
    return keys


def test_contract_block_covers_every_field_of_every_preset_agent():
    """跨产物一致性：契约里的每个字段，说明块都必须讲到。

    这是本切片补的关键测试。旧测试把「提示词」与「契约」分开验，没有一条
    要求两者一致，于是键名不一致在真实模型下必败、却全程没被发现。
    """
    for entry in DEFAULT_ROSTER:
        schema = entry["output_schema"]
        described = set(_KEY_IN_BLOCK.findall(describe_contract(schema)))
        missing = _property_keys(schema) - described
        assert not missing, f"{entry['key']} 的契约说明块漏了字段：{sorted(missing)}"


def test_every_schema_property_carries_a_chinese_title():
    """字段清单只能有一份：中文名必须长在契约上，提示词不再手抄。"""
    def walk(node: dict, path: str) -> None:
        for key, sub in (node.get("properties") or {}).items():
            assert sub.get("title"), f"{path}.{key} 缺少中文 title"
            if sub.get("type") == "object":
                walk(sub, f"{path}.{key}")
            elif sub.get("type") == "array" and (sub.get("items") or {}).get("type") == "object":
                walk(sub["items"], f"{path}.{key}[]")

    for entry in DEFAULT_ROSTER:
        walk(entry["output_schema"], entry["key"])


_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# 提示词里正当出现的非字段英文词（故事圣经 v0 的版本号）
_ALLOWED_LATIN = {"v0"}


def test_preset_prompts_do_not_hand_list_field_keys():
    """提示词里不许再出现字段键 —— 那份清单已由契约说明块自动生成。

    不能只查 snake_case：schema 的键多为单字（genre/premise/reason/tool…），
    而「在 reason 里说明缺什么」这种漂移正是最可能的复发形态。
    """
    for entry in DEFAULT_ROSTER:
        allowed = set(entry["context_slots"]) | _ALLOWED_LATIN
        found = set(_WORD_RE.findall(entry["system_prompt"]))
        hand_listed = found - allowed
        assert not hand_listed, f"{entry['key']} 的提示词手写了字段键：{sorted(hand_listed)}"


def test_adding_titles_does_not_change_validation():
    """title 是给渲染层读的，校验器不该受它影响 —— 加字段说明不该改动校验语义。"""
    from app.runtime.schema import apply_contract

    parser = next(e for e in DEFAULT_ROSTER if e["key"] == "idea_parser")
    valid = (
        '{"genre": "悬疑", "premise": "p", "protagonist_desire": "d",'
        ' "conflict_source": "c", "open_questions": []}'
    )
    parsed, ok, error = apply_contract(valid, parser["output_schema"])
    assert ok is True and error is None
    assert parsed["genre"] == "悬疑"

    _, ok_missing, error_missing = apply_contract('{"genre": "悬疑"}', parser["output_schema"])
    assert ok_missing is False
    assert "premise" in (error_missing or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_roster.py -v -k "contract_block or chinese_title or hand_list"`
Expected: FAIL —— 三张测试都会失败（没有 title；提示词里带着 `open_questions` / `reason`）

- [ ] **Step 3: Write minimal implementation**

`backend/app/agents/roster.py`：给两个 schema 的每个 property 加 `title`，并把两段提示词改写为不含字段键的版本。

```python
IDEA_PARSE_SCHEMA = {
    "type": "object",
    "required": ["genre", "premise", "protagonist_desire", "conflict_source", "open_questions"],
    "properties": {
        "genre": {"type": "string", "title": "题材"},
        "sub_genre": {"type": "string", "title": "子类型"},
        "premise": {"type": "string", "title": "一句话前提"},
        "protagonist_desire": {"type": "string", "title": "主角欲望"},
        "conflict_source": {"type": "string", "title": "核心冲突源"},
        "emotional_core": {"type": "string", "title": "情感内核"},
        "tone": {"type": "string", "title": "调性"},
        "length_expectation": {"type": "string", "title": "篇幅预期"},
        "comparable_works": {"type": "array", "items": {"type": "string"}, "title": "可能参考坐标"},
        "open_questions": {"type": "array", "items": {"type": "string"}, "title": "它没把握的问题"},
    },
}

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "required": ["options"],
    "properties": {
        "options": {
            "type": "array",
            "minItems": 2,
            "title": "候选方案",
            "items": {
                "type": "object",
                "required": ["tool", "reason", "fit_score", "risks"],
                "properties": {
                    "tool": {"type": "string", "title": "结构名"},
                    "reason": {"type": "string", "title": "适配理由"},
                    "fit_score": {"type": "number", "title": "适配度"},
                    "risks": {"type": "array", "items": {"type": "string"}, "title": "风险"},
                    "length_plan": {"type": "string", "title": "篇幅分配"},
                    "rhythm_shape": {"type": "string", "title": "节奏形态"},
                },
            },
        },
        "story_bible_v0": {
            "type": "object",
            "title": "故事圣经 v0",
            "properties": {
                "logline": {"type": "string", "title": "一句话故事"},
                "theme": {"type": "string", "title": "主题句"},
                "premise": {"type": "string", "title": "前提"},
                "acts": {
                    "type": "array",
                    "title": "幕骨架",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string", "title": "幕名"},
                            "purpose": {"type": "string", "title": "这一幕要做什么"},
                            "target_word_ratio": {"type": "number", "title": "篇幅占比"},
                        },
                    },
                },
                "main_characters": {
                    "type": "array",
                    "title": "主要人物",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "title": "人物名"},
                            "role": {"type": "string", "title": "定位"},
                            "desire": {"type": "string", "title": "他/她想要什么"},
                        },
                    },
                },
                "ending_direction": {"type": "string", "title": "结局方向"},
            },
        },
    },
}
```

两段提示词改为（注意：全篇不出现 snake_case 字段键，字段的键名与中文名由运行时自动追加的【输出契约】块给出）：

```python
IDEA_PARSER_PROMPT = """你是长篇小说灵感解析师，服务对象是作者。你的产出是结构化的解析卡，不是改写。

【作者原话】
{{ raw_idea }}

要求：
1. 逐项填写解析卡，字段的键名与含义见下方【输出契约】；
2. 主角欲望要写成「他/她想要什么」，不是「他/她是什么人」；
3. 核心冲突源要指出对撞的两股力量，而不是罗列敌人；
4. 可能参考坐标只写气质相近的作品，不写抄袭对象；
5. 你没把握的地方一律写进「它没把握的问题」这一项，向作者提问，不许编造设定填空；
6. 不要改写作者的原话，也不要在返回里复述它。"""

ARCHITECT_PROMPT = """你是长篇小说结构顾问，服务对象是作者。你的产出是候选方案加理由，不是最终决定。

【灵感解析卡】
{{ parsed_idea }}

【项目信息】
{{ project_core }}

【可用结构工具】
{{ tool_library }}

要求：
1. 给出 2–3 套适配结构，每套的适配理由必须引用解析卡中的具体要素，不许泛泛而谈「符合三幕剧」；
2. 每套写明适配度（0–1 的小数，不是百分数）、风险、篇幅分配与节奏形态；
3. 每套的适配理由末尾要写明这套结构的不适用情形；
4. 允许并鼓励杂交方案（如三幕骨架、第二幕内部走七点结构），杂交时在适配理由里说清是哪两层杂交；
5. 结局方向只作建议，不替作者决定；
6. 同时给出故事圣经 v0；
7. 信息不足时在适配理由里说明缺什么，不要编造设定。"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_roster.py -v`
Expected: 全部 PASS（含原有的 6 条）

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/roster.py backend/tests/test_roster.py
git commit -m "refactor(agents): 字段中文名搬进契约 title，提示词不再手抄清单"
```

---

### Task 4: 超时可配置

**Files:**
- Modify: `backend/app/config.py:12-17`、`backend/app/runtime/llm.py:106-111`、`backend/app/services/runtime_service.py:21-25,63-84`
- Test: `backend/tests/test_llm.py`、`backend/tests/test_runtime_service.py`

**Interfaces:**
- Consumes: 无
- Produces: `HttpxChatClient(timeout: float = 120.0)` 签名不变，但由调用方注入；超时解析顺序为 `model_binding_json["timeout_seconds"]` → 全局设置 `request_timeout_seconds` → `300.0`。超时错误的 `message` 形如 `请求超时（上限 300 秒，ReadTimeout）`。

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_llm.py` 末尾追加：

```python
import httpx
import pytest

from app.runtime.llm import ChatConfig, ChatFailure, HttpxChatClient


async def test_timeout_message_carries_the_limit():
    """httpx 超时异常的 str() 常为空串，文案必须自己带上限值，
    否则界面上显示的是「请求超时：」后面什么都没有。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    client = HttpxChatClient(transport=httpx.MockTransport(handler), timeout=275.0)
    with pytest.raises(ChatFailure) as excinfo:
        await client.complete(
            ChatConfig(base_url="http://x/v1", api_key="k", model="m"), [], {}
        )

    assert excinfo.value.error.kind == "timeout"
    assert "275" in excinfo.value.error.message
    assert not excinfo.value.error.message.endswith("：")
```

在 `backend/tests/test_runtime_service.py` 末尾追加：

```python
def test_timeout_falls_back_to_global_setting(session, monkeypatch):
    from app import config
    from app.services.runtime_service import RuntimeService

    config.save_settings({"request_timeout_seconds": 456})
    service = RuntimeService(session)
    assert service._resolve_timeout({}) == 456.0


def test_agent_level_timeout_wins(session):
    from app.services.runtime_service import RuntimeService

    service = RuntimeService(session)
    assert service._resolve_timeout({"timeout_seconds": 90}) == 90.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm.py::test_timeout_message_carries_the_limit tests/test_runtime_service.py -v -k "timeout"`
Expected: FAIL —— `AssertionError`（文案里没有 275）与 `AttributeError: '_resolve_timeout'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/config.py`，在 `DEFAULT_SETTINGS` 里加一行：

```python
DEFAULT_SETTINGS: dict = {
    "context_token_budget": 8000,
    "default_params": {"temperature": 0.7, "max_tokens": 4096},
    "model_routing": {},
    "budget_alert": None,
    # 重推理模型在长任务上实测需要 139.5 秒，写死 120 秒会让架构推荐必然失败。
    "request_timeout_seconds": 300,
}
```

`backend/app/runtime/llm.py`，把 `_wrap_transport_error` 改为：

```python
    def _wrap_transport_error(self, exc: Exception) -> ChatFailure:
        if isinstance(exc, httpx.TimeoutException):
            # httpx 的 str() 常是空串，所以自己把上限与类型写进文案，
            # 否则界面显示成「请求超时：」后面什么都没有。
            detail = str(exc).strip()
            label = f"请求超时（上限 {self._timeout:g} 秒，{type(exc).__name__}）"
            return ChatFailure(ChatError("timeout", f"{label}：{detail}" if detail else label))
        if isinstance(exc, httpx.TransportError):
            return ChatFailure(ChatError("network", f"网络错误：{exc}"))
        return ChatFailure(ChatError("network", f"调用失败：{exc}"))
```

`backend/app/services/runtime_service.py`：

把 `_resolve_client` 换成：

```python
    def _resolve_client(self, timeout: float) -> ChatClient:
        """单独成一个方法，测试可以替换它以注入假传输层。

        不缓存默认客户端：超时是逐次运行解析出来的，缓存会让第一次的值
        粘住后续所有调用。
        """
        if self._client is not None:
            return self._client
        return HttpxChatClient(timeout=timeout)

    def _resolve_timeout(self, binding: dict) -> float:
        """超时三层解析：角色卡 → 全局设置 → 默认。让慢模型可被单独放宽。"""
        agent_level = binding.get("timeout_seconds")
        if agent_level:
            return float(agent_level)
        return float(config.load_settings().get("request_timeout_seconds", 300))
```

在 `execute` 里，把这一行：

```python
        result = _run_sync(execute_run, inp, source, self._resolve_client())
```

改为：

```python
        result = _run_sync(execute_run, inp, source, self._resolve_client(self._resolve_timeout(binding)))
```

**还要修一处测试补丁 —— 不修会打挂 `test_api.py` 里 5 条既有测试。**

`backend/tests/test_api.py:177` 用单参 lambda 替换了 `_resolve_client`：

```python
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self: fake)
```

`_resolve_client` 现在多了一个 `timeout` 参数，调用点会传两个实参，于是这个 lambda 会抛 `TypeError: <lambda>() takes 1 positional argument but 2 were given`。改为接收并忽略它（假传输层没有超时语义）：

```python
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self, timeout: fake)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm.py tests/test_runtime_service.py tests/test_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/runtime/llm.py backend/app/services/runtime_service.py backend/tests/test_llm.py backend/tests/test_runtime_service.py backend/tests/test_api.py
git commit -m "feat(runtime): 请求超时可配置，默认 300 秒"
```

---

### Task 5: 版本继承取当前版本

**Files:**
- Modify: `backend/app/services/agent_service.py:26-59`
- Test: `backend/tests/test_agents_service.py`（不存在则新建）

**Interfaces:**
- Consumes: `Agent.current_version_id`、`AgentVersion.version_no`
- Produces: `create_version` 的**版本号**仍取 `max(version_no)+1`，**内容继承源**改为 `agent.current_version_id` 指向的版本（取不到时回退到版本号最大的那个）。

- [ ] **Step 1: Write the failing test**

创建或追加到 `backend/tests/test_agents_service.py`：

```python
import pytest

from app.db.models import Agent, AgentVersion
from app.services import agent_service


def _make_agent(session, prompt: str = "v1 提示词") -> Agent:
    agent = Agent(name="测试智能体", role_label="测试", task_type="idea_parse")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        system_prompt=prompt,
        context_slots_json=["raw_idea"],
        model_binding_json={"model": "m1"},
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return agent


def test_new_version_after_rollback_inherits_the_current_version(session):
    """回滚之后，「当前版本」不再是版本号最大的那个。

    取最大版本号会把作者刚弃用的内容悄悄带回来 —— 而「回滚到好版本，
    基于它改一改再保存」正是作者最自然的操作路径。
    """
    agent = _make_agent(session, prompt="v1 正确提示词")

    v2 = agent_service.create_version(session, agent.id, system_prompt="v2 测试串")
    assert v2.version_no == 2

    agent_service.rollback_to(session, agent.id, agent.current_version_id)  # 无副作用
    v1 = [v for v in agent_service.list_versions(session, agent.id) if v.version_no == 1][0]
    agent_service.rollback_to(session, agent.id, v1.id)

    v3 = agent_service.create_version(session, agent.id, note="只改了备注")

    assert v3.version_no == 3
    assert v3.system_prompt == "v1 正确提示词"
    assert v3.model_binding_json == {"model": "m1"}
    assert v3.context_slots_json == ["raw_idea"]


def test_explicit_fields_still_win_over_inheritance(session):
    agent = _make_agent(session)
    v2 = agent_service.create_version(session, agent.id, system_prompt="全新的")
    assert v2.system_prompt == "全新的"
    assert v2.model_binding_json == {"model": "m1"}  # 未显式给的字段仍继承


def test_first_version_of_an_empty_agent(session):
    agent = Agent(name="空智能体", task_type="idea_parse")
    session.add(agent)
    session.commit()

    v1 = agent_service.create_version(session, agent.id, system_prompt="首版")
    assert v1.version_no == 1
    assert v1.system_prompt == "首版"
    assert v1.param_profile == "balanced"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agents_service.py -v`
Expected: FAIL —— `assert 'v2 测试串' == 'v1 正确提示词'`（继承到的是 v2）

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/agent_service.py`，把 `create_version` 里的取版本号那段改为：

```python
def create_version(session: Session, agent_id: str, **fields) -> AgentVersion:
    """插入新版本并移动 current_version_id。旧版本保留，可回滚。

    两件事用的是不同的源，别合并：
    - **版本号**取最大版本号 + 1，避免与历史撞号（回滚后新建必然撞）；
    - **内容继承源**取 `current_version_id` 指向的版本，而不是版本号最大的
      那个 —— 回滚之后这两者会分叉，取错会把作者刚弃用的内容悄悄带回来。
    """
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")

    highest = session.scalars(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.version_no.desc())
    ).first()
    base = (
        session.get(AgentVersion, agent.current_version_id)
        if agent.current_version_id
        else None
    ) or highest

    version = AgentVersion(
        agent_id=agent_id,
        version_no=(highest.version_no + 1) if highest else 1,
        system_prompt=fields.get("system_prompt", base.system_prompt if base else ""),
        model_binding_json=fields.get(
            "model_binding_json", base.model_binding_json if base else {}
        ),
        param_profile=fields.get("param_profile", base.param_profile if base else "balanced"),
        context_slots_json=fields.get(
            "context_slots_json", base.context_slots_json if base else []
        ),
        output_schema_json=fields.get(
            "output_schema_json", base.output_schema_json if base else None
        ),
        skills_json=fields.get("skills_json", base.skills_json if base else []),
        trigger_mode=fields.get("trigger_mode", base.trigger_mode if base else "manual"),
        note=fields.get("note", ""),
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return version
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agents_service.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_service.py backend/tests/test_agents_service.py
git commit -m "fix(agents): 版本继承取当前版本，不再继承被弃用版本"
```

---

### Task 6: agent 级字段更新与槽位清单接口

**Files:**
- Modify: `backend/app/api/schemas.py`（加 `AgentUpdate`）、`backend/app/services/agent_service.py`（加 `update_agent`）、`backend/app/api/agents.py`（加 `PATCH`）、`backend/app/main.py`
- Create: `backend/app/api/slots.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `SLOT_REGISTRY`（`app.runtime.context`）
- Produces:
  - `PATCH /api/agents/{agent_id}` 收 `{name?, role_label?, color?, enabled?}`，返回与 `GET /api/agents` 同形的单个对象（`_agent_out`）。
  - `GET /api/slots` 返回 `[{key, label, priority, over_budget}]`，按优先级降序。
  - `agent_service.update_agent(session, agent_id, **fields) -> Agent`。

- [ ] **Step 1: Write the failing test**

本文件的 `client` 夹具（第 13-32 行）已经在建表后调用了 `seed_agents` / `seed_tools`，并补了一家启用的服务商 —— 所以下面三条**只用 `client`**，不要再去碰 `session` 夹具（两者各自重建表，混用会把数据冲掉）。

追加到 `backend/tests/test_api.py` 末尾：

```python
def test_patch_agent_updates_agent_level_fields(client):
    agent = client.get("/api/agents").json()[0]

    response = client.patch(
        f"/api/agents/{agent['id']}",
        json={"role_label": "解析官", "color": "#ff0000", "enabled": False},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["role_label"] == "解析官"
    assert updated["color"] == "#ff0000"
    assert updated["enabled"] is False
    assert updated["name"] == agent["name"]  # 没传的字段不动
    assert updated["task_type"] == agent["task_type"]
    # 改 agent 级字段不该产生新版本
    assert updated["current_version"]["version_no"] == agent["current_version"]["version_no"]


def test_patch_unknown_agent_is_404(client):
    assert client.patch("/api/agents/nope", json={"name": "x"}).status_code == 404


def test_slots_endpoint_reflects_the_registry(client):
    from app.runtime.context import SLOT_REGISTRY

    payload = client.get("/api/slots").json()

    assert {s["key"] for s in payload} == set(SLOT_REGISTRY)
    assert payload == sorted(payload, key=lambda s: -s["priority"])
    by_key = {s["key"]: s for s in payload}
    assert by_key["raw_idea"]["label"] == SLOT_REGISTRY["raw_idea"].label
    assert by_key["raw_idea"]["over_budget"] == "drop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py -v -k "patch_agent or slots_endpoint"`
Expected: FAIL — 405 / 404（路由不存在）

- [ ] **Step 3: Write minimal implementation**

`backend/app/api/schemas.py` 末尾追加：

```python
class AgentUpdate(BaseModel):
    """agent 级字段。改这些不动版本 —— 版本只承载提示词与运行配置（D-06）。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    role_label: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)
    enabled: bool | None = None
```

`backend/app/services/agent_service.py` 末尾追加：

```python
_AGENT_LEVEL_FIELDS = ("name", "role_label", "color", "enabled")


def update_agent(session: Session, agent_id: str, **fields) -> Agent:
    """只改 agent 级字段，不产生新版本。"""
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")
    for key in _AGENT_LEVEL_FIELDS:
        value = fields.get(key)
        if value is not None:
            setattr(agent, key, value)
    session.commit()
    return agent
```

`backend/app/api/agents.py`：导入 `AgentUpdate`，并在 `list_agents` 之后加：

```python
@router.patch("/{agent_id}")
def update_agent(
    agent_id: str, payload: AgentUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        agent = agent_service.update_agent(
            session, agent_id, **payload.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    version = (
        agent_service.get_version(session, agent.current_version_id)
        if agent.current_version_id
        else None
    )
    return _agent_out(agent, version)
```

创建 `backend/app/api/slots.py`：

```python
"""槽位清单。唯一真相在 runtime/context.py 的 SLOT_REGISTRY，这里只做投影 ——
前端不必再硬编一份，否则又会出现「两份清单互相不一致」的老问题。"""

from __future__ import annotations

from fastapi import APIRouter

from app.runtime.context import SLOT_REGISTRY

router = APIRouter(prefix="/api/slots", tags=["slots"])


@router.get("")
def list_slots() -> list[dict]:
    return [
        {"key": spec.key, "label": spec.label, "priority": spec.priority, "over_budget": spec.over_budget}
        for spec in sorted(SLOT_REGISTRY.values(), key=lambda s: -s.priority)
    ]
```

`backend/app/main.py`：把 `slots` 加进导入与挂载循环：

```python
from app.api import agents, architecture, ideas, projects, providers, runs, slots, tools
...
for module in (projects, ideas, architecture, agents, runs, tools, providers, slots):
    app.include_router(module.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/schemas.py backend/app/api/agents.py backend/app/api/slots.py backend/app/services/agent_service.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): agent 级字段更新与槽位清单接口"
```

---

### Task 7: 连通性测试改为真实验证模型

**Files:**
- Modify: `backend/app/api/schemas.py`（加 `ProviderTest`）、`backend/app/services/provider_service.py:62-94`、`backend/app/api/providers.py:61-63`
- Test: `backend/tests/test_provider_service.py`（不存在则新建）

**Interfaces:**
- Consumes: `HttpxChatClient`、`ChatFailure`、`config.load_settings()`
- Produces: `provider_service.test_connection(session, provider_id, model: str | None = None) -> {ok: bool, message: str}`。`POST /api/providers/{id}/test` 接受可选 body `{"model": "..."}`。

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_provider_service.py`：

```python
import httpx
import pytest

from app.db.models import Agent, AgentVersion, Provider
from app.runtime.llm import HttpxChatClient
from app.services import provider_service


@pytest.fixture()
def provider(session):
    p = Provider(name="测试商", kind="custom", base_url="http://x/v1", enabled=True)
    session.add(p)
    session.commit()
    return p


def _service_with(monkeypatch, handler) -> None:
    """把 HttpxChatClient 换成假传输层，不打真实网络。"""
    monkeypatch.setattr(
        provider_service,
        "HttpxChatClient",
        lambda **kwargs: HttpxChatClient(transport=httpx.MockTransport(handler), **kwargs),
    )


def _bind_model(session, provider, model: str) -> None:
    agent = Agent(name="某智能体", task_type="idea_parse")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version_no=1,
        model_binding_json={"provider_id": provider.id, "model": model},
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}], "usage": {}})


def _status(code: int, message: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, json={"error": {"message": message}})

    return handler


def test_uses_the_model_bound_to_an_agent(session, provider, monkeypatch):
    """空模型名发请求是假阳性的根源：它只证明地址可达，不证明模型可用。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return _ok(request)

    _bind_model(session, provider, "qwen3.8-flash")
    _service_with(monkeypatch, handler)

    result = provider_service.test_connection(session, provider.id)

    assert result["ok"] is True
    assert "qwen3.8-flash" in seen["body"]
    assert "qwen3.8-flash" in result["message"]


def test_refuses_to_probe_without_a_model(session, provider, monkeypatch):
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _ok(request)

    _service_with(monkeypatch, handler)
    result = provider_service.test_connection(session, provider.id)

    assert result["ok"] is False
    assert "绑定模型" in result["message"]
    assert called is False  # 不发无意义的请求


def test_explicit_model_wins(session, provider, monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return _ok(request)

    _service_with(monkeypatch, handler)
    provider_service.test_connection(session, provider.id, model="手工填的模型")
    assert "手工填的模型" in seen["body"]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (400, "请求被拒"),
        (401, "密钥无效"),
        (403, "密钥无效"),
        (404, "接口地址或模型名不存在"),
        (429, "额度不足或限流"),
    ],
)
def test_failure_kinds_are_labelled(session, provider, monkeypatch, code, expected):
    _bind_model(session, provider, "m")
    _service_with(monkeypatch, _status(code, f"服务商说的原话 {code}"))

    result = provider_service.test_connection(session, provider.id)

    assert result["ok"] is False
    assert expected in result["message"]
    assert f"服务商说的原话 {code}" in result["message"]  # 原文必须带上


def test_network_failure_is_reported(session, provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _bind_model(session, provider, "m")
    _service_with(monkeypatch, handler)

    result = provider_service.test_connection(session, provider.id)
    assert result["ok"] is False
    assert "网络" in result["message"] or "调用失败" in result["message"]


def test_missing_base_url_is_reported(session, monkeypatch):
    p = Provider(name="没地址", kind="custom", base_url="", enabled=True)
    session.add(p)
    session.commit()
    assert provider_service.test_connection(session, p.id)["ok"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provider_service.py -v`
Expected: FAIL —— 多条（空模型名仍发请求、错误分类不分 400/404）

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/provider_service.py`：替换 `test_connection` 与 `_sync_probe`，并加两个映射表与一个查找函数。

顶部导入区补上：

```python
from app.db.models import AgentVersion
from app.runtime.llm import ChatConfig, ChatFailure, HttpxChatClient
```

（`AgentVersion` 与 `ChatFailure` 是新增的导入。）

```python
# 按 HTTP 状态码给判定，比按 error.kind 分得更细：
# 404 与 400 在 kind 上都是 bad_request，但对作者的含义完全不同。
_STATUS_LABELS = {
    400: "请求被拒",
    401: "密钥无效",
    403: "密钥无效",
    404: "接口地址或模型名不存在",
    429: "额度不足或限流",
}

_KIND_LABELS = {
    "network": "网络不可达",
    "timeout": "请求超时",
    "auth": "密钥无效",
    "rate_limit": "额度不足或限流",
    "server": "服务商错误",
    "bad_request": "请求被拒",
}


def _first_bound_model(session: Session, provider_id: str) -> str | None:
    """找一个绑定到该服务商的模型名。

    角色卡没显式写 provider_id 时，运行时会回落到第一个启用的服务商 ——
    所以若全局只有一个启用的服务商，未指定归属的模型也算它的。
    """
    enabled_ids = [
        p.id for p in session.scalars(select(Provider).where(Provider.enabled.is_(True)))
    ]
    fallback_allowed = len(enabled_ids) == 1 and enabled_ids[0] == provider_id

    loose: str | None = None
    for version in session.scalars(select(AgentVersion)):
        binding = version.model_binding_json or {}
        model = binding.get("model")
        if not model:
            continue
        if binding.get("provider_id") == provider_id:
            return str(model)
        if fallback_allowed and binding.get("provider_id") is None:
            loose = loose or str(model)
    return loose


def test_connection(session: Session, provider_id: str, model: str | None = None) -> dict:
    """一键连通性测试。

    必须带一个模型名：用空模型名发请求只能证明地址可达，任何 400/401/404
    都会被当成「连接正常」，是假阳性的根源。
    """
    provider = session.get(Provider, provider_id)
    if provider is None:
        return {"ok": False, "message": f"服务商不存在：{provider_id}"}
    if not provider.base_url:
        return {"ok": False, "message": "尚未填写接口地址"}

    target_model = model or _first_bound_model(session, provider_id)
    if not target_model:
        return {
            "ok": False,
            "message": "请先为某个智能体绑定模型，或在此填写测试用模型",
        }

    api_key = dpapi.get_secret(provider.api_key_ref) if provider.api_key_ref else ""
    timeout = float(config.load_settings().get("request_timeout_seconds", 300))
    client = HttpxChatClient(timeout=timeout)
    chat_config = ChatConfig(base_url=provider.base_url, api_key=api_key or "", model=target_model)

    try:
        _sync_probe(client, chat_config)
    except ChatFailure as exc:
        label = _STATUS_LABELS.get(exc.error.status or 0) or _KIND_LABELS.get(
            exc.error.kind, "调用失败"
        )
        return {"ok": False, "message": f"{label}：{exc.error.message}"}
    except Exception as exc:  # noqa: BLE001 — 界面要看到原因而不是堆栈
        return {"ok": False, "message": f"调用失败：{exc}"}
    return {"ok": True, "message": f"连接正常，模型 {target_model} 可用"}
```

`_sync_probe` 改为让失败原样抛出（由 `test_connection` 分类）：

```python
def _sync_probe(client: HttpxChatClient, config: ChatConfig) -> None:
    import asyncio

    async def probe() -> None:
        # 极短的请求即可判定：密钥、地址、模型名任一处不对都会被服务商拒绝。
        await client.complete(config, [{"role": "user", "content": "ping"}], {"max_tokens": 1})

    asyncio.run(probe())
```

`provider_service.py` 顶部补一个导入 —— 该文件目前只导了 `dpapi` / `GenerationRun` / `Provider` / `ChatConfig` / `HttpxChatClient`，没有 `config`：

```python
from app import config
```

`backend/app/api/schemas.py` 末尾追加：

```python
class ProviderTest(BaseModel):
    model: str | None = None
```

`backend/app/api/providers.py`，把测试路由改为接受可选 body：

```python
@router.post("/providers/{provider_id}/test")
def test_provider(
    provider_id: str, payload: ProviderTest | None = None, session: Session = Depends(get_session)
) -> dict:
    return provider_service.test_connection(
        session, provider_id, model=payload.model if payload else None
    )
```

并把 `ProviderTest` 加进该文件顶部的 schemas 导入。

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_provider_service.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/provider_service.py backend/app/api/providers.py backend/app/api/schemas.py backend/tests/test_provider_service.py
git commit -m "fix(providers): 连通性测试必须带模型名，判定按状态码细分"
```

---

### Task 8: 前端接口封装与全局类型

**Files:**
- Modify: `frontend/src/api/client.ts`、`frontend/index.html`

**Interfaces:**
- Consumes: Task 6 的 `PATCH /api/agents/{id}` 与 `GET /api/slots`；Task 7 的 `POST /api/providers/{id}/test` 带 body
- Produces: `api.updateAgent`、`api.listSlots`、`api.updateProvider`、`api.deleteProvider`、`api.testProvider(id, model?)`；类型 `SlotSpec`、`Settings.request_timeout_seconds`

- [ ] **Step 1: 加接口与类型**

`frontend/src/api/client.ts`：在 `api` 对象里 `listAgents` 之后插入：

```ts
  updateAgent: (agentId: string, body: Record<string, unknown>) =>
    request<Agent>(`/api/agents/${agentId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  listSlots: () => request<SlotSpec[]>('/api/slots'),
```

把 `testProvider` 换成：

```ts
  testProvider: (id: string, model?: string) =>
    request<{ ok: boolean; message: string }>(`/api/providers/${id}/test`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ model: model ?? null }),
    }),
  updateProvider: (id: string, body: Record<string, unknown>) =>
    request<ProviderView>(`/api/providers/${id}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }),
  deleteProvider: (id: string) => request<void>(`/api/providers/${id}`, { method: 'DELETE' }),
```

在类型区末尾追加：

```ts
export interface SlotSpec {
  key: string
  label: string
  priority: number
  over_budget: 'never' | 'summarize' | 'drop'
}
```

并把 `Settings` 补一个字段：

```ts
export interface Settings {
  context_token_budget: number
  default_params: { temperature: number; max_tokens: number }
  model_routing: Record<string, string>
  budget_alert: number | null
  request_timeout_seconds: number
}
```

- [ ] **Step 2: 改 index.html**

`frontend/index.html`：

```html
<html lang="zh-CN">
```

```html
    <title>StoryForge</title>
```

- [ ] **Step 3: 验证构建**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/index.html
git commit -m "feat(frontend): 接口封装补齐智能体/槽位/服务商，修正页面标题"
```

---

### Task 9: 智能体工作室 —— 角色卡全字段与模型绑定

**Files:**
- Rewrite: `frontend/src/pages/Studio.tsx`

**Interfaces:**
- Consumes: `api.updateAgent`、`api.listSlots`、`api.createVersion`、`api.listProviders`、`SlotSpec`、`ProviderView`
- Produces: 无（叶子页面）

- [ ] **Step 1: 写页面**

把 `frontend/src/pages/Studio.tsx` 整体替换为：

```tsx
import { useEffect, useRef, useState } from 'react'
import {
  api,
  type Agent,
  type AgentVersion,
  type ProviderView,
  type RunView,
  type SlotSpec,
} from '../api/client'
import RunTrace from '../components/RunTrace'

const PARAM_PROFILES = [
  { value: 'strict', label: '严谨' },
  { value: 'balanced', label: '平衡' },
  { value: 'creative', label: '发散' },
]

const TRIGGER_MODES = [
  { value: 'manual', label: '手动' },
  { value: 'assist', label: '协同' },
  { value: 'auto', label: '自动' },
]

export default function Studio() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [providers, setProviders] = useState<ProviderView[]>([])
  const [slots, setSlots] = useState<SlotSpec[]>([])
  const [projectId, setProjectId] = useState('')
  const [selected, setSelected] = useState<Agent | null>(null)
  const [versions, setVersions] = useState<AgentVersion[]>([])
  const [run, setRun] = useState<RunView | null>(null)
  const [notice, setNotice] = useState('')

  const [draft, setDraft] = useState({
    name: '',
    roleLabel: '',
    color: '#6366f1',
    enabled: true,
    prompt: '',
    model: '',
    providerId: '',
    paramProfile: 'balanced',
    slots: [] as string[],
    schemaText: '',
    triggerMode: 'manual',
  })
  const [schemaError, setSchemaError] = useState('')

  useEffect(() => {
    api.listAgents().then(setAgents)
    api.listProviders().then(setProviders)
    api.listSlots().then(setSlots)
    api.listProjects().then((list) => {
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  // 重置草稿的时机：换智能体，或当前版本变了（保存了新版本 / 回滚）。
  // 不能只依赖 selected —— 保存 agent 级字段后 refreshAgents 会造出一个新的
  // selected 对象，若那时也整体重置，作者在提示词/模型里未保存的改动会被静默还原。
  const seededKey = useRef<string | null>(null)

  useEffect(() => {
    if (!selected) return

    const key = `${selected.id}:${selected.current_version?.id ?? ''}`
    if (seededKey.current === key) return
    const agentChanged = seededKey.current?.split(':')[0] !== selected.id
    seededKey.current = key

    const version = selected.current_version
    const binding = (version?.model_binding_json ?? {}) as Record<string, unknown>
    setDraft({
      name: selected.name,
      roleLabel: selected.role_label,
      color: selected.color,
      enabled: selected.enabled,
      prompt: version?.system_prompt ?? '',
      model: typeof binding.model === 'string' ? binding.model : '',
      providerId: typeof binding.provider_id === 'string' ? binding.provider_id : '',
      paramProfile: version?.param_profile ?? 'balanced',
      slots: version?.context_slots_json ?? [],
      schemaText: version?.output_schema_json
        ? JSON.stringify(version.output_schema_json, null, 2)
        : '',
      triggerMode: version?.trigger_mode ?? 'manual',
    })
    setSchemaError('')
    if (agentChanged) {
      setNotice('')
      setRun(null)
    }
    api.listVersions(selected.id).then(setVersions)
  }, [selected])

  async function refreshAgents(agentId?: string) {
    const list = await api.listAgents()
    setAgents(list)
    if (agentId) setSelected(list.find((a) => a.id === agentId) ?? null)
  }

  async function saveAgentFields() {
    if (!selected) return
    try {
      await api.updateAgent(selected.id, {
        name: draft.name,
        role_label: draft.roleLabel,
        color: draft.color,
        enabled: draft.enabled,
      })
      await refreshAgents(selected.id)
      setNotice('已更新角色卡基本信息（不产生新版本）')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveVersion() {
    if (!selected) return
    let schema: Record<string, unknown> | null = null
    if (draft.schemaText.trim()) {
      try {
        schema = JSON.parse(draft.schemaText)
      } catch {
        setSchemaError('输出契约不是合法 JSON')
        return
      }
    }
    setSchemaError('')

    const binding: Record<string, unknown> = {}
    if (draft.model.trim()) binding.model = draft.model.trim()
    if (draft.providerId) binding.provider_id = draft.providerId

    try {
      await api.createVersion(selected.id, {
        system_prompt: draft.prompt,
        model_binding_json: binding,
        param_profile: draft.paramProfile,
        context_slots_json: draft.slots,
        output_schema_json: schema,
        trigger_mode: draft.triggerMode,
        note: '手动编辑',
      })
      await refreshAgents(selected.id)
      setNotice('已保存为新版本')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function rollback(versionId: string) {
    if (!selected) return
    try {
      await api.rollback(selected.id, versionId)
      await refreshAgents(selected.id)
      setNotice('已回滚')
    } catch (error) {
      setNotice((error as Error).message)
    }
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

  function toggleSlot(key: string) {
    setDraft((prev) => ({
      ...prev,
      slots: prev.slots.includes(key)
        ? prev.slots.filter((k) => k !== key)
        : [...prev.slots, key],
    }))
  }

  function moveSlot(key: string, delta: number) {
    setDraft((prev) => {
      const index = prev.slots.indexOf(key)
      const next = index + delta
      if (index < 0 || next < 0 || next >= prev.slots.length) return prev
      const slots = [...prev.slots]
      ;[slots[index], slots[next]] = [slots[next], slots[index]]
      return { ...prev, slots }
    })
  }

  const currentVersionNo = selected?.current_version?.version_no

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
              } ${agent.enabled ? '' : 'opacity-50'}`}
            >
              <span className="mr-2 text-slate-400">{agent.role_label}</span>
              {agent.name}
              {!agent.enabled && <span className="ml-2 text-xs">（已停用）</span>}
            </button>
          ))}
        </nav>

        {selected ? (
          <div className="space-y-6">
            <div className="text-sm text-slate-400">
              任务类型：{selected.task_type} · 当前版本 v{currentVersionNo}
            </div>

            <section className="space-y-3 rounded border border-slate-800 p-4">
              <h3 className="text-sm font-medium text-slate-300">角色卡</h3>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <label className="text-slate-400">名称</label>
                <input
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
                <label className="text-slate-400">定位</label>
                <input
                  className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.roleLabel}
                  onChange={(e) => setDraft({ ...draft, roleLabel: e.target.value })}
                />
                <label className="text-slate-400">颜色</label>
                <input
                  type="color"
                  className="h-9 w-14 rounded border border-slate-700 bg-slate-900"
                  value={draft.color}
                  onChange={(e) => setDraft({ ...draft, color: e.target.value })}
                />
                <label className="flex items-center gap-2 text-slate-400">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                  />
                  启用
                </label>
                <button
                  className="rounded border border-slate-700 px-4 py-2 text-sm"
                  onClick={saveAgentFields}
                >
                  保存基本信息
                </button>
              </div>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4">
              <h3 className="text-sm font-medium text-slate-300">系统提示词</h3>
              <textarea
                className="h-56 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
                value={draft.prompt}
                onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
              />
              <p className="text-xs text-slate-500">
                字段的键名与含义由运行时按输出契约自动追加，提示词里不必再写一遍。
              </p>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
              <h3 className="text-sm font-medium text-slate-300">运行配置</h3>
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-slate-400">服务商</label>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.providerId}
                  onChange={(e) => setDraft({ ...draft, providerId: e.target.value })}
                >
                  <option value="">（自动：第一个启用的服务商）</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <label className="text-slate-400">模型</label>
                <input
                  className="w-64 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  placeholder="例如 qwen3.8-flash"
                  value={draft.model}
                  onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                />
                <label className="text-slate-400">参数档</label>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.paramProfile}
                  onChange={(e) => setDraft({ ...draft, paramProfile: e.target.value })}
                >
                  {PARAM_PROFILES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <label className="text-slate-400">触发方式</label>
                <select
                  className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                  value={draft.triggerMode}
                  onChange={(e) => setDraft({ ...draft, triggerMode: e.target.value })}
                >
                  {TRIGGER_MODES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-slate-500">
                模型名必须与服务商提供的一致，否则调用会失败。参数档目前只存不生效（属 P3）。
              </p>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
              <h3 className="text-sm font-medium text-slate-300">上下文槽位</h3>
              <div className="flex flex-wrap gap-2">
                {slots.map((slot) => {
                  const on = draft.slots.includes(slot.key)
                  return (
                    <button
                      key={slot.key}
                      onClick={() => toggleSlot(slot.key)}
                      className={`rounded border px-3 py-1 text-xs ${
                        on ? 'border-indigo-500 bg-slate-800' : 'border-slate-700'
                      }`}
                    >
                      {slot.label}
                      <span className="ml-1 font-mono text-[10px] text-slate-500">{slot.key}</span>
                    </button>
                  )
                })}
              </div>
              <ol className="space-y-1">
                {draft.slots.map((key, index) => (
                  <li key={key} className="flex items-center gap-3">
                    <span className="text-slate-500">{index + 1}.</span>
                    <span className="font-mono text-xs">{key}</span>
                    <button className="text-xs text-indigo-400" onClick={() => moveSlot(key, -1)}>
                      上移
                    </button>
                    <button className="text-xs text-indigo-400" onClick={() => moveSlot(key, 1)}>
                      下移
                    </button>
                  </li>
                ))}
                {draft.slots.length === 0 && (
                  <li className="text-xs text-slate-500">还没选槽位，这个智能体读不到任何上下文。</li>
                )}
              </ol>
            </section>

            <section className="space-y-3 rounded border border-slate-800 p-4">
              <h3 className="text-sm font-medium text-slate-300">输出契约（JSON）</h3>
              <textarea
                className="h-52 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs"
                value={draft.schemaText}
                onChange={(e) => setDraft({ ...draft, schemaText: e.target.value })}
                placeholder={'留空表示不做结构化校验，例如：\n{\n  "type": "object",\n  "properties": {"genre": {"type": "string", "title": "题材"}}\n}'}
              />
              {schemaError && <p className="text-xs text-amber-400">{schemaError}</p>}
              <p className="text-xs text-slate-500">
                属性上的 title 是字段的中文名，渲染时用来给模型生成字段说明 —— 改契约即改提示词。
              </p>
            </section>

            <div className="flex items-center gap-2">
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

            <section className="text-sm">
              <h3 className="mb-2 font-medium text-slate-300">版本历史</h3>
              <ul className="space-y-1">
                {versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-3">
                    <span className="text-slate-400">v{v.version_no}</span>
                    {v.version_no === currentVersionNo && (
                      <span className="text-xs text-emerald-400">当前</span>
                    )}
                    <span className="text-slate-500">{v.note || '—'}</span>
                    {v.version_no !== currentVersionNo && (
                      <button className="text-xs text-indigo-400" onClick={() => rollback(v.id)}>
                        回滚到此版本
                      </button>
                    )}
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

- [ ] **Step 2: 验证构建与手工走查**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

手工走查（后端与前端都在跑）：
1. 打开 `http://127.0.0.1:5173/studio`，能看到两个智能体。
2. 选中「灵感解析师」，确认名称/定位/颜色/启用、系统提示词、服务商下拉、模型输入框、参数档、触发方式、槽位勾选与排序、输出契约文本域**全部出现**。
3. 把输出契约改成非法 JSON，点「保存为新版本」→ 应提示「输出契约不是合法 JSON」且不新建版本。
4. 改回合法 JSON，点保存 → 版本历史多一条 vN+1，旧版本「回滚到此版本」按钮仍在。
5. 「当前」标记只出现在当前版本上，当前版本没有回滚按钮。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Studio.tsx
git commit -m "feat(studio): 角色卡全字段编辑与模型绑定"
```

---

### Task 10: 架构页 —— 故事圣经可编辑与 L1 手动录入

**Files:**
- Rewrite: `frontend/src/pages/Architecture.tsx`

**Interfaces:**
- Consumes: `api.getArchitecture`、`api.recommendArchitecture`、`api.adoptArchitecture`、`AdoptPayload`
- Produces: 无（叶子页面）

- [ ] **Step 1: 写页面**

把 `frontend/src/pages/Architecture.tsx` 整体替换为：

```tsx
import { useEffect, useState } from 'react'
import {
  api,
  type Act,
  type AdoptPayload,
  type ArchitectureOption,
  type Project,
  type RecommendResponse,
} from '../api/client'
import RunTrace from '../components/RunTrace'

interface DraftAct {
  seq: number
  name: string
  purpose: string
  target_word_ratio: string
}

const EMPTY_DRAFT = { logline: '', theme: '', premise: '', ending_direction: '' }

function actsFromBible(bible: { acts?: { name: string; purpose?: string; target_word_ratio?: number }[] }): DraftAct[] {
  return (bible.acts ?? []).map((act, index) => ({
    seq: index + 1,
    name: act.name,
    purpose: act.purpose ?? '',
    target_word_ratio: act.target_word_ratio == null ? '' : String(act.target_word_ratio),
  }))
}

export default function Architecture() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [recommendation, setRecommendation] = useState<RecommendResponse | null>(null)
  const [chosen, setChosen] = useState<ArchitectureOption | null>(null)
  const [savedActs, setSavedActs] = useState<Act[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [draftActs, setDraftActs] = useState<DraftAct[]>([])
  const [manual, setManual] = useState(false)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!projectId) return
    api.getArchitecture(projectId).then((data) => setSavedActs(data.acts))
    setRecommendation(null)
    setChosen(null)
    setManual(false)
    setDraft(EMPTY_DRAFT)
    setDraftActs([])
  }, [projectId])

  async function recommend() {
    setBusy(true)
    setMessage('')
    try {
      const result = await api.recommendArchitecture(projectId)
      setRecommendation(result)
      if (result.structured) {
        const bible = result.story_bible_v0
        setDraft({
          logline: bible.logline ?? '',
          theme: bible.theme ?? '',
          premise: bible.premise ?? '',
          ending_direction: bible.ending_direction ?? '',
        })
        setDraftActs(actsFromBible(bible))
      }
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startManual() {
    setManual(true)
    setRecommendation(null)
    setChosen(null)
    setMessage('')
    setDraft(EMPTY_DRAFT)
    setDraftActs([{ seq: 1, name: '', purpose: '', target_word_ratio: '' }])
  }

  function updateAct(index: number, patch: Partial<DraftAct>) {
    setDraftActs((prev) => prev.map((act, i) => (i === index ? { ...act, ...patch } : act)))
  }

  function addAct() {
    setDraftActs((prev) => [
      ...prev,
      { seq: prev.length + 1, name: '', purpose: '', target_word_ratio: '' },
    ])
  }

  function removeAct(index: number) {
    setDraftActs((prev) =>
      prev.filter((_, i) => i !== index).map((act, i) => ({ ...act, seq: i + 1 })),
    )
  }

  async function adopt() {
    const useManual = manual || !recommendation
    if (!useManual && !chosen) return

    const acts = draftActs
      .filter((act) => act.name.trim())
      .map((act, index) => ({
        seq: index + 1,
        name: act.name.trim(),
        purpose: act.purpose.trim() || undefined,
        target_word_ratio: act.target_word_ratio.trim()
          ? Number(act.target_word_ratio)
          : undefined,
      }))
    if (acts.length === 0) {
      setMessage('至少填一幕。')
      return
    }

    const payload: AdoptPayload = {
      tool_ref: chosen?.tool,
      logline: draft.logline.trim() || undefined,
      theme: draft.theme.trim() || undefined,
      premise: draft.premise.trim() || undefined,
      ending_direction: draft.ending_direction.trim() || undefined,
      acts,
    }

    try {
      const saved = await api.adoptArchitecture(projectId, payload)
      setSavedActs(saved.acts)
      setMessage('已写入项目结构')
    } catch (error) {
      setMessage((error as Error).message)
    }
  }

  const showEditor = manual || (recommendation?.structured ?? false)

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">架构推荐</h2>

      <div className="flex flex-wrap items-center gap-3">
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
        <button
          className="rounded border border-slate-700 px-4 py-2 text-sm disabled:opacity-50"
          onClick={startManual}
          disabled={!projectId}
        >
          手工建立故事圣经
        </button>
        {message && <span className="text-sm text-slate-400">{message}</span>}
      </div>

      {!showEditor && !savedActs.length && (
        <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
          还没有结构。点「推荐结构」让架构师给 2–3 套方案，或者点「手工建立故事圣经」自己写 ——
          手动档下 AI 不参与。
        </p>
      )}

      {recommendation && !recommendation.structured && (
        <div className="rounded bg-amber-950/40 p-3 text-sm text-amber-300">
          未结构化：{recommendation.parse_error}
          <pre className="mt-2 whitespace-pre-wrap text-xs">{recommendation.raw_text}</pre>
        </div>
      )}

      {recommendation?.structured && (
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
      )}

      {showEditor && (
        <section className="space-y-3 rounded border border-slate-800 p-4 text-sm">
          <h3 className="text-sm font-medium text-slate-300">
            故事圣经 v0{manual ? '（手工）' : '（可编辑，采纳的是你改过的版本）'}
          </h3>

          <label className="block">
            <span className="text-slate-500">logline</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.logline}
              onChange={(e) => setDraft({ ...draft, logline: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-slate-500">主题句</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.theme}
              onChange={(e) => setDraft({ ...draft, theme: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-slate-500">前提</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.premise}
              onChange={(e) => setDraft({ ...draft, premise: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-slate-500">结局方向</span>
            <textarea
              className="mt-1 h-20 w-full rounded border border-slate-700 bg-slate-900 p-3 text-sm"
              value={draft.ending_direction}
              onChange={(e) => setDraft({ ...draft, ending_direction: e.target.value })}
            />
          </label>

          <div>
            <div className="mb-2 flex items-center gap-3">
              <span className="text-slate-500">幕骨架</span>
              <button className="text-xs text-indigo-400" onClick={addAct}>
                加一幕
              </button>
            </div>
            <ul className="space-y-2">
              {draftActs.map((act, index) => (
                <li key={index} className="flex flex-wrap items-center gap-2">
                  <input
                    className="w-52 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    placeholder="幕名"
                    value={act.name}
                    onChange={(e) => updateAct(index, { name: e.target.value })}
                  />
                  <input
                    className="min-w-[240px] flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    placeholder="这一幕要做什么"
                    value={act.purpose}
                    onChange={(e) => updateAct(index, { purpose: e.target.value })}
                  />
                  <input
                    className="w-24 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    placeholder="占比"
                    value={act.target_word_ratio}
                    onChange={(e) => updateAct(index, { target_word_ratio: e.target.value })}
                  />
                  <button className="text-xs text-amber-400" onClick={() => removeAct(index)}>
                    删除
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <button
            className="rounded bg-emerald-700 px-4 py-2 text-sm disabled:opacity-50"
            onClick={adopt}
            disabled={!manual && !chosen}
          >
            采纳并写入项目
          </button>
          {!manual && !chosen && (
            <p className="text-xs text-slate-500">先在上面选一套方案，再采纳。</p>
          )}
        </section>
      )}

      {savedActs.length > 0 && (
        <section className="rounded border border-slate-800 p-4 text-sm">
          <h3 className="mb-2 text-sm font-medium text-slate-300">已写入的结构</h3>
          <ul className="list-disc space-y-1 pl-5">
            {savedActs.map((act) => (
              <li key={act.id}>
                第{act.seq}幕 {act.name}
                {act.purpose ? ` —— ${act.purpose}` : ''}
                {act.target_word_ratio != null ? `（占比 ${act.target_word_ratio}）` : ''}
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

- [ ] **Step 2: 验证构建与手工走查**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

手工走查：
1. 打开 `http://127.0.0.1:5173/architecture`，**空项目应看到空态文案**（此前是一片空白）。
2. 点「手工建立故事圣经」→ 出现空表单，填 logline 与一幕，点「采纳并写入项目」→「已写入的结构」出现该幕。**这一步不需要模型。**
3. 点「推荐结构」→ 出方案后选一套 → 表单**预填了模型的产出且可编辑**；改一改再采纳，确认「已写入的结构」是**改后的值**。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Architecture.tsx
git commit -m "feat(architecture): 故事圣经可编辑，加 L1 手动录入与空态"
```

---

### Task 11: 模型与费用页 —— 服务商改删、超时设置

**Files:**
- Modify: `frontend/src/pages/Models.tsx`

**Interfaces:**
- Consumes: `api.updateProvider`、`api.deleteProvider`、`api.testProvider(id, model?)`、`Settings.request_timeout_seconds`
- Produces: 无（叶子页面）

- [ ] **Step 1: 改页面**

`frontend/src/pages/Models.tsx`：

在 `useEffect` 的加载块之后，`addProvider` 之前插入编辑状态与方法：

```tsx
  const [editing, setEditing] = useState<{ id: string; name: string; base_url: string; api_key: string; enabled: boolean } | null>(null)
  const [testModel, setTestModel] = useState('')
```

把 `test` 换成：

```tsx
  async function test(id: string) {
    try {
      const result = await api.testProvider(id, testModel.trim() || undefined)
      setNotice(`${result.ok ? '正常' : '失败'}：${result.message}`)
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveProvider() {
    if (!editing) return
    try {
      const updated = await api.updateProvider(editing.id, {
        name: editing.name.trim(),
        base_url: editing.base_url.trim(),
        ...(editing.api_key ? { api_key: editing.api_key } : {}),
        enabled: editing.enabled,
      })
      setProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      setEditing(null)
      setNotice('已保存。密钥留空表示不修改。')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function removeProvider(id: string) {
    try {
      await api.deleteProvider(id)
      setProviders((prev) => prev.filter((p) => p.id !== id))
      setNotice('已删除')
    } catch (error) {
      setNotice((error as Error).message)
    }
  }

  async function saveTimeout(value: number) {
    if (!settings) return
    try {
      setSettings(await api.updateSettings({ request_timeout_seconds: value }))
    } catch (error) {
      setNotice((error as Error).message)
    }
  }
```

把服务商列表那一整段 `<ul className="space-y-2 text-sm"> ... </ul>` 换成：

```tsx
        <ul className="space-y-2 text-sm">
          {providers.map((p) => (
            <li key={p.id} className="space-y-2 border-b border-slate-800 pb-2 last:border-0">
              <div className="flex flex-wrap items-center gap-4">
                <span className="w-32">{p.name}</span>
                <span className="w-64 truncate text-slate-500">{p.base_url}</span>
                <span className="font-mono text-xs text-slate-500">{p.api_key_masked || '未设密钥'}</span>
                {!p.enabled && <span className="text-xs text-amber-400">已停用</span>}
                <button className="text-xs text-indigo-400" onClick={() => test(p.id)}>
                  测试连通性
                </button>
                <button
                  className="text-xs text-indigo-400"
                  onClick={() =>
                    setEditing({
                      id: p.id,
                      name: p.name,
                      base_url: p.base_url,
                      api_key: '',
                      enabled: p.enabled,
                    })
                  }
                >
                  编辑
                </button>
                <button className="text-xs text-amber-400" onClick={() => removeProvider(p.id)}>
                  删除
                </button>
              </div>

              {editing?.id === p.id && (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    value={editing.name}
                    onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  />
                  <input
                    className="w-80 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    value={editing.base_url}
                    onChange={(e) => setEditing({ ...editing, base_url: e.target.value })}
                  />
                  <input
                    className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                    type="password"
                    placeholder="密钥（留空不修改）"
                    value={editing.api_key}
                    onChange={(e) => setEditing({ ...editing, api_key: e.target.value })}
                  />
                  <label className="flex items-center gap-2 text-slate-400">
                    <input
                      type="checkbox"
                      checked={editing.enabled}
                      onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })}
                    />
                    启用
                  </label>
                  <button className="rounded bg-indigo-600 px-4 py-2 text-sm" onClick={saveProvider}>
                    保存
                  </button>
                  <button
                    className="rounded border border-slate-700 px-4 py-2 text-sm"
                    onClick={() => setEditing(null)}
                  >
                    取消
                  </button>
                </div>
              )}
            </li>
          ))}
          {providers.length === 0 && <li className="text-slate-500">还没配置服务商。</li>}
        </ul>
        <div className="flex items-center gap-3 text-sm">
          <label className="text-slate-400">测试用模型</label>
          <input
            className="w-64 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="留空则用已绑定的模型"
            value={testModel}
            onChange={(e) => setTestModel(e.target.value)}
          />
          <span className="text-slate-500">
            连通性测试必须带模型名 —— 空模型名的「通过」只证明地址可达。
          </span>
        </div>
```

在「上下文预算」那一节之后，加一节超时设置：

```tsx
      <section className="space-y-2 rounded border border-slate-800 p-4 text-sm">
        <h3 className="text-sm font-medium text-slate-300">请求超时</h3>
        <div className="flex items-center gap-3">
          <input
            type="number"
            className="w-32 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={settings?.request_timeout_seconds ?? 300}
            onChange={(e) => saveTimeout(Number(e.target.value))}
          />
          <span className="text-slate-500">
            秒。重推理模型在长任务上可能跑两分钟以上，调大可避免半途被掐断。
          </span>
        </div>
      </section>
```

- [ ] **Step 2: 验证构建与手工走查**

Run: `cd frontend && pnpm build`
Expected: 无 TypeScript 报错

手工走查：
1. 「模型与费用」页：在「测试用模型」里填一个**不存在的**模型名 → 点「测试连通性」→ 应显示**失败**（此前会显示「正常」，这是假阳性）。
2. 清空该输入框，若已有智能体绑定了模型 → 测试应显示「连接正常，模型 X 可用」。
3. 点「编辑」改名称 → 保存 → 列表里名字变了，密钥仍显示屏蔽态。
4. 改「请求超时」为 600 → 刷新页面后仍是 600。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Models.tsx
git commit -m "feat(models): 服务商改删、超时设置、连通性测试带模型名"
```

---

### Task 12: 真实模型端到端复验

**Files:** 无（验收任务）

**Interfaces:**
- Consumes: 前 11 个任务的全部产出
- Produces: 一份复验结论（写回 `CLAUDE.md` §7 与发现记录）

**前提**：真实服务商已配置（阿里云百炼），且**每次调用都要值回票价** —— 免费额度用完即停。

- [ ] **Step 1: 重建开发库并重启后端**

预置阵容的契约与提示词都变了，而 `seed_agents` 是幂等的（已存在即跳过），旧库里的角色卡不会更新。

```bash
# 停掉后端，备份旧库
mv "$LOCALAPPDATA/StoryForge/storyforge.db" "$LOCALAPPDATA/StoryForge/backup-pre-hardening.db"
# 重新起后端（会在空目录里建表并预置）
cd backend && uv run uvicorn app.main:app --port 8756
```

- [ ] **Step 2: 走 P1a 验收 §1.2 的七步**

在浏览器 `http://127.0.0.1:5173`：

1. 新建项目。
2. 「模型与费用」录入服务商，填测试用模型，点测试连通性 → **必须显示「连接正常，模型 X 可用」**。
3. 「智能体工作室」为**灵感解析师**绑定模型（如 `qwen3.8-flash`）、为**架构师**绑定一个（如 `qwen3.8-max-0902`），各保存为新版本。
4. 「灵感与解析」录入原话、存为灵感、点解析 → 解析卡**渲染为可逐项编辑的字段**（不是「未结构化」）。核对原话一字未变。
5. 调试台展开「渲染后的完整提示词」→ **末尾应有【输出契约】块**，且内容与落库的提示词一致。
6. 「架构推荐」点推荐结构 → **这次不应超时**（若仍超时，把「请求超时」调到 600 再试一次，并记录实际耗时）。
7. 选一套方案 → 编辑 logline 与第一幕的幕名 → 采纳 → 「已写入的结构」显示的是**改后的值**。

- [ ] **Step 3: 记录结论**

把复验结果写进 `CLAUDE.md` §7 的阶段记录（新增一条），包含：每次真实调用的耗时与 token、是否出现「未结构化」、发现的新问题。若七步全过，把 §7 路线图的 P1a 状态改为「✅ 完成」。

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/plans/2026-10-14-real-model-verification-findings.md
git commit -m "docs: P1a 收口复验结论"
```

---

## 附：本计划明确不做的事

- **数据迁移框架**（`create_all` 改不了已有表）—— 另起薄切片。本切片 Task 12 Step 1 用「重建开发库」绕过。
- **SQLite FTS5 全文检索** —— 仍按 `CLAUDE.md` §7 在 P1b 之前单独做。
- **流式改造** —— 见 spec §3.2，建议留给 P2（现在做会让 token 与费用退化为估算）。若作者要求现在做，需先花一两次调用验证百炼的 `stream_options` 支持。
- **参数档生效、费用单价配置** —— 仍属 P3。
- **杂交方案标注** —— 需要先定「杂交」在数据上怎么表达，属设计问题。
- **灵感页的两处文案**（「未结构化：」前缀、解析按钮禁用无说明）—— 不在本切片改动的文件里，另行处理。
