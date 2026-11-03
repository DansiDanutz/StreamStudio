import { useEffect, useState } from 'react'
import { Stage } from './stage/Stage'
import { orderedScenes, useStage } from './stage/store'
import { SceneStrip } from './stage/SceneStrip'
import { Timeline } from './director/TimelinePanel'
import { IS_PROGRAM, openProgram, startController, useProgram } from './output/link'
import { ProgramView } from './output/ProgramView'
import { loadGestureManifest } from './avatar/gestures'
import { startAgentBridge } from './agent/bridge'
import { LibraryPanel } from './library/LibraryPanel'
import { initSceneSync } from './stage/sceneSync'
import { ScriptPanel } from './director/ScriptPanel'
import { fileToItem } from './stage/Library'
import { useDirector } from './director/store'
import { staleServerWarning } from './health'
import { guardCue, lipsMatch, type Cue } from './director/types'
import { ChannelsPage } from './channels/ChannelsPage'
import { EpisodePage } from './episode/EpisodePage'

const RENDER = new URLSearchParams(location.search).get('render') === '1'
const AUTOPLAY = new URLSearchParams(location.search).get('autoplay') === '1'
const EPISODE = new URLSearchParams(location.search).get('episode')

/** Output-clean view used by the headless renderer and (later) the live compositor. */
function RenderView() {
  useEffect(() => {
    document.documentElement.classList.add('render-mode')
    void loadGestureManifest()
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
  if (new URLSearchParams(location.search).has('channels')) return <ChannelsPage />
  if (EPISODE) return <EpisodePage id={EPISODE} />
  if (RENDER) return <RenderView />
  if (IS_PROGRAM) return <ProgramView />
  return <Editor />
}

function Editor() {
  const scene = useStage((s) => s.active())
  const orientation = useStage((s) => s.orientation)
  const guides = useStage((s) => s.guides)
  const selected = useStage((s) => s.selected)
  const { toggleOrientation, toggleMenu, toggleGuides, toggleLocked, toggleVisible, toggleCutout } = useStage.getState()
  const cutout = useStage((s) => s.cutout)
  const [health, setHealth] = useState<string>('…')
  const [serverWarning, setServerWarning] = useState<string | null>(null)
  const [bottom, setBottom] = useState<'scenes' | 'timeline'>('scenes')
  const [tab, setTab] = useState<'library' | 'script'>('library')
  const cue = useDirector((s) => s.cue)
  const live = useDirector((s) => s.live)
  const { applyCue, stop } = useDirector.getState()

  useEffect(() => { void initSceneSync(); void loadGestureManifest() }, [])
  useEffect(() => startController(), [])
  useEffect(() => startAgentBridge(), [])
  const program = useProgram()

  useEffect(() => {
    const check = () => fetch('/api/health').then((r) => r.json()).then((h) => {
      setHealth(`api ${h.version} · ${h.hw_encoders?.length ? `${h.hw_encoders.length} hw encoders` : 'no hw encoder'} · ${h.jobs.queued} queued`)
      setServerWarning(staleServerWarning(h))
    }).catch(() => setHealth(location.hostname.endsWith('vercel.app') ? 'hosted demo · no server' : 'api offline'))
    void check()
    const every = setInterval(check, 60_000) // a pull while the editor is open makes the server stale
    return () => clearInterval(every)
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
      if (/^[1-9]$/.test(k)) {
        const sc = orderedScenes(useStage.getState().scenes)[Number(k) - 1]
        if (sc) { if (!useDirector.getState().playing) stop(); useStage.getState().setActive(sc.id) }
      }
      const cues: Record<string, Cue> = { a: 'avatar', d: 'duo', s: 'split', c: 'content', f: 'full', p: 'pip' }
      if (cues[k]) applyCue(cues[k])
      if (k === 'escape') stop()
      if (k === 'z') applyCue('content', { x: 0.5, y: 0.5, scale: 1.6 })
      if (k === 'x') useDirector.getState().pushSketch(null)
      if (k === 't') { // Dan points at whatever is selected
        const st = useStage.getState()
        if (st.selectedMedia) useDirector.getState().pointAt(`media:${st.selectedMedia}`)
        else if (st.selected && st.selected !== 'avatar') useDirector.getState().pointAt(st.selected)
      }
      const sm = useStage.getState().selectedMedia
      if (sm && (k === 'delete' || k === 'backspace')) useStage.getState().removeMedia(sm)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, toggleOrientation, toggleMenu, toggleGuides, toggleLocked, toggleVisible, applyCue, stop])

  return (
    <div className="app">
      <header className="bar">
        <div className="brand">Stream<em>Studio</em></div>
        <div className="scene-now" title="Current scene (switch in the strip below, or keys 1–9)"><span>{scene.collection ?? 'Scene'}</span>{scene.name}</div>
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
        <div className="group">
          <button className={program.connected ? 'on' : ''} onClick={() => openProgram(orientation)} title="Open the clean output window: it mirrors this editor, plays the sound and records">
            {program.live ? '● LIVE' : program.recording ? `● REC ${Math.floor(program.seconds / 60)}:${String(program.seconds % 60).padStart(2, '0')}` : program.connected ? 'Program ↗ on' : 'Program ↗'}
          </button>
        </div>
        <div className="status">{health}</div>
        {serverWarning && <div className="server-warning" role="alert">{serverWarning}</div>}
      </header>
      <main className="work">
        <div className="stage-col">
          <Stage />
          <div className="bottom">
            <div className="bottom-tabs">
              <button className={bottom === 'scenes' ? 'on' : ''} onClick={() => setBottom('scenes')}>Scenes</button>
              <button className={bottom === 'timeline' ? 'on' : ''} onClick={() => setBottom('timeline')}>Timeline</button>
            </div>
            {bottom === 'scenes' ? <SceneStrip /> : <Timeline />}
          </div>
        </div>
        <aside className="side"><a href="?channels">Channels</a>
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'library'} className={tab === 'library' ? 'on' : ''} onClick={() => setTab('library')}>Library</button>
            <button role="tab" aria-selected={tab === 'script'} className={tab === 'script' ? 'on' : ''} onClick={() => setTab('script')}>Script</button>
          </div>
          {tab === 'library'
            ? <LibraryPanel onAddFile={(f) => { const it = fileToItem(f); useStage.getState().addMedia({ label: it.label, src: it.src, playback: it.playback, framed: it.framed, at: { x: 0.5, y: 0.45 }, w: it.w, aspect: it.aspect }) }} />
            : <ScriptPanel />}
        </aside>
      </main>
      <footer className="hints">
        Drag cards · corner handles resize · Alt = no snap · <b>O</b> orientation · <b>M</b> menu · <b>G</b> guides · <b>L</b> lock · <b>H</b> hide · <b>1–9</b> scenes · cues <b>A</b> avatar <b>D</b> duo <b>S</b> split <b>C</b> content <b>F</b> full <b>P</b> pip <b>Z</b> zoom <b>T</b> point at the selected card <b>Esc</b> reset · drag from Library to add a card · <b>Del</b> removes it
      </footer>
    </div>
  )
}
