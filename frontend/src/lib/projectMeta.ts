export interface ProjectMetaView {
  volumes: number | null
  chapters: number | null
  words: number | null
}

export function formatWords(value: number | null): string {
  if (value === null) return '—'
  if (value >= 10000) return `${(value / 10000).toFixed(1)} 万字`
  return `${value} 字`
}

/** 侧栏底部的一行摘要。取不到的数按「不知道」显示破折号，不冒充 0。 */
export function summaryLine(meta: ProjectMetaView): string {
  const volumes = meta.volumes === null ? '—' : `${meta.volumes} 卷`
  const chapters = meta.chapters === null ? '—' : `${meta.chapters} 章`
  return `${volumes} · ${chapters} · ${formatWords(meta.words)}`
}
