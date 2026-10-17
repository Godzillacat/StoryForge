import { useEffect, useState } from 'react'
import { api, type ChapterStatusOption, type Project, type VolumeNode } from '../api/client'
import ChapterTree, { type Selection } from '../components/chapters/ChapterTree'
import ChapterEditor from '../components/chapters/ChapterEditor'
import SceneEditor from '../components/chapters/SceneEditor'
import VolumeEditor from '../components/chapters/VolumeEditor'

export default function Chapters() {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [statuses, setStatuses] = useState<ChapterStatusOption[]>([])
  const [volumes, setVolumes] = useState<VolumeNode[]>([])
  const [selected, setSelected] = useState<Selection | null>(null)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (list[0]) setProjectId(list[0].id)
    }).catch((error) => setNotice((error as Error).message))
    api.listChapterTypes().then((data) => setStatuses(data.statuses))
      .catch((error) => setNotice((error as Error).message))
  }, [])

  useEffect(() => {
    if (!projectId) return
    setSelected(null)
    setNotice('')
    setVolumes([])
    api.getChapterTree(projectId).then((data) => setVolumes(data.volumes))
      .catch((error) => setNotice((error as Error).message))
  }, [projectId])

  async function refresh() {
    const data = await api.getChapterTree(projectId)
    setVolumes(data.volumes)
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setNotice('')
    try {
      await action()
    } catch (error) {
      setNotice((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const volume = selected?.kind === 'volume' ? volumes.find((v) => v.id === selected.id) : undefined
  const chapter =
    selected?.kind === 'chapter'
      ? volumes.flatMap((v) => v.chapters).find((c) => c.id === selected.id)
      : undefined
  const scene =
    selected?.kind === 'scene'
      ? volumes.flatMap((v) => v.chapters).flatMap((c) => c.scenes).find((s) => s.id === selected.id)
      : undefined

  async function addVolume() {
    await run(async () => {
      const created = await api.createVolume(projectId, { name: '新卷' })
      await refresh()
      setSelected({ kind: 'volume', id: created.id })
    })
  }

  async function addChapter(volumeId: string) {
    await run(async () => {
      const created = await api.createChapter(volumeId, { title: '新章' })
      await refresh()
      setSelected({ kind: 'chapter', id: created.id })
    })
  }

  async function addScene(chapterId: string) {
    await run(async () => {
      const created = await api.createScene(chapterId, { goal: '' })
      await refresh()
      setSelected({ kind: 'scene', id: created.id })
    })
  }

  async function move(kind: Selection['kind'], id: string, direction: 'up' | 'down') {
    await run(async () => {
      if (kind === 'volume') await api.moveVolume(id, direction)
      else if (kind === 'chapter') await api.moveChapter(id, direction)
      else await api.moveScene(id, direction)
      await refresh()
    })
  }

  async function deleteSelected() {
    if (!selected) return
    if (!window.confirm('删除这一项？子项会一并删除。')) return
    await run(async () => {
      if (selected.kind === 'volume') await api.deleteVolume(selected.id)
      else if (selected.kind === 'chapter') await api.deleteChapter(selected.id)
      else await api.deleteScene(selected.id)
      setSelected(null)
      await refresh()
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">章节设计</h2>
        <select className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>{project.name}</option>
          ))}
        </select>
        {notice && <span className="text-sm text-slate-400">{notice}</span>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <ChapterTree
          volumes={volumes}
          selected={selected}
          onSelect={setSelected}
          onAddVolume={addVolume}
          onAddChapter={addChapter}
          onAddScene={addScene}
          onMove={move}
        />

        <div className="space-y-4">
          {!selected && (
            <p className="rounded border border-slate-800 p-4 text-sm text-slate-500">
              从左边选一卷、一章或一个场景开始编辑；也可以先手工建卷。
            </p>
          )}
          {volume && (
            <VolumeEditor
              volume={volume}
              statuses={statuses}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateVolume(volume.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
          )}
          {chapter && (
            <ChapterEditor
              chapter={chapter}
              statuses={statuses}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateChapter(chapter.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
          )}
          {scene && (
            <SceneEditor
              scene={scene}
              statuses={statuses}
              busy={busy}
              onSave={async (fields) => run(async () => {
                await api.updateScene(scene.id, fields)
                await refresh()
                setNotice('已保存')
              })}
              onDelete={deleteSelected}
            />
          )}
        </div>
      </div>
    </div>
  )
}
