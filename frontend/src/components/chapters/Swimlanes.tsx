import type { VolumeNode } from '../../api/client'
import { buildSwimlanes } from '../../lib/chapterViews'

export default function Swimlanes({
  volumes,
  onSelectChapter,
}: {
  volumes: VolumeNode[]
  onSelectChapter: (id: string) => void
}) {
  const model = buildSwimlanes(volumes)
  if (model.chapters.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        还没有卷章。去「结构设计」建卷，或先用 AI 排卷章。
      </p>
    )
  }
  if (model.rows.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-[13.5px] text-muted">
        章还没填推进的线。在结构设计里编辑章，填「推进的线」后这里会按线分组。
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-[13.5px] font-medium text-ink-2">剧情线</h3>
        <p className="text-[11.5px] text-muted">
          行是章里的「推进的线」，列是故事顺序的章；点格子回到该章。
        </p>
      </div>
      <div className="overflow-x-auto rounded-card border border-line">
        <table className="text-left text-[13.5px]">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-surface px-3 py-2 text-[11.5px] text-muted">
                线
              </th>
              {model.bands
                .filter((band) => band.end > band.start)
                .map((band) => (
                  <th
                    key={band.id}
                    colSpan={band.end - band.start}
                    className="border-l border-line px-2 py-2 text-center text-[11.5px] text-ink-2"
                  >
                    {band.name}
                  </th>
                ))}
            </tr>
            <tr>
              <th className="sticky left-0 z-10 bg-surface px-3 py-1 text-[11.5px] text-muted">
                章
              </th>
              {model.chapters.map((chapter) => (
                <th
                  key={chapter.id}
                  title={`${chapter.label}（${chapter.volumeName}）`}
                  className="border-l border-line px-1 py-1 text-center text-[11.5px] font-normal text-muted"
                >
                  {chapter.chapterSeq + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.rows.map((row) => (
              <tr key={row.name} className="border-t border-line">
                <th className="sticky left-0 z-10 whitespace-nowrap bg-surface px-3 py-2 text-left text-[11.5px] font-medium text-ink-2">
                  {row.name}{' '}
                  <span className="text-muted">({row.count})</span>
                </th>
                {model.chapters.map((chapter, index) => (
                  <td
                    key={chapter.id}
                    className="border-l border-line px-1 py-1 text-center"
                  >
                    {row.cells[index] ? (
                      <button
                        className="mx-auto block h-4 w-6 rounded-sm bg-accent hover:bg-accent-ink"
                        title={`${chapter.label}（${chapter.volumeName}）`}
                        aria-label={`${chapter.label}：${row.name}`}
                        onClick={() => onSelectChapter(chapter.id)}
                      />
                    ) : (
                      <span className="block h-4 w-6" />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
