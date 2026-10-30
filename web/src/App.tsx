import { useEffect, useState } from 'react'
import { PRESETS } from './stage/presets'
import { Stage } from './stage/Stage'
import { useStage } from './stage/store'

export default function App() {
  const scenes = useStage((s) => s.scenes)
  const activeId = useStage((s) => s.activeId)
  const scene = useStage((s) => s.active())
  const orientation = useStage((s) => s.orientation)
  const guides = useStage((s) => s.guides)
  const selected = useStage((s) => s.selected)
  const { toggleOrientation, toggleMenu, toggleGuides, setActive, saveAs, deleteScene, loadPreset, toggleLocked, toggleVisible } = useStage.getState()
  const [health, setHealth] = useState<string>('…')

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
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, toggleOrientation, toggleMenu, toggleGuides, toggleLocked, toggleVisible, loadPreset])

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
        </div>
        <div className="status">{health}</div>
      </header>
      <Stage />
      <footer className="hints">
        Drag cards · corner handles resize · Alt = no snap · <b>O</b> orientation · <b>M</b> menu · <b>G</b> guides · <b>L</b> lock · <b>H</b> hide · <b>1–6</b> presets
      </footer>
    </div>
  )
}
