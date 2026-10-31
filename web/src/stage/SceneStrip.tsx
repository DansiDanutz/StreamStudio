import { useRef, useState } from 'react'
import { COLLECTIONS, PRESETS } from './presets'
import { orderedScenes, useStage } from './store'
import type { Scene } from './types'
import { useDirector } from '../director/store'
import { isPipShaped } from '../director/cueLayouts'

const SCENE_MIME = 'application/x-streamstudio-scene'
const PLATE = '/studio/plate-landscape-final.png'
const SEATED = '/avatar/thumbs/presenter-seated.jpg' // presenter at the desk, on the plate
const FACE = '/avatar/thumbs/presenter.jpg'
const BEZEL_BG: Record<string, string> = { space: '#07070d', violet: 'linear-gradient(135deg,#3a1d6e,#120a24)', ink: '#10141c', teal: 'linear-gradient(135deg,#0d4b4f,#071b1d)', mono: '#171717' }
const SYNC_LABEL = { local: 'saved in this browser', server: 'saved on Mac Studio', saving: 'saving…', error: 'not saved: server error' } as const

/** Bottom strip: every scene as a live thumbnail, grouped by collection. Click to switch,
 *  1–9 hotkeys, drag to reorder or to move between collections, double-click to rename. */
export function SceneStrip() {
  const scenes = useStage((s) => s.scenes)
  const activeId = useStage((s) => s.activeId)
  const orientation = useStage((s) => s.orientation)
  const sync = useStage((s) => s.sync)
  const { setActive, moveScene, newScene, importScenes } = useStage.getState()
  const [menu, setMenu] = useState<{ c: string; left: number } | null>(null) // "+ New" menu: collection + x
  const [over, setOver] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const ordered = orderedScenes(scenes)
  const extra = [...new Set(scenes.map((s) => s.collection ?? 'Talk'))].filter((c) => !(COLLECTIONS as readonly string[]).includes(c))
  const groups = [...COLLECTIONS, ...extra]

  const go = (id: string) => {
    if (!useDirector.getState().playing) useDirector.getState().stop() // drop a manual cue preview
    setActive(id)
  }
  const exportAll = () => {
    const blob = new Blob([JSON.stringify({ kind: 'streamstudio.scenes', version: 1, scenes: ordered }, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'streamstudio-scenes.json'
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 1000)
  }

  return (
    <div className="strip" onPointerDown={(e) => e.stopPropagation()}>
      <div className="strip-cols">
        {groups.map((c) => {
          const list = ordered.filter((s) => (s.collection ?? 'Talk') === c)
          return (
            <section key={c} className={`strip-col ${over === c ? 'is-over' : ''}`}
              onDragOver={(e) => { if (e.dataTransfer.types.includes(SCENE_MIME)) { e.preventDefault(); setOver(c) } }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => { const id = e.dataTransfer.getData(SCENE_MIME); setOver(null); if (id) moveScene(id, c, null) }}>
              <header>
                <span>{c}</span>
                <button className="strip-new" title={`New scene in ${c}`} onClick={(e) => {
                  const strip = (e.currentTarget.closest('.strip') as HTMLElement).getBoundingClientRect()
                  setMenu(menu?.c === c ? null : { c, left: e.currentTarget.getBoundingClientRect().left - strip.left })
                }}>+</button>
              </header>
              <div className="strip-row">
                {list.map((s) => <Thumb key={s.id} scene={s} n={ordered.indexOf(s) + 1} on={s.id === activeId} orientation={orientation} onGo={() => go(s.id)} />)}
                {!list.length && <div className="strip-empty">Drop a scene here</div>}
              </div>
            </section>
          )
        })}
      </div>
      {menu && (
        <div className="strip-menu" style={{ left: menu.left }} onMouseLeave={() => setMenu(null)}>
          <div className="lbl">New in {menu.c}, from template</div>
          {PRESETS.map((p) => <button key={p.id} onClick={() => { newScene(p.id, menu.c); setMenu(null) }}>{p.name}</button>)}
        </div>
      )}
      <div className="strip-foot">
        <span className={`sync sync-${sync}`} title={sync === 'local' ? 'No StreamStudio server here: scenes live in this browser. Export to keep a copy.' : ''}>● {SYNC_LABEL[sync]}</span>
        <button onClick={exportAll} title="Download every scene as a file">Export</button>
        <button onClick={() => fileRef.current?.click()} title="Add scenes from an exported file">Import</button>
        <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={async (e) => {
          const f = e.target.files?.[0]
          e.target.value = ''
          if (!f) return
          try {
            const j = JSON.parse(await f.text())
            const n = importScenes(Array.isArray(j) ? j : j.scenes ?? [])
            if (!n) alert('No scenes found in that file.')
          } catch { alert('That file is not a StreamStudio scene export.') }
        }} />
      </div>
    </div>
  )
}

function Thumb({ scene, n, on, orientation, onGo }: { scene: Scene; n: number; on: boolean; orientation: 'landscape' | 'portrait'; onGo: () => void }) {
  const { renameScene, duplicateScene, deleteScene, moveScene } = useStage.getState()
  const count = useStage((s) => s.scenes.length)
  const [editing, setEditing] = useState(false)
  const [drop, setDrop] = useState(false)
  const L = scene.layouts[orientation]
  const media = scene.media?.[orientation] ?? []
  const pct = (r: { x: number; y: number; w: number; h: number }) => ({ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%` })
  const avatarFull = L.avatar.visible && L.avatar.w >= 0.999 && L.avatar.h >= 0.999
  const seated = scene.bezel === 'studio' && avatarFull // the cut-out sits at the desk
  const bg = scene.bezel === 'studio' ? { backgroundImage: `url(${seated ? SEATED : PLATE})` } : avatarFull ? { backgroundImage: `url(${FACE})` } : { background: BEZEL_BG[scene.bezel] ?? '#111' }
  return (
    <div className={`thumb ${on ? 'is-on' : ''} ${drop ? 'is-drop' : ''}`} draggable={!editing}
      onDragStart={(e) => { e.dataTransfer.setData(SCENE_MIME, scene.id); e.dataTransfer.effectAllowed = 'move' }}
      onDragOver={(e) => { if (e.dataTransfer.types.includes(SCENE_MIME)) { e.preventDefault(); e.stopPropagation(); setDrop(true) } }}
      onDragLeave={() => setDrop(false)}
      onDrop={(e) => { e.stopPropagation(); setDrop(false); const id = e.dataTransfer.getData(SCENE_MIME); if (id) moveScene(id, scene.collection ?? 'Talk', scene.id) }}
      onClick={onGo} title={`${scene.name}${n <= 9 ? ` · key ${n}` : ''}`}>
      <div className={`thumb-frame ${orientation}`} style={bg}>
        {L.main.visible && <i className="t-main" style={pct(L.main)} />}
        {L.avatar.visible && !avatarFull && <i className={`t-avatar ${isPipShaped(L.avatar, orientation) ? 'round' : ''}`} style={{ ...pct(L.avatar), backgroundImage: `url(${FACE})` }} />}
        {scene.menuShown && <i className="t-menu" style={pct(L.menu)} />}
        {media.filter((m) => m.layout.visible).map((m) => (
          <i key={m.id} className="t-media" style={{ ...pct(m.layout), backgroundImage: m.poster ? `url(${m.poster})` : undefined }} />
        ))}
        {n <= 9 && <b className="t-key">{n}</b>}
      </div>
      {editing
        ? <input className="thumb-name" autoFocus defaultValue={scene.name} onClick={(e) => e.stopPropagation()}
            onBlur={(e) => { renameScene(scene.id, e.target.value); setEditing(false) }}
            onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') setEditing(false); e.stopPropagation() }} />
        : <div className="thumb-name" onDoubleClick={(e) => { e.stopPropagation(); setEditing(true) }}>{scene.name}</div>}
      <div className="thumb-actions" onClick={(e) => e.stopPropagation()}>
        <button title="Rename" onClick={() => setEditing(true)}>✎</button>
        <button title="Duplicate" onClick={() => duplicateScene(scene.id)}>⧉</button>
        <button title="Delete scene" disabled={count <= 1} onClick={() => { if (confirm(`Delete the scene "${scene.name}"?`)) deleteScene(scene.id) }}>✕</button>
      </div>
    </div>
  )
}
