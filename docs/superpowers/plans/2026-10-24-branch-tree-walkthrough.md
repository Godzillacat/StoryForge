# 场景分支树 · 走查记录（2026-10-24）

## 方法

| 手段 | 覆盖 | 没覆盖 |
|---|---|---|
| 真实 uvicorn（临时数据目录）+ 真实 HTTP | 三层派生、深度、第四层拒绝、A/B 父拒绝、丢弃中间父后子提升为根、合入最深分支 | — |
| pytest 22 条 / vitest 12 条 | 深度、环保护、迁移 v13（含缺表库跳过）、派生复制正文、提升、纯函数建树与默认名 | — |
| 组件级渲染 | **未做**（BranchPanel 带数据加载与 `window.prompt`，本轮没做浏览器级走查） | 缩进观感、`window.prompt` 在 WebView2 是否可用 |

## 证据

**1. 三层与上限**

```
root  阿明犹豫          depth=1  parent=NULL
child 阿明决意          depth=2  parent=root
grand 阿明决意（短版）   depth=3  parent=child

第四层（parent=grand）  → 400「最多三层分支」
从 A/B 临时分支派生     → 400「A/B 分支不能作为派生起点」
```

**2. 丢弃中间父 → 孙分支提升为根**

```
DELETE /api/branches/{child}
GET    /api/branches/{grand}
→ name=阿明决意（短版） depth=1 parent=NULL
```

**3. 合入最深一条**

```
PUT  /api/branches/{grand}/body  {"content":"分支正文：他决定不再等。"}
POST /api/branches/{grand}/merge
→ chars=12
GET  /api/scenes/{id}/text  → 正文 =「分支正文：他决定不再等。」
GET  /api/scenes/{id}/revisions → branch:12, author:12
```

采纳/合并语义**与以前完全一致**：整份替换正文、旧正文进修订历史（来源 `branch`）。

## 已知限制

- **未做浏览器级走查**：缩进观感与 `window.prompt` 在 pywebview/WebView2 的可用性未验证 —— 若被拦截，需改成内联输入（这是个真实风险，手点时请先看这一点）。
- 深度上限三层；第四层给 400，前端「派生」按钮在 depth=3 时禁用。
- 丢弃父分支会把子分支提升为根，派生关系随之丢失（这是「不级联删」的代价）。
- 脏数据（父指针指向不在本场景的分支）会被当根处理。

## 请作者手点一次（2 分钟）

1. 写作台 → 分支 → 新建一条，再点它的「派生」→ 应弹出输入框（**若没有弹框，说明 prompt 被外壳拦截，请告诉我**）；
2. 连点两次「派生」默认名应是「父名 · 派生」与「父名 · 派生 2」；
3. 丢弃中间一条 → 它的子分支应升到顶层（缩进回到 0）。
