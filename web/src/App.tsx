import { useEffect, useState } from 'react'
import { PRESETS } from './stage/presets'
import { Stage } from './stage/Stage'
import { useStage } from './stage/store'
import { ScriptPanel } from './director/ScriptPanel'
import { Library, fileToItem } from './stage/Library'
import { useDirector } from './director/store'
import { guardCue, lipsMatch, type Cue } from './director/types'

const RENDER = new URLSearchParams(location.search).get('render') === '1'
const AUTOPLAY = new URLSearchParams(location.search).get('autoplay') === '1'

/** Output-clean view used by the headless renderer and (later) the live compositor. */
function RenderView() {
  useEffect(() => {
    document.documentElement.classList.add('render-mode')
    const st = useStage.getState()
    if (st.guides) st.toggleGuides()
    ;(window as unknown as { __director: typeof useDirector }).__director = useDirector
    // Open directly on the first segment's cue (no tween from the editor layout), then play.
    const d = useDirector.getState()
    const first = d.script.segments[0]
    if (first) d.applyCue(guardCue(first.cue, first), first.zoom ?? null, 0, !lipsMatch(first))
    if (AUTOPLAY) setTimeout(() => useDirector.getState().play(0), 800)
  }, [])
  return <div className="render-root"><Stage /></div>
}

export default function App() {
  if (RENDER) return <RenderView />
  return <Editor />
}

function Editor() {
  const scenes = useStage((s) => s.scenes)
  const activeId = useStage((s) => s.activeId)
  const scene = useStage((s) => s.active())
  const orientation = useStage((s) => s.orientation)
  const guides = useStage((s) => s.guides)
  const selected = useStage((s) => s.selected)
  const { toggleOrientation, toggleMenu, toggleGuides, setActive, saveAs, deleteScene, loadPreset, toggleLocked, toggleVisible, toggleCutout } = useStage.getState()
  const cutout = useStage((s) => s.cutout)
  const [health, setHealth] = useState<string>('…')
  const [tab, setTab] = useState<'library' | 'script'>('library')
  const cue = useDirector((s) => s.cue)
  const live = useDirector((s) => s.live)
  const { applyCue, stop } = useDirector.getState()

  useEffect(() => {
    fetch('/api/health').then((r) => r.json()).then((h) => setHealth(`api ${h.version} · ${h.hw_encoders?.length ? `${h.hw_encoders.length} hw encoders` : 'no hw encoder'} · ${h.jobs.queued} queued`)).catch(() => setHealth('api offline'))
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT') return
      const k = e.key.toLowerCase()
      if (k === 'o') toggleOrientation()
      if (k === 'm') toggleMenu()
      if (k === 'g') toggleGuides()
      if (k === 'l' && selected) toggleLocked(selected)
      if (k === 'h' && selected) toggleVisible(selected)
      if (/^[1-6]$/.test(k)) loadPreset(PRESETS[Number(k) - 1].id)
      const cues: Record<string, Cue> = { a: 'avatar', d: 'duo', s: 'split', c: 'content', f: 'full', p: 'pip' }
      if (cues[k]) applyCue(cues[k])
      if (k === 'escape') stop()
      if (k === 'z') applyCue('content', { x: 0.5, y: 0.5, scale: 1.6 })
      if (k === 'x') useDirector.getState().pushSketch(null)
      const sm = useStage.getState().selectedMedia
      if (sm && (k === 'delete' || k === 'backspace')) useStage.getState().removeMedia(sm)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, toggleOrientation, toggleMenu, toggleGuides, toggleLocked, toggleVisible, loadPreset, applyCue, stop])

  return (
    <div className="app">
      <header className="bar">
        <div className="brand">Stream<em>Studio</em></div>
        <div className="group">
          <select value={activeId} onChange={(e) => setActive(e.target.value)} aria-label="Scene">
            {scenes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <button onClick={() => { const n = prompt('Scene name', `${scene.name} copy`); if (n) saveAs(n) }}>Save as</button>
          <button onClick={() => deleteScene(activeId)} disabled={scenes.length <= 1}>Delete</button>
        </div>
        <div className="group">
          <button onClick={toggleOrientation} title="O">{orientation === 'landscape' ? '16:9' : '9:16'}</button>
          <button onClick={toggleMenu} className={scene.menuShown ? 'on' : ''} title="M">Menu {scene.menuShown ? 'shown' : 'transparent'}</button>
          <button onClick={toggleGuides} className={guides ? 'on' : ''} title="G">Guides</button>
          <button onClick={toggleCutout} className={cutout ? 'on' : ''} title="Presenter cut out of the clip and placed in the studio">Cut-out</button>
        </div>
        <div className="group cuebar" role="group" aria-label="Cue">
          {(['avatar', 'duo', 'split', 'content', 'full', 'pip'] as Cue[]).map((c) => (
            <button key={c} className={live && cue === c ? 'on' : ''} onClick={() => applyCue(c)} title={c[0].toUpperCase()}>{c}</button>
          ))}
          {live && <button onClick={stop} title="Esc">reset</button>}
        </div>
        <div className="status">{health}</div>
      </header>
      <main className="work">
        <Stage />
        <aside className="side">
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'library'} className={tab === 'library' ? 'on' : ''} onClick={() => setTab('library')}>Library</button>
            <button role="tab" aria-selected={tab === 'script'} className={tab === 'script' ? 'on' : ''} onClick={() => setTab('script')}>Script</button>
          </div>
          {tab === 'library'
            ? <Library onAddFile={(f) => { const it = fileToItem(f); useStage.getState().addMedia({ label: it.label, src: it.src, playback: it.playback, framed: it.framed, at: { x: 0.5, y: 0.45 }, w: it.w, aspect: it.aspect }) }} />
            : <ScriptPanel />}
        </aside>
      </main>
      <footer className="hints">
        Drag cards · corner handles resize · Alt = no snap · <b>O</b> orientation · <b>M</b> menu · <b>G</b> guides · <b>L</b> lock · <b>H</b> hide · <b>1–6</b> presets · cues <b>A</b> avatar <b>D</b> duo <b>S</b> split <b>C</b> content <b>F</b> full <b>P</b> pip <b>Z</b> zoom <b>Esc</b> reset · drag from Library to add a card · <b>Del</b> removes it
      </footer>
    </div>
  )
}
