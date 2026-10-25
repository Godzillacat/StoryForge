import type { IconName } from '../ui/icons'

export interface NavItem {
  to: string
  label: string
  icon: IconName
  /** 需要从项目元数据里取数的角标；目前只有设定条目总数。 */
  badge?: 'entries'
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

/**
 * 侧栏导航：按创作阶段分组，顺序固定 —— 构思 → 设定 → 写作 → 阅读与发行 → 系统。
 * 顺序本身就是产品判断：作者一天里先想故事，再补设定，然后动笔，最后才是配置。
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    title: '总览',
    items: [{ to: '/dashboard', label: '故事仪表盘', icon: 'dashboard' }],
  },
  {
    title: '构思',
    items: [
      { to: '/idea', label: '灵感与解析', icon: 'idea' },
      { to: '/architecture', label: '架构推荐', icon: 'architecture' },
    ],
  },
  {
    title: '设定',
    items: [
      { to: '/world', label: '世界观', icon: 'world', badge: 'entries' },
      { to: '/relations', label: '关系网', icon: 'relations' },
      { to: '/timeline', label: '时间线', icon: 'timeline' },
      { to: '/terms', label: '术语表', icon: 'terms' },
    ],
  },
  {
    title: '写作',
    items: [
      { to: '/chapters', label: '章节设计', icon: 'chapters' },
      { to: '/write', label: '写作台', icon: 'write' },
    ],
  },
  {
    title: '阅读与发行',
    items: [
      { to: '/read', label: '阅读器', icon: 'read' },
      { to: '/pipeline', label: '管线编排', icon: 'pipeline' },
    ],
  },
  {
    title: '系统',
    items: [
      { to: '/studio', label: '智能体工作室', icon: 'studio' },
      { to: '/models', label: '模型与费用', icon: 'models' },
    ],
  },
]

export function flatNavItems(groups: NavGroup[] = NAV_GROUPS): NavItem[] {
  return groups.flatMap((group) => group.items)
}
