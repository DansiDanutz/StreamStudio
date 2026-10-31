import { useEffect, useMemo, useRef, useState } from 'react'
import { useDirector } from './store'
import { useStage } from '../stage/store'
import { clipDurations, compileTimeline, type TimelineItem } from './timeline'

const TRACKS = ['Scene', 'Layout', 'Voice', 'Gesture', 'Table', 'Cards', 'Main'] as const
const fmt = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`

/** The script laid out in time: what is on screen, what is heard, and what actually plays after
 *  the rules. Click a block to preview that moment on stage; double-click to play from there. */
export function Timeline() {
  const script = useDirector((s) => s.script)
  const playing = useDirector((s) => s.playing)
  const current = useDirector((s) => s.current)
  const segStartedAt = useDirector((s) => s.segStartedAt)
  const scenes = useStage((s) => s.scenes)
  const activeId = useStage((s) => s.activeId)
  const cards = useStage((s) => s.active().media?.[s.orientation])
  const [pps, setPps] = useState(24) // pixels per second
  const [sel, setSel] = useState<number | null>(null)
  const [, bump] = useState(0)
  const startScene = useRef(activeId)
  const tl = useMemo(() => compileTimeline(script, scenes, startScene.current, cards ?? []), [script, scenes, cards]) // eslint-disable-line react-hooks/exhaustive-deps
  const head = useRef<HTMLDivElement>(null)

  // learn real clip lengths so the timeline matches what will play
  useEffect(() => {
    for (const it of tl.items) {
      if (!it.clip || !it.lips || clipDurations.has(it.clip)) continue
      const v = document.createElement('video')
      v.preload = 'metadata'
      v.onloadedmetadata = () => { if (Number.isFinite(v.duration)) { clipDurations.set(it.clip!, Math.round(v.duration * 1000)); bump((n) => n + 1) } }
      v.src = it.clip
    }
  }, [tl])

  // playhead
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const it = tl.items[current]
      if (head.current) {
        const ms = playing && it ? it.startMs + (performance.now() - segStartedAt) : sel !== null && tl.items[sel] ? tl.items[sel].startMs : 0
        head.current.style.transform = `translateX(${(Math.min(ms, tl.totalMs) / 1000) * pps}px)`
      }
      if (playing) raf = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [playing, current, segStartedAt, tl, pps, sel])

  const x = (ms: number) => (ms / 1000) * pps
  const pick = (i: number) => { setSel(i); useDirector.getState().preview(i) }
  const play = (i: number) => { setSel(i); useDirector.getState().play(i) }
  const block = (it: TimelineItem, from: number, to: number, cls: string, label: string, title: string) => (
    <div key={`${cls}${it.index}`} className={`tl-b ${cls} ${sel === it.index ? 'sel' : ''} ${playing && current === it.index ? 'air' : ''}`}
      style={{ left: x(from), width: Math.max(3, x(to - from) - 2) }} title={title}
      onClick={() => pick(it.index)} onDoubleClick={() => play(it.index)}>{label}</div>
  )
  // scene track: merge runs of the same scene
  const sceneRuns: { from: number; to: number; name: string; i: number }[] = []
  for (const it of tl.items) {
    const name = it.sceneInEffect?.name ?? '(current scene)'
    const last = sceneRuns.at(-1)
    if (last && last.name === name) last.to = it.endMs; else sceneRuns.push({ from: it.startMs, to: it.endMs, name, i: it.index })
  }
  const width = Math.max(x(tl.totalMs) + 40, 400)
  const s = sel !== null ? tl.items[sel] : null
  return (
    <div className="tl">
      <div className="tl-bar">
        <b>{fmt(tl.totalMs)}</b> · {tl.items.length} segments
        {tl.warnings > 0 && <span className="tl-warn">⚠ {tl.warnings} to check</span>}
        <label className="tl-zoom">zoom <input type="range" min={8} max={80} value={pps} onChange={(e) => setPps(Number(e.target.value))} /></label>
        {playing ? <button onClick={() => useDirector.getState().stop()}>■ Stop</button> : <button className="primary" onClick={() => play(sel ?? 0)}>▶ Play{sel ? ` from ${sel + 1}` : ''}</button>}
      </div>
      <div className="tl-body">
        <div className="tl-labels">{TRACKS.map((t) => <div key={t}>{t}</div>)}</div>
        <div className="tl-scroll">
          <div className="tl-grid" style={{ width }}>
            <div className="tl-ruler">
              {Array.from({ length: Math.ceil(tl.totalMs / 1000) + 1 }, (_, sec) => (
                <i key={sec} style={{ left: x(sec * 1000) }} className={sec % 5 === 0 ? 'major' : ''}>{sec % 5 === 0 ? fmt(sec * 1000) : ''}</i>
              ))}
            </div>
            <div className="tl-track">{sceneRuns.map((r) => (
              <div key={r.i} className="tl-b scene" style={{ left: x(r.from), width: Math.max(3, x(r.to - r.from) - 2) }} onClick={() => pick(r.i)} title={r.name}>{r.name}</div>
            ))}</div>
            <div className="tl-track">{tl.items.map((it) => block(it, it.startMs, it.endMs, `cue c-${it.plays} ${it.plays !== it.cue ? 'guarded' : ''}`, it.plays !== it.cue ? `${it.cue}→${it.plays}` : it.plays, it.plays !== it.cue ? `Asked ${it.cue}; plays ${it.plays} (lip-sync guard)` : it.plays))}</div>
            <div className="tl-track">{tl.items.map((it) => block(it, it.startMs + it.leadMs, it.endMs, `voice v-${it.voice}`, `${it.voice === 'clip' ? '👄 ' : it.voice === 'narration' ? '🎙 ' : '⏱ '}${it.text}`, `${it.voice === 'clip' ? 'Lip-synced clip' : it.voice === 'narration' ? 'Narration' : 'No voice yet (timed)'}: ${it.text}`))}</div>
            <div className="tl-track">{tl.items.filter((it) => it.gesture).map((it) => block(it, it.startMs, it.startMs + it.leadMs, `gest ${it.gesture!.clip ? '' : 'nocl'}`, `☝ ${it.gesture!.plays ?? 'auto'}`, `Gesture ${it.gesture!.asked}${it.target ? ` → ${it.target}` : ''}`))}</div>
            <div className="tl-track">{tl.items.filter((it) => it.table).map((it) => (
              <div key={it.index} className="tl-m tbl" style={{ left: x(it.startMs + 400) }} title={it.table} onClick={() => pick(it.index)}>◆ {it.table}</div>
            ))}</div>
            <div className="tl-track">{tl.items.filter((it) => it.media).map((it) => (
              <div key={it.index} className="tl-m crd" style={{ left: x(it.startMs + (it.leadMs ? it.leadMs * 0.55 : 300)) }} title={it.media} onClick={() => pick(it.index)}>▣ {it.media}</div>
            ))}</div>
            <div className="tl-track">{tl.items.filter((it) => it.visual || it.via || it.zoom).map((it) => (
              <div key={it.index} className="tl-m vis" style={{ left: x(it.startMs) }} onClick={() => pick(it.index)}
                title={[it.visual && `shows ${it.visual.replace(/^url:/, '')}`, it.via && `opens via ${it.via}`, it.zoom && `zoom ×${it.zoom.scale}`].filter(Boolean).join(' · ')}>
                {it.via ? '⧉ ' : ''}{it.visual ? it.visual.replace(/^url:https?:\/\//, '🌐 ').slice(0, 28) : it.zoom ? `🔍 ×${it.zoom.scale}` : `via ${it.via}`}
              </div>
            ))}</div>
            <div ref={head} className="tl-head" />
          </div>
        </div>
      </div>
      <div className="tl-detail">
        {s ? <>
          <b>{s.index + 1}.</b> {fmt(s.startMs)}–{fmt(s.endMs)} · <i>{s.text}</i>
          {s.warnings.map((w, i) => <div key={i} className="tl-warn">⚠ {w}</div>)}
        </> : <span className="muted">Click a block to see that moment on stage · double-click to play from there.</span>}
      </div>
    </div>
  )
}
