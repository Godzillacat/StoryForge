export interface ProjectLike {
  id: string
}

/**
 * 决定当前显示哪个项目：深链 > 上次选择 > 列表第一个。
 * 三者都失效（项目被删、链接过期）时返回空串，由页面显示空态 —— 不猜、不静默跳到别处。
 */
export function pickProjectId(
  stored: string | null,
  list: ProjectLike[],
  override?: string | null,
): string {
  const known = (id: string | null | undefined): id is string =>
    Boolean(id) && list.some((project) => project.id === id)

  if (known(override)) return override
  if (known(stored)) return stored
  return list[0]?.id ?? ''
}
