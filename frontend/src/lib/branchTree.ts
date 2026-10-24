/**
 * 写作台分支列表的树形布局纯函数。
 *
 * 派生关系在后端是 `parent_branch_id` 一条边；深度由服务层沿父链算好
 * （根 = 1，最多 3 层）随列表一起下发。前端不重复计算语义，只把平铺的
 * 列表排成「根在前、子紧随父」的前序，并给出缩进与父名。
 */

/** 一行分支缩进 16px —— 三层最窄也还读得清（设计 §3.3）。 */
export const INDENT_PER_LEVEL = 16

/** 派生默认名的后缀；只影响 prompt 的预填值，不改变后端「重名报错」。 */
const DERIVE_SUFFIX = ' · 派生'

/** `buildBranchRows` 只依赖这几个字段；`BranchSummary` 满足它。 */
export interface BranchNode {
  id: string
  name: string
  parent_id?: string | null
  depth?: number
}

/** 排好序的一行：原样透传分支字段，另加树的三个派生值。 */
export type BranchRow<T extends BranchNode = BranchNode> = T & {
  depth: number
  indent: number
  /** 父分支的名字；根分支（含父不在列表里的孤儿）为 null。 */
  parentName: string | null
}

/**
 * 把分支列表排成前序：根按列表顺序在前，每条子分支紧跟它的父分支。
 *
 * - **深度以后端为准**：后端给 `depth` 就直接用，缺了才按树结构补
 *   （根 = 1，子 = 父 + 1）。后端一次算全场景的深度，前端重算只会算浅
 *   —— 列表里可能只有父链的一部分。
 * - **孤儿当根**：`parent_id` 指向的分支不在列表里（父被删 / 是 A/B
 *   临时分支）时，它作为根排在顶层，且不显示「派生自」（前端拿不到名字）。
 * - **脏数据成环**：环上的分支不是任何根的子孙，遍历完根后按原顺序补成
 *   根，保证列表里一条都不少、也不会转不出来。
 */
export function buildBranchRows<T extends BranchNode>(
  branches: readonly T[] | null | undefined,
): BranchRow<T>[] {
  const list = branches ?? []
  const byId = new Map<string, T>()
  for (const branch of list) {
    if (!byId.has(branch.id)) byId.set(branch.id, branch)
  }

  const childrenOf = new Map<string, T[]>()
  const roots: T[] = []
  for (const branch of list) {
    const parentId = branch.parent_id ?? null
    // 指向自己也算孤儿，否则它永远等不到被遍历。
    if (parentId !== null && parentId !== branch.id && byId.has(parentId)) {
      const siblings = childrenOf.get(parentId)
      if (siblings) siblings.push(branch)
      else childrenOf.set(parentId, [branch])
    } else {
      roots.push(branch)
    }
  }

  const rows: BranchRow<T>[] = []
  const seen = new Set<string>()

  function emit(branch: T, structuralDepth: number, parent: T | null): void {
    if (seen.has(branch.id)) return
    seen.add(branch.id)
    const depth =
      typeof branch.depth === 'number' && branch.depth > 0
        ? branch.depth
        : structuralDepth
    rows.push({
      ...branch,
      depth,
      indent: (depth - 1) * INDENT_PER_LEVEL,
      parentName: parent ? parent.name : null,
    })
    for (const child of childrenOf.get(branch.id) ?? []) {
      emit(child, depth + 1, branch)
    }
  }

  for (const root of roots) emit(root, 1, null)
  // 成环 / 重复 id 的尾巴：不是任何根的子孙，也不能从列表里消失。
  for (const branch of list) {
    if (!seen.has(branch.id)) emit(branch, 1, null)
  }
  return rows
}

/**
 * 派生时 prompt 的预填名：「父名 · 派生」；已被占用就依次试
 * 「父名 · 派生 2」「父名 · 派生 3」……
 *
 * **只避让当前列表里已有的名字**，不替后端做唯一性判断：作者改完名字
 * 提交时若仍重名，后端照旧 400、错误原样显示 —— 这里只是让默认值少撞墙。
 */
export function defaultChildName(
  parentName: string,
  existingNames: readonly string[],
): string {
  const base = `${(parentName ?? '').trim()}${DERIVE_SUFFIX}`
  // 与后端 `_clean_name` 同口径：名字两端空白不算数。
  const taken = new Set(existingNames.map((name) => (name ?? '').trim()))
  if (!taken.has(base)) return base
  let suffix = 2
  while (taken.has(`${base} ${suffix}`)) suffix += 1
  return `${base} ${suffix}`
}

