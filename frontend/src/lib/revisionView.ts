/**
 * 修订建议列表的纯视图逻辑。
 *
 * 面板只做两件事：判断一行还能不能勾、数勾了几行。把这两件从组件里
 * 拿出来，是因为「锁定与已变化的行不可选」是这条链路上最容易写错的
 * 规则 —— 写错的后果不是显示难看，而是把旧建议套到作者刚改过的内容上。
 */

/** 一行建议在界面上的可选状态。 */
export interface RevisionRowState {
  /** 对象已锁定：服务端会跳过，界面也不该允许勾选。 */
  locked?: boolean
  /** 现值已变化（或这一条已经应用过）：旧建议不能直接套。 */
  stale?: boolean
}

/** 锁定与已变化的行不可勾选；其余都能选。 */
export function isSelectable(item: RevisionRowState): boolean {
  return !item.locked && !item.stale
}

/**
 * 数「已勾选且仍可选」的行。
 *
 * 用数组下标对应 `selected` 里的成员：下标就是服务端建议的 `index`，
 * 也就是应用请求里 `accepted` 的值，三者必须是同一个东西。
 */
export function countSelected(
  items: readonly RevisionRowState[],
  selected: ReadonlySet<number>,
): number {
  return items.reduce(
    (count, item, position) =>
      selected.has(position) && isSelectable(item) ? count + 1 : count,
    0,
  )
}
