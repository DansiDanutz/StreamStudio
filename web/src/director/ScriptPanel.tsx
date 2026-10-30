import { useState } from 'react'
import { propose } from './autoDirect'
import { useDirector } from './store'
import type { Cue } from './types'
import { tagUrl } from '../stage/media'
import { SKETCHES } from '../overlays/sketches'

const CUES: { id: Cue; label: string; hint: string }[] = [
  { id: 'avatar', label: 'Avatar', hint: 'You fill the frame. No card, no content.' },
  { id: 'duo', label: 'Duo', hint: 'You large, content small.' },
  { id: 'split', label: 'Split', hint: 'The scene as you laid it out.' },
  { id: 'content', label: 'Content', hint: 'Content maximized, you minimized.' },
  { id: 'full', label: 'Full', hint: 'Content fills the frame, you hidden.' },
]

/** Right-hand panel: the script as segments, each with its cue, clip and visual. */
export function ScriptPanel() {
  const script = useDirector((s) => s.script)
  const playing = useDirector((s) => s.playing)
  const current = useDirector((s) => s.current)
  const { updateSegment, addSegment, removeSegment, runAutoDirect, play, stop, setText } = useDirector.getState()
  const [raw, setRaw] = useState<string | null>(null)
  const total = script.segments.reduce((a, s) => a + s.durationMs, 0)

  return (
    <aside className="script">
      <div className="script-head">
        <div>
          <div className="lbl">Script</div>
          <div className="script-title">{script.title} · {script.segments.length} segments · ~{Math.round(total / 1000)}s</div>
        </div>
        <div className="group">
          <button onClick={() => setRaw(raw === null ? script.segments.map((s) => s.text).join('\n\n') : null)}>{raw === null ? 'Paste text' : 'Back'}</button>
          <button onClick={runAutoDirect} title="Propose a cue for every unpinned segment">Auto-direct</button>
          {playing
            ? <button className="danger" onClick={stop}>Stop</button>
            : <button className="primary" onClick={() => play(0)}>▶ Play</button>}
        </div>
      </div>

      {raw !== null ? (
        <div className="script-raw">
          <textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={18} spellCheck={false} />
          <button className="primary" onClick={() => { setText(raw); setRaw(null) }}>Split into segments</button>
        </div>
      ) : (
        <ol className="segs-list">
          {script.segments.map((s, i) => {
            const p = propose(s.text, i, script.segments.length)
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
                  <span>{(s.durationMs / 1000).toFixed(1)}s{s.clip ? ' · clip' : ' · no clip (timed)'}</span>
                  {s.zoom && <span>zoom ×{s.zoom.scale} @ {Math.round(s.zoom.x * 100)},{Math.round(s.zoom.y * 100)}</span>}
                  {!s.pinned && p.reasons.length > 0 && <span className="why">why: {p.reasons.join(', ')}</span>}
                  <select className="sketch-pick" value={s.sketch ?? ''} onChange={(e) => updateSegment(s.id, { sketch: e.target.value || undefined })} title="Desk sketch drawn when this segment starts">
                    <option value="">no sketch</option>
                    {Object.keys(SKETCHES).map((k) => <option key={k} value={k}>✎ {k}</option>)}
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
