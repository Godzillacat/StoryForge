# P4c 走查记录：伏笔闭环与逻辑链文本视图

> 2026-10-22。分支 `worktree-p4c-foreshadow-logic`。走查全程使用临时数据目录
> （`STORYFORGE_DATA_DIR`），**未调用模型**、**未写入作者真实库**。

## 1. 自动化测试

| 项 | 结果 |
|---|---|
| 后端 | **917 passed**（基线 889，本段新增 28） |
| 前端 | **33 passed**（基线 30，本段新增 3） |
| 前端构建 | `pnpm build` 干净 |

## 2. 接口级走查（`scripts/p4c_walkthrough.py`，22 项全过）

| 步骤 | 预期 | 实测 |
|---|---|---|
| `GET /api/foreshadow-types` | 四态按 planned/planted/paid/dropped 下发，中文标签正确 | ✅ |
| 建四条伏笔覆盖四态 | 均 201 | ✅ |
| 只设计划回收、无埋设 | `effective_status=planned` | ✅ |
| 给「还没动」挂上埋设位置 | `effective_status=planted`，`status` 仍是 `planned`，`status_is_derived=true` | ✅ |
| 显式 `planted` + 实际回收 | `effective_status=paid`（事实赢） | ✅ |
| 显式 `dropped` + 实际回收 | `effective_status=dropped`（唯一例外） | ✅ |
| 汇总 | paid 2 / planted 1 / planned 0 / dropped 1 | ✅ |
| 回收率 | `0.667`（2/3，`dropped` 不进分母） | ✅ |
| 未知状态 `finished` | 400，文案含「未知的伏笔状态」 | ✅ |
| 中文标签「已弃」写入 | 落库为 `dropped` | ✅ |
| 清掉实际回收 | `effective_status` 退回 `planted` | ✅ |
| 旧值 `confirmed`（直接写库造） | `status_is_legacy=true`、`effective_status=planned`、`status` 原样 | ✅ |
| 成品报告未回收 | 不含已弃与已收，含已埋未收的 | ✅ |
| 逻辑链三类 | `["cause","turn","reveal"]` | ✅ |
| 段落序号 | `[2,3,4]`（按非空段落计） | ✅ |
| 汇总计数 | `{total:3, cause:1, turn:1, reveal:1}` | ✅ |
| 连接词与中文类型名 | 「因为」/「因果」 | ✅ |
| 空正文 | `chain=[]` 且给出原因 | ✅ |
| 无连接词 | `chain=[]`，文案含「没有明显」 | ✅ |
| 不存在的场景 | 404 | ✅ |

### 2.1 走查抓到的真缺陷（已修）

**`ForeshadowUpdate` 不开放 `actual_pay_scene_id`。** 走查第 5、6 步与汇总断言一起红了：
只有回写助手能写实际回收位置，一旦它把伏笔匹配到错误的场景，这条伏笔的
`effective_status` 会**永久**停在 `paid` —— 状态列的下拉改不回任何其他值，作者无从自救。

修法：`ForeshadowUpdate` 加该字段（服务层 `_checked_scene_id` 校验场景存在且属于同一
项目，`exclude_unset` 保证「没传」与「传 null」区分），账本每行给一个「清掉实际回收」
入口，补 2 条后端测试（`test_author_can_clear_a_wrongly_matched_actual_pay` 等）。

## 3. 浏览器走查（Playwright + msedge）

后端 `STORYFORGE_DATA_DIR=/tmp/sf-p4c` 起在 8756，前端 `pnpm dev --port 5273`。

| 项 | 结果 |
|---|---|
| 伏笔账本渲染 | 5 条；「共 5 条 · 已收 2 · 已埋未收 1 · 规划中 1 · 已弃 1 · 回收率 50%（2/4）」 |
| 「已弃」筛选 | 只剩「作者放弃」一行 |
| 行内改状态 | 「还没动」→ 已弃：头部变成「已弃 2 · 回收率 67%（2/3）」 |
| 清掉实际回收 | 「显式已埋」→ 已收 2→1、已埋未收 0→1、回收率 67%→33% |
| 逻辑链面板 | ¶2 因果 / ¶3 转折 / ¶4 揭示，连接词分别标「因为」「但是」「原来」 |
| 无连接词的场景 | 显示「正文里没有明显的因果连接词。」 |
| 控制台 | 0 ERROR |

走查中还修了两处 UI 语义：

- **「派生」与「旧值」徽标互斥**：旧值那行也「不等」，但那是词表归一、不是位置派生，
  两个标记同时出现会让作者以为位置字段改过。
- **旧值行重选「规划中」是 no-op**：`effective_status` 相等导致早返回，琥珀色「旧值」
  徽标永远去不掉。改为 `next === row.effectiveStatus && !row.statusIsLegacy` 才跳过。

## 4. 未覆盖 / 遗留

- **旧值行的修复路径只做了代码级推理，没在浏览器里造一条 `confirmed` 数据验证**
  （接口走查里造过，界面上只验证了徽标渲染）。作者库若真有存量 `confirmed`，
  第一次重选「规划中」时会走这条新分支。
- 逻辑链**只认连接词**，不理解句子；「于是他停下，因为下雨」报「于是」（类型仍是因果）。
  误报的代价只是多列一句，且它不接入任何自动检查。
- 逻辑链**不做图形化**（依 D-22 推二期）。
- 伏笔**不自动推进状态**：正文写入不会把伏笔标成 `paid`，那仍走回写助手 + 作者确认。
- 回收率**没有历史曲线**，只有当前值。
