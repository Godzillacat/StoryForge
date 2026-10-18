import type { VolumeNode } from '../../api/client'

interface Props {
  volumes: VolumeNode[]
  selectedSceneId: string
  onSelect: (sceneId: string) => void
}

export default function WritingTree({ volumes, selectedSceneId, onSelect }: Props) {
  if (volumes.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        这个项目还没有卷章结构，请先去「章节设计」排卷排章。
      </p>
    )
  }

  return (
    <div className="space-y-3 text-sm">
      {volumes.map((volume) => (
        <section key={volume.id}>
          <h3 className="mb-1 font-medium text-slate-300">
            第{volume.seq + 1}卷 {volume.name}
          </h3>
          {volume.chapters.map((chapter) => (
            <div key={chapter.id} className="mb-2">
              <p className="mb-1 text-xs text-slate-500">
                第{chapter.seq + 1}章 {chapter.title}
              </p>
              <ul className="space-y-1">
                {chapter.scenes.map((scene) => (
                  <li key={scene.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(scene.id)}
                      className={`w-full rounded px-2 py-1 text-left ${
                        selectedSceneId === scene.id
                          ? 'bg-slate-800 text-white'
                          : 'text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      <span className="block truncate">
                        {scene.seq + 1}. {scene.goal || '（未写目标）'}
                      </span>
                      <span
                        className={`text-xs ${
                          scene.has_body ? 'text-emerald-400' : 'text-slate-600'
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
