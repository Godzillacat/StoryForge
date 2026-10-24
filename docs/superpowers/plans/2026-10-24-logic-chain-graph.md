# 逻辑链图形化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在写作台「逻辑链」面板里加一个段落轨道图，把已有的因果 / 转折 / 揭示命中按段落铺开，文本列表保留。

**Architecture:** 后端只补一个 `paragraphs` 字段（与 `extract_chain` 共用分段函数）；前端把布局算成纯函数（vitest 覆盖），SVG 手写渲染，`LogicChain.tsx` 加「图形 / 文本」开关，两种模式共用同一次请求。

**Tech Stack:** FastAPI + pytest；React + TypeScript + 手写 SVG + vitest。

**Spec:** `docs/superpowers/specs/2026-10-24-logic-chain-graph-design.md`

## Global Constraints

- 不引入图表库、图形引擎或任何新依赖。
- 规则不动：`extract_chain` 的行为、连接词表、类型优先级一律不改。
- 图形**只表达出现顺序**，不表达指代；图形模式必须显示这句话。
- 颜色取 sky / amber / emerald 深色带值，深色底 `#020617` 上对比度 ≥ 3:1，实测值写进注释。
- 界面文案、注释用中文；标识符用英文。
- UI 不写自动化测试；纯逻辑必须有 vitest / pytest。

## Review Focus

1. **段落很多（40+）**：横向滚动必须出现，节点不能重叠，高度随最多的一列增长。
2. **一段里命中很多（8+）**：列内不折叠，总高跟着长。
3. **`paragraphs` 与命中段不一致**（服务端给 0、命中却在第 5 段）：以命中段为准，不丢节点。
4. **空正文 / 零命中**：不画空图，显示原有 `reason`。
5. **超长句子 / 含 `<` `>` 的句子**：节点内截断加省略号，全文进 `<title>`，React 负责转义。

## File Structure

- Modify `backend/app/logic_chain.py` — 加 `count_paragraphs`（与 `extract_chain` 共用 `_PARA_SPLIT`）
- Modify `backend/app/services/logic_service.py:275-294` — 响应加 `paragraphs`
- Modify `backend/tests/test_logic_chain.py`、`backend/tests/test_logic_api.py` — 口径与字段
- Create `frontend/src/lib/logicChainGraph.ts` — 布局 + 截断纯函数 + 几何常量
- Create `frontend/src/lib/logicChainGraph.test.ts`
- Create `frontend/src/components/writing/LogicChainGraph.tsx` — SVG 渲染
- Modify `frontend/src/components/writing/LogicChain.tsx` — 开关、空态、图/文共用数据
- Modify `frontend/src/api/client.ts:866-878` — 类型加 `paragraphs`

---

### Task 1: 后端补 `paragraphs`

**Files:**
- Modify: `backend/app/logic_chain.py`
- Modify: `backend/app/services/logic_service.py:275-294`
- Test: `backend/tests/test_logic_chain.py`、`backend/tests/test_logic_api.py`

**Interfaces:**
- Produces: `count_paragraphs(text: str | None) -> int`；`GET /api/scenes/{id}/logic-chain` 响应多一个 `paragraphs: int`

- [ ] **Step 1: 写失败的测试**

在 `backend/tests/test_logic_chain.py` 追加：

```python
def test_count_paragraphs_ignores_blank_runs():
    from app.logic_chain import count_paragraphs
    assert count_paragraphs("第一段。\n\n\n第二段。\n\n   \n第三段。") == 3
    assert count_paragraphs("") == 0
    assert count_paragraphs(None) == 0


def test_count_paragraphs_agrees_with_extract_chain():
    from app.logic_chain import count_paragraphs, extract_chain
    text = "开头。\n\n因为下雨，他留下。\n\n\n结尾。"
    chain = extract_chain(text)
    assert count_paragraphs(text) == 3
    assert max(item["paragraph"] for item in chain) <= count_paragraphs(text)
```

在 `backend/tests/test_logic_api.py` 追加（沿用该文件里已有的建场景夹具写法）：

```python
def test_logic_chain_reports_paragraph_count(client):
    scene_id = _scene_with_body(client, "第一段。\n\n因为下雨，他留下。\n\n第三段。")
    data = client.get(f"/api/scenes/{scene_id}/logic-chain").json()
    assert data["paragraphs"] == 3
    assert data["chain"][0]["paragraph"] == 2


def test_logic_chain_paragraph_count_is_zero_without_body(client):
    scene_id = _scene_with_body(client, "")
    data = client.get(f"/api/scenes/{scene_id}/logic-chain").json()
    assert data["paragraphs"] == 0
```

> 若 `test_logic_api.py` 里没有 `_scene_with_body` 辅助，用同文件已有的建场景 + 写正文步骤替代，不要新造夹具。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend; uv run pytest tests/test_logic_chain.py tests/test_logic_api.py -q`
Expected: FAIL —— `count_paragraphs` 不存在 / `KeyError: 'paragraphs'`

- [ ] **Step 3: 实现**

`logic_chain.py` 加：

```python
def count_paragraphs(text: str | None) -> int:
    """正文的**非空段落数**，与 `extract_chain` 用同一个分段函数。

    图形视图的横轴要覆盖整段正文：只靠命中句的段落号推，会截掉最后一个
    命中段之后的所有段，「结尾几段一条都没有」这个信号就没了。
    """
    if not text:
        return 0
    return sum(1 for paragraph in _PARA_SPLIT.split(text) if paragraph.strip())
```

`logic_service.logic_chain` 的两个 return 都加 `"paragraphs": count_paragraphs(body)`（空正文时 `body` 是 `""`，自然得 0）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend; uv run pytest tests/test_logic_chain.py tests/test_logic_api.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/logic_chain.py backend/app/services/logic_service.py backend/tests/test_logic_chain.py backend/tests/test_logic_api.py
git commit -m "feat: 逻辑链接口补 paragraphs（非空段落数）"
```

---

### Task 2: 布局纯函数

**Files:**
- Create: `frontend/src/lib/logicChainGraph.ts`
- Test: `frontend/src/lib/logicChainGraph.test.ts`

**Interfaces:**
- Consumes: `LogicChainItem`（`api/client.ts` 已有）
- Produces: 常量 `NODE_WIDTH=168`、`NODE_HEIGHT=52`、`COLUMN_WIDTH=192`、`ROW_GAP=12`、`PAD_LEFT=16`、`PAD_TOP=24`、`PAD_BOTTOM=28`；类型 `GraphNode { index, paragraph, sentence, kind, kindLabel, marker, x, y, width, height }`、`GraphEdge { from, to, kind }`、`GraphColumn { paragraph, nodes }`、`LogicChainGraph { columns, nodes, edges, width, height, maxRows }`；函数 `buildLogicChainGraph(chain, paragraphs): LogicChainGraph`、`shortenSentence(text: string, max = 22): string`

- [ ] **Step 1: 写失败的测试**

```ts
import { describe, expect, it } from 'vitest'
import type { LogicChainItem } from '../api/client'
import {
  buildLogicChainGraph, shortenSentence, NODE_WIDTH, NODE_HEIGHT, COLUMN_WIDTH, PAD_LEFT, PAD_TOP,
} from './logicChainGraph'

function hit(paragraph: number, kind = 'cause', sentence = '因为下雨，他留下。'): LogicChainItem {
  return { paragraph, sentence, kind, kind_label: kind, marker: '因为' }
}

it('keeps empty paragraphs as columns', () => {
  const graph = buildLogicChainGraph([hit(1), hit(3)], 3)
  expect(graph.columns.map((c) => c.paragraph)).toEqual([1, 2, 3])
  expect(graph.columns[1].nodes).toEqual([])
})

it('stacks nodes top-down inside a column and numbers them flat', () => {
  const graph = buildLogicChainGraph([hit(1), hit(1), hit(2)], 2)
  expect(graph.columns[0].nodes.map((n) => n.index)).toEqual([0, 1])
  expect(graph.columns[0].nodes[0].y).toBe(PAD_TOP)
  expect(graph.columns[0].nodes[1].y).toBe(PAD_TOP + NODE_HEIGHT + 12)
  expect(graph.columns[1].nodes[0].x).toBe(PAD_LEFT + COLUMN_WIDTH)
})

it('links consecutive hits with edges coloured by the target kind', () => {
  const graph = buildLogicChainGraph([hit(1), hit(2, 'turn'), hit(3, 'reveal')], 3)
  expect(graph.edges).toEqual([
    { from: 0, to: 1, kind: 'turn' },
    { from: 1, to: 2, kind: 'reveal' },
  ])
})

it('draws no edge for a single hit', () => {
  expect(buildLogicChainGraph([hit(2)], 2).edges).toEqual([])
})

it('trusts the hits when paragraphs under-reports', () => {
  const graph = buildLogicChainGraph([hit(5)], 0)
  expect(graph.columns).toHaveLength(5)
  expect(graph.nodes).toHaveLength(1)
})

it('returns an empty graph when nothing matched', () => {
  const graph = buildLogicChainGraph([], 4)
  expect(graph).toEqual({ columns: [], nodes: [], edges: [], width: 0, height: 0, maxRows: 0 })
})

it('grows in both directions', () => {
  const tall = buildLogicChainGraph([hit(1), hit(1), hit(1), hit(2)], 2)
  expect(tall.maxRows).toBe(3)
  expect(tall.height).toBeGreaterThan(buildLogicChainGraph([hit(1), hit(2)], 2).height)
  const wide = buildLogicChainGraph([hit(1), hit(9)], 9)
  expect(wide.width).toBeGreaterThan(buildLogicChainGraph([hit(1), hit(2)], 2).width)
})

it('shortens long sentences and leaves short ones alone', () => {
  expect(shortenSentence('短句。')).toBe('短句。')
  expect(shortenSentence('一'.repeat(40))).toBe('一'.repeat(22) + '…')
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend; pnpm vitest run src/lib/logicChainGraph.test.ts`
Expected: FAIL —— 模块不存在

- [ ] **Step 3: 实现 `frontend/src/lib/logicChainGraph.ts`**

要点：列数取 `Math.max(paragraphs, 最大命中段)`；`x = PAD_LEFT + (p-1)*COLUMN_WIDTH`；
`y = PAD_TOP + row*(NODE_HEIGHT+ROW_GAP)`；`width = PAD_LEFT*2 + (n-1)*COLUMN_WIDTH + NODE_WIDTH`；
`height = PAD_TOP + maxRows*(NODE_HEIGHT+ROW_GAP) - ROW_GAP + PAD_BOTTOM`；`chain` 为空时返回全零图。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend; pnpm vitest run src/lib/logicChainGraph.test.ts`
Expected: PASS（8 条）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/lib/logicChainGraph.ts frontend/src/lib/logicChainGraph.test.ts
git commit -m "feat: 逻辑链图形布局纯函数"
```

---

### Task 3: SVG 组件

**Files:**
- Create: `frontend/src/components/writing/LogicChainGraph.tsx`

**Interfaces:**
- Consumes: `buildLogicChainGraph` 及其常量/类型；`LogicChainItem[]`
- Produces: `export default function LogicChainGraph({ chain, paragraphs }: { chain: LogicChainItem[]; paragraphs: number })`

- [ ] **Step 1: 实现组件**

结构：外层 `div.overflow-x-auto.rounded.border`；`svg width={graph.width} height={graph.height} role="img" aria-label="逻辑链"`；
先画 `edges`（三次贝塞尔，`stroke={color(kind)}`、`opacity=0.45`、`fill="none"`），再画 `nodes`
（`<rect rx=6>` + 两行 `<text>`：类型标签 / `shortenSentence`），每个节点带 `<title>` 放
「¶段落 · 全文 · 连接词」；底部每个列画 `¶n` 刻度。

颜色常量与注释（实施时用实测值）：

```tsx
// 深色底 #020617 上实测（WCAG 相对亮度公式）：sky-500 7.28:1、amber-500 9.39:1、
// emerald-500 7.95:1 —— 三者都 ≥ 4.5:1，正文级文字也够用。
const COLORS: Record<string, string> = { cause: '#0ea5e9', turn: '#f59e0b', reveal: '#10b981' }
```

空 `chain` 返回 `null`（空态由父组件负责）。

- [ ] **Step 2: 类型检查**

Run: `cd frontend; pnpm exec tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/writing/LogicChainGraph.tsx
git commit -m "feat: 逻辑链段落轨道图（手写 SVG）"
```

---

### Task 4: 接进面板

**Files:**
- Modify: `frontend/src/components/writing/LogicChain.tsx`
- Modify: `frontend/src/api/client.ts:866-878`

**Interfaces:**
- Consumes: `LogicChainGraph`、`LogicChainResponse.paragraphs`
- Produces: 面板内的 `mode: 'graph' | 'text'` 状态（默认 `'graph'`）

- [ ] **Step 1: 类型加字段**

`LogicChainResponse` 加 `paragraphs: number`。

- [ ] **Step 2: 改面板**

- 头部右侧两个按钮：`图形` / `文本`，当前模式高亮（`bg-slate-800 text-slate-200`），点击只改 `mode`，**不发请求**。
- `mode === 'graph'` 且 `data.chain.length > 0`：渲染 `<LogicChainGraph chain={data.chain} paragraphs={data.paragraphs} />`，并在图上方显示一句「按出现顺序相连，不代表句子真的指向哪一句。」
- 其余情况保持现有文本列表与空态文案不变。
- 切换不清空 `data`。

- [ ] **Step 3: 构建**

Run: `cd frontend; pnpm build`
Expected: 干净

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/writing/LogicChain.tsx frontend/src/api/client.ts
git commit -m "feat: 逻辑链面板加图形/文本开关"
```

---

### Task 5: 全量验证

- [ ] **Step 1: 后端**

Run: `cd backend; uv run pytest -q`（需 `UV_CACHE_DIR` 指向可写目录）
Expected: 999 + 新增条数全过

- [ ] **Step 2: 前端**

Run: `cd frontend; pnpm vitest run`
Expected: 71 + 8 全过

- [ ] **Step 3: 构建**

Run: `cd frontend; pnpm build`
Expected: 干净

---

### Task 6: 浏览器走查

用临时数据目录起服务（`STORYFORGE_DATA_DIR` 指到临时目录），造一场有正文的场景：

1. 图形默认打开，段落列与节点位置正确；
2. 点「文本」回到列表，内容一致；再点「图形」，**Network 面板没有新请求**；
3. 悬停节点能看到全文与连接词；
4. 换到一场没有正文的场景，显示空态、不画空图；
5. 造一段 40 段、其中一段 8 个命中的正文，横向滚动与高度正常。

结果写进 `docs/superpowers/plans/2026-10-24-logic-chain-graph-walkthrough.md`。

---

### Task 7: 收口

- [ ] 同步 `CLAUDE.md`：§7 路线图加一行「二期 · 逻辑链图形化」，阶段记录写实现与验证；§8 变更记录加「图形只表达出现顺序」「补 `paragraphs`」两条。
- [ ] 合并 `worktree-logic-chain-graph` 到 master，删 worktree 与分支。
