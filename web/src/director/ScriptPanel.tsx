import { useState } from 'react'
import { propose } from './autoDirect'
import { useDirector } from './store'
import { guardCue, lipsMatch, type Cue } from './types'
import { tagUrl } from '../stage/media'
import { SKETCHES } from '../overlays/sketches'
import { WorkflowPicker } from './WorkflowPicker'
import { HeygenPanel } from './HeygenPanel'
import { GESTURES } from '../avatar/gestures'
import { HOTSPOTS } from '../stage/hotspots'
import { orderedScenes, useStage } from '../stage/store'

const CUES: { id: Cue; label: string; hint: string }[] = [
  { id: 'avatar', label: 'Avatar', hint: 'You fill the frame. No card, no content.' },
  { id: 'duo', label: 'Duo', hint: 'You large, content small.' },
  { id: 'split', label: 'Split', hint: 'The scene as you laid it out.' },
  { id: 'content', label: 'Content', hint: 'Content maximized, you minimized.' },
  { id: 'full', label: 'Full', hint: 'Content fills the frame, you hidden.' },
  { id: 'pip', label: 'Pip', hint: 'You small (circle or portrait) over the studio. Safe with any voice.' },
]

/** Right-hand panel: the script as segments, each with its cue, clip and visual. */
export function ScriptPanel() {
  const script = useDirector((s) => s.script)
  const playing = useDirector((s) => s.playing)
  const current = useDirector((s) => s.current)
  const shape = useDirector((s) => s.avatarShape)
  const { updateSegment, addSegment, removeSegment, runAutoDirect, play, stop, setText, setAvatarShape } = useDirector.getState()
  const [raw, setRaw] = useState<string | null>(null)
  const [flows, setFlows] = useState(false)
  const [hg, setHg] = useState(false)
  const scenes = useStage((s) => s.scenes)
  const media = useStage((s) => s.active().media?.[s.orientation])
  const targets = [
    { value: 'main', label: 'Main card' },
    ...HOTSPOTS.map((h) => ({ value: `hotspot:${h.id}`, label: h.label })),
    ...(media ?? []).map((m) => ({ value: `media:${m.label}`, label: `Card: ${m.label}` })),
  ]
  const total = script.segments.reduce((a, s) => a + s.durationMs, 0)

  return (
    <aside className="script">
      <div className="script-head">
        <div>
          <div className="lbl">Script</div>
          <div className="script-title">{script.title} · {script.segments.length} segments · ~{Math.round(total / 1000)}s</div>
        </div>
        <div className="group">
          <button onClick={() => { setHg(!hg); setFlows(false); setRaw(null) }} className={hg ? 'on' : ''} title="Render your lines and gestures on HeyGen">HeyGen</button>
          <button onClick={() => { setFlows(!flows); setHg(false); setRaw(null) }} className={flows ? 'on' : ''} title="Ready-made script shapes">Workflows</button>
          <button onClick={() => setRaw(raw === null ? script.segments.map((s) => s.text).join('\n\n') : null)}>{raw === null ? 'Paste text' : 'Back'}</button>
          <button onClick={runAutoDirect} title="Propose a cue for every unpinned segment">Auto-direct</button>
          <button onClick={() => setAvatarShape(shape === 'circle' ? 'portrait' : 'circle')} title="Shape of your small card">{shape === 'circle' ? '◯ circle' : '▯ portrait'}</button>
          {playing
            ? <button className="danger" onClick={stop}>Stop</button>
            : <button className="primary" onClick={() => play(0)}>▶ Play</button>}
        </div>
      </div>

      {hg ? <HeygenPanel onDone={() => setHg(false)} /> : flows ? <WorkflowPicker onDone={() => setFlows(false)} /> : raw !== null ? (
        <div className="script-raw">
          <textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={18} spellCheck={false} />
          <button className="primary" onClick={() => { setText(raw); setRaw(null) }}>Split into segments</button>
        </div>
      ) : (
        <ol className="segs-list">
          {script.segments.map((s, i) => {
            const p = propose(s.text, i, script.segments.length)
            const ok = lipsMatch(s)
            const shown = guardCue(s.cue, s)
            return (
              <li key={s.id} className={`seg ${i === current ? 'on-air' : ''}`}>
                <div className="seg-top">
                  <span className="seg-n">{i + 1}</span>
                  <div className="cues" role="group" aria-label="Cue">
                    {CUES.map((c) => (
                      <button key={c.id} title={c.hint} className={s.cue === c.id ? 'on' : ''}
                        onClick={() => updateSegment(s.id, { cue: c.id, pinned: true, zoom: c.id === 'content' ? s.zoom : undefined })}>{c.label}</button>
                    ))}
                  </div>
                  <button className="icon" title={s.pinned ? 'Pinned: auto-direct keeps this cue' : 'Auto'} onClick={() => updateSegment(s.id, { pinned: !s.pinned })}>{s.pinned ? '📌' : '✦'}</button>
                  <button className="icon" title="Play from here" onClick={() => play(i)}>▶</button>
                  <button className="icon" title="Remove" onClick={() => removeSegment(s.id)}>✕</button>
                </div>
                <textarea value={s.text} rows={Math.min(6, Math.max(2, Math.ceil(s.text.length / 60)))} spellCheck={false}
                  onChange={(e) => updateSegment(s.id, { text: e.target.value })} />
                <div className="seg-meta">
                  <span className={`lips ${ok ? 'ok' : 'no'}`} title={ok ? 'Voice is the clip’s own lip-synced audio: full-frame face allowed' : 'Lips do not match this voice: your face stays in the small card'}>
                    lips {ok ? '✓' : '✕'}{shown !== s.cue ? ` · plays as ${shown}` : ''}
                  </span>
                  <span>{(s.durationMs / 1000).toFixed(1)}s{s.clip ? ' · clip' : ' · no clip (timed)'}</span>
                  <select value={s.voice ?? 'clip'} title="Voice source" onChange={(e) => updateSegment(s.id, { voice: e.target.value as 'clip' | 'narration' })}>
                    <option value="clip">voice: clip</option>
                    <option value="narration">voice: narration</option>
                  </select>
                  {s.voice === 'narration' && <label className="file">audio{s.audio ? ' ✓' : ''}<input type="file" accept="audio/*,video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) updateSegment(s.id, { audio: URL.createObjectURL(f) }) }} /></label>}
                  {s.zoom && <span>zoom ×{s.zoom.scale} @ {Math.round(s.zoom.x * 100)},{Math.round(s.zoom.y * 100)}</span>}
                  {!s.pinned && p.reasons.length > 0 && <span className="why">why: {p.reasons.join(', ')}</span>}
                  <input className="table-ev" value={s.table ?? ''} placeholder="table: arrive:claude" title="Table event: arrive:<id> · react:<ids|all> · dim:all · clear"
                    onChange={(e) => updateSegment(s.id, { table: e.target.value || undefined })} />
                  <select className="sketch-pick" value={s.sketch ?? ''} onChange={(e) => updateSegment(s.id, { sketch: e.target.value || undefined })} title="Desk sketch drawn when this segment starts">
                    <option value="">no sketch</option>
                    {Object.keys(SKETCHES).map((k) => <option key={k} value={k}>✎ {k}</option>)}
                  </select>
                  <select value={s.scene ?? ''} title="Scene this segment switches to" onChange={(e) => updateSegment(s.id, { scene: e.target.value || undefined })}>
                    <option value="">scene: keep</option>
                    {orderedScenes(scenes).map((sc) => <option key={sc.id} value={sc.id}>▦ {sc.name}</option>)}
                  </select>
                  <select value={s.gesture ?? ''} title="Gesture at the start of the segment" onChange={(e) => updateSegment(s.id, { gesture: e.target.value || undefined })}>
                    <option value="">no gesture</option>
                    <option value="auto">☝ point at target (auto)</option>
                    {GESTURES.map((g) => <option key={g.id} value={g.id}>☝ {g.label}</option>)}
                  </select>
                  {(s.gesture || s.via) && <select value={s.target ?? ''} title="What the presenter points at" onChange={(e) => updateSegment(s.id, { target: e.target.value || undefined })}>
                    <option value="">target: {s.via ? 'the hotspot' : 'Main card'}</option>
                    {targets.map((t) => <option key={t.value} value={t.value}>→ {t.label}</option>)}
                  </select>}
                  <select value={s.via ?? ''} title="The Main card opens out of / closes into this place in the studio" onChange={(e) => updateSegment(s.id, { via: e.target.value || undefined })}>
                    <option value="">no monitor transition</option>
                    {HOTSPOTS.filter((h) => h.id !== 'table').map((h) => <option key={h.id} value={h.id}>⧉ via {h.label}</option>)}
                  </select>
                  <label className="file">clip<input type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) updateSegment(s.id, { clip: tagUrl(f) }) }} /></label>
                  <label className="file">visual<input type="file" accept="video/*,image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) updateSegment(s.id, { visual: tagUrl(f) }) }} /></label>
                </div>
              </li>
            )
          })}
          <li><button className="add" onClick={addSegment}>+ segment</button></li>
        </ol>
      )}
    </aside>
  )
}
