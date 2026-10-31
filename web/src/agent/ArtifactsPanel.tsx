import { useMemo, useState } from 'react'
import { buildCatalog, type Artifact } from './catalog'
import { EXECUTORS } from './bridge'
import { useStage, orderedScenes } from '../stage/store'

const KIND_LABEL: Record<string, string> = {
  scene: 'Scenes', template: 'Templates', cue: 'Layouts', gesture: 'Gestures', target: 'Cards',
  hotspot: 'Studio places', object: 'Objects', media: 'Media', workflow: 'Workflows', 'stage-media': 'On stage now',
}

/** Every artifact, the way agents see it: id, what it is, and the actions that use it.
 *  ▶ runs an action here; ⧉ copies the exact call an agent would make. */
export function ArtifactsPanel() {
  const scenes = useStage((s) => s.scenes)
  const media = useStage((s) => s.active().media?.[s.orientation])
  const [kind, setKind] = useState<string>('all')
  const [q, setQ] = useState('')
  const [note, setNote] = useState<string | null>(null)

  const all = useMemo<Artifact[]>(() => {
    const base = buildCatalog().artifacts
    const sc: Artifact[] = orderedScenes(scenes).map((s) => ({
      id: `scene:${s.id}`, kind: 'scene', name: s.name, description: `Scene in ${s.collection ?? 'Talk'}.`,
      actions: [{ action: 'scene.activate', args: { id: s.id } }],
    }))
    const live: Artifact[] = (media ?? []).map((m) => ({
      id: `media:${m.id}`, kind: 'stage-media', name: m.label, description: 'A media card on the current scene.', preview: m.poster,
      actions: [{ action: 'point.at', args: { target: `media:${m.id}` } }, { action: 'media.remove', args: { id: m.id } }],
    }))
    return [...sc, ...live, ...base]
  }, [scenes, media])

  const kinds = ['all', ...Array.from(new Set(all.map((a) => a.kind)))]
  const shown = all.filter((a) => (kind === 'all' || a.kind === kind) && (!q || `${a.id} ${a.name} ${a.description}`.toLowerCase().includes(q.toLowerCase())))

  const run = (action: string, args: Record<string, unknown>) => {
    try {
      const r = EXECUTORS[action](args)
      setNote(`${action} ✓ ${r && Object.keys(r as object).length ? JSON.stringify(r) : ''}`)
    } catch (e) { setNote(`${action}: ${(e as Error).message}`) }
  }
  const copy = (action: string, args: Record<string, unknown>) => {
    const call = JSON.stringify({ tool: 'studio_do', arguments: { action, args } })
    void navigator.clipboard?.writeText(call).then(() => setNote('Agent call copied'), () => setNote(call))
  }

  return (
    <div className="artifacts">
      <div className="lib-head">
        <div className="lbl">Artifacts · {all.length}</div>
        <p>Everything in the studio, as agents see it. <b>▶</b> runs it here; <b>⧉</b> copies the call an agent makes (MCP <code>studio_do</code>, see docs/AGENTS.md).</p>
        <input className="art-search" placeholder="Search artifacts…" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="art-kinds">
          {kinds.map((k) => (
            <button key={k} className={kind === k ? 'on' : ''} onClick={() => setKind(k)}>
              {k === 'all' ? 'All' : KIND_LABEL[k] ?? k} <span>{k === 'all' ? all.length : all.filter((a) => a.kind === k).length}</span>
            </button>
          ))}
        </div>
        {note && <div className="art-note">{note}</div>}
      </div>
      <ul className="art-list">
        {shown.map((a) => (
          <li key={a.id}>
            {a.preview ? <img src={a.preview} alt="" /> : <i className={`art-ico k-${a.kind}`} />}
            <div className="art-body">
              <div className="art-name">{a.name} <code>{a.id}</code></div>
              <div className="art-desc">{a.description}</div>
              <div className="art-actions">
                {a.actions.map((x, i) => (
                  <span key={i} className="art-act">
                    <button title={`Run ${x.action} here`} onClick={() => run(x.action, x.args)}>▶ {x.action}{x.args && Object.values(x.args)[0] && x.action === 'table.event' ? ` ${String(Object.values(x.args)[0])}` : ''}</button>
                    <button title="Copy the agent call" onClick={() => copy(x.action, x.args)}>⧉</button>
                  </span>
                ))}
              </div>
            </div>
          </li>
        ))}
        {!shown.length && <li className="art-empty">Nothing matches.</li>}
      </ul>
    </div>
  )
}
