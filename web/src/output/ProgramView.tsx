import { useEffect, useRef, useState } from 'react'
import { Stage } from '../stage/Stage'
import { useStage } from '../stage/store'
import { startProgram } from './link'
import { loadGestureManifest } from '../avatar/gestures'
import { LiveLink, Recorder, uploadTake, type Take } from './recorder'
import { TakeTranscript } from './TakeTranscript'

const rec = new Recorder()
const live = new LiveLink()
const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

/** The Program window: clean output that mirrors the editor, plays the sound, and records itself. */
export function ProgramView() {
  const [frameRate, setFrameRate] = useState<30 | 60>(30)
  const [recording, setRecording] = useState(false)
  const [secs, setSecs] = useState(0)
  const [last, setLast] = useState<{ take: Take; url: string; id: string | null; mp4: boolean } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [linked, setLinked] = useState(false)
  const [onAir, setOnAir] = useState(false)
  const [liveCfg, setLiveCfg] = useState<{ rtmp_url: string; stream_key: string; has_key: boolean } | null>(null)
  const [showCfg, setShowCfg] = useState(false)
  const orientation = useStage((s) => s.orientation)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    document.documentElement.classList.add('render-mode', 'program-mode')
    document.title = 'Program · StreamStudio'
    void loadGestureManifest()
    const off = startProgram(() => ({ recording: rec.recording, seconds: rec.seconds, live: live.on }))
    fetch('/api/live/config').then((r) => (r.ok ? r.json() : null)).then(setLiveCfg).catch(() => setLiveCfg(null))
    live.onEnd = (reason) => { setOnAir(false); rec.setTap(null); if (reason) setErr(reason) }
    rec.onTake = async (take) => {
      if (live.on) { rec.setTap(null); await live.close(); setOnAir(false) }
      setRecording(false)
      const url = URL.createObjectURL(take.blob)
      setLast({ take, url, id: null, mp4: false })
      const id = await uploadTake(take)
      setLast({ take, url, id, mp4: false })
    }
    const unsub = useStage.subscribe(() => setLinked(true))
    const t = setInterval(() => setSecs(rec.seconds), 500)
    return () => { rec.onTake = null; off(); unsub(); clearInterval(t) }
  }, [])

  // Poll the server until the MP4 is ready.
  useEffect(() => {
    if (!last?.id || last.mp4) return
    const t = setInterval(async () => {
      try {
        const list = (await (await fetch('/api/recordings')).json()) as { id: string; mp4: boolean }[]
        if (list.find((r) => r.id === last.id)?.mp4) setLast((l) => (l ? { ...l, mp4: true } : l))
      } catch { /* keep trying */ }
    }, 2000)
    return () => clearInterval(t)
  }, [last])

  const start = async (timeslice = 1000) => {
    setErr(null)
    const base = root.current?.querySelector('.base')
    if (!base) return
    try { await rec.start(base, timeslice, !!liveCfg, frameRate); setRecording(true) } catch { setErr('Recording needs permission to capture this tab: pick "This tab" and allow audio.') }
  }
  const goLive = async () => {
    setErr(null)
    if (!liveCfg?.has_key) { setShowCfg(true); return }
    try {
      await live.open()
      if (!rec.recording) await start(500) // live always records too
      if (!rec.recording) { await live.close(); return }
      rec.setTap((b) => live.send(b))
      setOnAir(true)
    } catch (e) { setErr((e as Error).message) }
  }
  const endLive = async () => { rec.setTap(null); await live.close(); setOnAir(false) }
  const saveCfg = async (form: FormData) => {
    const body: Record<string, string> = { rtmp_url: String(form.get('url') || 'rtmp://a.rtmp.youtube.com/live2') }
    const key = String(form.get('key') || '')
    if (key) body.stream_key = key
    const r = await fetch('/api/live/config', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    if (r.ok) { setLiveCfg(await r.json()); setShowCfg(false); setErr(null) } else setErr((await r.json()).detail ?? 'Could not save.')
  }
  const stop = async () => {
    if (live.on) await endLive()
    await rec.stop()

  }

  return (
    <div className={`program ${orientation}`} ref={root}>
      <div className="program-bar">
        <b>Program</b>
        <span className={`dot ${linked ? 'on' : ''}`}>{linked ? 'linked to the editor' : 'waiting for the editor…'}</span>
        <label>Capture rate <select value={frameRate} disabled={recording}
          onChange={e => setFrameRate(e.target.value === '60' ? 60 : 30)}>
          <option value="30">30 fps</option><option value="60">60 fps</option>
        </select></label>
        {recording
          ? <button className="rec on" onClick={stop}>■ Stop · {fmt(secs)}</button>
          : <button className="rec" onClick={() => start(500)} disabled={!linked}>● Record</button>}
        {onAir
          ? <button className="live on" onClick={endLive}>■ End live</button>
          : <button className="live" onClick={goLive} disabled={!linked || !liveCfg} title={liveCfg ? 'Stream to YouTube (also records)' : 'Needs the StreamStudio server'}>◉ Go live</button>}
        {liveCfg && <button className="cfg" onClick={() => setShowCfg(!showCfg)} title="YouTube stream key">⚙</button>}
        {rec.recording && !rec.cropped && <span className="warn">recording the whole tab (crop not supported in this browser)</span>}
        {err && <span className="warn">{err}</span>}
        {last && !recording && (
          <span className="take">
            Take {fmt(last.take.seconds)} ·{' '}
            <a href={last.url} download={`streamstudio-take.${last.take.mime.includes('mp4') ? 'mp4' : 'webm'}`}>download</a>
            {last.id ? (last.mp4 ? <> · <a href={`/api/recordings/${last.id}.mp4`}>MP4 ready</a><TakeTranscript id={last.id} /></> : ' · saved on Mac Studio, making the MP4…') : ' · no server: download it'}
          </span>
        )}
        <button onClick={() => document.documentElement.requestFullscreen?.()}>Fullscreen</button>
      </div>
      {showCfg && (
        <form className="live-cfg" onSubmit={(e) => { e.preventDefault(); void saveCfg(new FormData(e.currentTarget)) }}>
          <b>YouTube live</b>
          <p>In YouTube Studio → Go live → Stream, copy the <i>Stream key</i>. It is saved on your Mac Studio only and never shown again in full.</p>
          <label>Server <input name="url" defaultValue={liveCfg?.rtmp_url ?? 'rtmp://a.rtmp.youtube.com/live2'} /></label>
          <label>Stream key <input name="key" type="password" autoComplete="off" placeholder={liveCfg?.has_key ? `saved (${liveCfg.stream_key}), paste to replace` : 'xxxx-xxxx-xxxx-xxxx-xxxx'} /></label>
          <div><button type="button" onClick={() => setShowCfg(false)}>Cancel</button> <button className="primary">Save</button></div>
        </form>
      )}
      <div className="program-stage"><Stage /></div>
    </div>
  )
}
