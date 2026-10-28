import type { VolumeNode } from '../../api/client'

interface Props {
  volumes: VolumeNode[]
  selectedSceneId: string
  onSelect: (sceneId: string) => void
}

export default function WritingTree({ volumes, selectedSceneId, onSelect }: Props) {
  if (volumes.length === 0) {
    return (
      <p className="text-[13.5px] text-muted">
        这个项目还没有卷章结构，请先去「章节设计」排卷排章。
      </p>
    )
  }

  return (
    <div className="space-y-3 text-[13.5px]">
      {volumes.map((volume) => (
        <section key={volume.id}>
          <h3 className="mb-1 font-medium text-ink-2">
            第{volume.seq + 1}卷 {volume.name}
          </h3>
          {volume.chapters.map((chapter) => (
            <div key={chapter.id} className="mb-2">
              <p className="mb-1 text-[11.5px] text-muted">
                第{chapter.seq + 1}章 {chapter.title}
              </p>
              <ul className="space-y-1">
                {chapter.scenes.map((scene) => (
                  <li key={scene.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(scene.id)}
                      className={`w-full rounded-control px-2 py-1 text-left ${
                        selectedSceneId === scene.id
                          ? 'bg-accent-soft text-accent-ink'
                          : 'text-muted hover:bg-sunken'
                      }`}
                    >
                      <span className="block truncate">
                        {scene.seq + 1}. {scene.goal || '（未写目标）'}
                      </span>
                      <span
                        className={`text-[11.5px] ${
                          scene.has_body ? 'text-accent-ink' : 'text-faint'
                        }`}
                      >
                        {scene.has_body ? '已写' : '未写'}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
