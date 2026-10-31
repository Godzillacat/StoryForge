import type { VolumeNode } from '../../api/client'
import { Button } from '../../ui/Button'

export interface Selection {
  kind: 'volume' | 'chapter' | 'scene'
  id: string
}

export default function ChapterTree({
  volumes,
  selected,
  onSelect,
  onAddVolume,
  onAddChapter,
  onAddScene,
  onMove,
}: {
  volumes: VolumeNode[]
  selected: Selection | null
  onSelect: (selection: Selection) => void
  onAddVolume: () => void
  onAddChapter: (volumeId: string) => void
  onAddScene: (chapterId: string) => void
  onMove: (kind: Selection['kind'], id: string, direction: 'up' | 'down') => void
}) {
  const active = (kind: Selection['kind'], id: string) =>
    selected?.kind === kind && selected.id === id ? 'bg-accent-soft' : 'hover:bg-sunken'

  return (
    <nav className="space-y-3 text-[13.5px]">
      <Button onClick={onAddVolume}>
        新建卷
      </Button>
      {volumes.map((volume) => (
        <div key={volume.id}>
          <div className="flex items-center gap-1">
            <button
              className={`flex-1 rounded-control px-2 py-1.5 text-left ${active('volume', volume.id)}`}
              onClick={() => onSelect({ kind: 'volume', id: volume.id })}
            >
              第{volume.seq + 1}卷 {volume.name}
            </button>
            <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onMove('volume', volume.id, 'up')}>
              ↑
            </button>
            <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onMove('volume', volume.id, 'down')}>
              ↓
            </button>
            <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onAddChapter(volume.id)}>
              +章
            </button>
          </div>
          <ul className="ml-4 space-y-1">
            {volume.chapters.map((chapter) => (
              <li key={chapter.id}>
                <div className="flex items-center gap-1">
                  <button
                    className={`flex-1 rounded-control px-2 py-1 text-left ${active('chapter', chapter.id)}`}
                    onClick={() => onSelect({ kind: 'chapter', id: chapter.id })}
                  >
                    {chapter.seq + 1}. {chapter.title}
                  </button>
                  <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onMove('chapter', chapter.id, 'up')}>
                    ↑
                  </button>
                  <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onMove('chapter', chapter.id, 'down')}>
                    ↓
                  </button>
                  <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onAddScene(chapter.id)}>
                    +场景
                  </button>
                </div>
                <ul className="ml-4 space-y-1">
                  {chapter.scenes.map((scene) => (
                    <li key={scene.id} className="flex items-center gap-1">
                      <button
                        className={`flex-1 rounded-control px-2 py-1 text-left text-[11.5px] ${active('scene', scene.id)}`}
                        onClick={() => onSelect({ kind: 'scene', id: scene.id })}
                      >
                        场景{scene.seq + 1}：{scene.goal || '（未写目标）'}
                      </button>
                      <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onMove('scene', scene.id, 'up')}>
                        ↑
                      </button>
                      <button className="px-1 text-[11.5px] text-accent-ink" onClick={() => onMove('scene', scene.id, 'down')}>
                        ↓
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {volumes.length === 0 && (
        <p className="text-[13.5px] text-muted">还没有卷。点「新建卷」开始。</p>
      )}
    </nav>
  )
}
