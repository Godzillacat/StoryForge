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
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        还没有卷章。去「结构设计」建卷，或先用 AI 排卷章。
      </p>
    )
  }
  if (model.rows.length === 0) {
    return (
      <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
        章还没填推进的线。在结构设计里编辑章，填「推进的线」后这里会按线分组。
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-slate-300">剧情线</h3>
        <p className="text-xs text-slate-500">
          行是章里的「推进的线」，列是故事顺序的章；点格子回到该章。
        </p>
      </div>
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="text-left text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-slate-900 px-3 py-2 text-xs text-slate-400">
                线
              </th>
              {model.bands
                .filter((band) => band.end > band.start)
                .map((band) => (
                  <th
                    key={band.id}
                    colSpan={band.end - band.start}
                    className="border-l border-slate-800 px-2 py-2 text-center text-xs text-slate-300"
                  >
                    {band.name}
                  </th>
                ))}
            </tr>
            <tr>
              <th className="sticky left-0 z-10 bg-slate-900 px-3 py-1 text-xs text-slate-500">
                章
              </th>
              {model.chapters.map((chapter) => (
                <th
                  key={chapter.id}
                  title={`${chapter.label}（${chapter.volumeName}）`}
                  className="border-l border-slate-800 px-1 py-1 text-center text-xs font-normal text-slate-500"
                >
                  {chapter.chapterSeq + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.rows.map((row) => (
              <tr key={row.name} className="border-t border-slate-800">
                <th className="sticky left-0 z-10 whitespace-nowrap bg-slate-950 px-3 py-2 text-left text-xs font-medium text-slate-300">
                  {row.name}{' '}
                  <span className="text-slate-500">({row.count})</span>
                </th>
                {model.chapters.map((chapter, index) => (
                  <td
                    key={chapter.id}
                    className="border-l border-slate-800 px-1 py-1 text-center"
                  >
                    {row.cells[index] ? (
                      <button
                        className="mx-auto block h-4 w-6 rounded-sm bg-indigo-500 hover:bg-indigo-400"
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
