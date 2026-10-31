import { useEffect, useRef, useState } from 'react'
import { Stage } from '../stage/Stage'
import { useStage } from '../stage/store'
import { startProgram } from './link'
import { Recorder, uploadTake, type Take } from './recorder'

const rec = new Recorder()
const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

/** The Program window: clean output that mirrors the editor, plays the sound, and records itself. */
export function ProgramView() {
  const [recording, setRecording] = useState(false)
  const [secs, setSecs] = useState(0)
  const [last, setLast] = useState<{ take: Take; url: string; id: string | null; mp4: boolean } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [linked, setLinked] = useState(false)
  const orientation = useStage((s) => s.orientation)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    document.documentElement.classList.add('render-mode', 'program-mode')
    document.title = 'Program · StreamStudio'
    const off = startProgram(() => ({ recording: rec.recording, seconds: rec.seconds }))
    const unsub = useStage.subscribe(() => setLinked(true))
    const t = setInterval(() => setSecs(rec.seconds), 500)
    return () => { off(); unsub(); clearInterval(t) }
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

  const start = async () => {
    setErr(null)
    const base = root.current?.querySelector('.base')
    if (!base) return
    try { await rec.start(base); setRecording(true) } catch { setErr('Recording needs permission to capture this tab: pick "This tab" and allow audio.') }
  }
  const stop = async () => {
    const take = await rec.stop()
    setRecording(false)
    const url = URL.createObjectURL(take.blob)
    setLast({ take, url, id: null, mp4: false })
    const id = await uploadTake(take)
    setLast({ take, url, id, mp4: false })
  }

  return (
    <div className={`program ${orientation}`} ref={root}>
      <div className="program-bar">
        <b>Program</b>
        <span className={`dot ${linked ? 'on' : ''}`}>{linked ? 'linked to the editor' : 'waiting for the editor…'}</span>
        {recording
          ? <button className="rec on" onClick={stop}>■ Stop · {fmt(secs)}</button>
          : <button className="rec" onClick={start} disabled={!linked}>● Record</button>}
        {rec.recording && !rec.cropped && <span className="warn">recording the whole tab (crop not supported in this browser)</span>}
        {err && <span className="warn">{err}</span>}
        {last && !recording && (
          <span className="take">
            Take {fmt(last.take.seconds)} ·{' '}
            <a href={last.url} download={`streamstudio-take.${last.take.mime.includes('mp4') ? 'mp4' : 'webm'}`}>download</a>
            {last.id ? (last.mp4 ? <> · <a href={`/api/recordings/${last.id}.mp4`}>MP4 ready</a></> : ' · saved on Mac Studio, making the MP4…') : ' · no server: download it'}
          </span>
        )}
        <button onClick={() => document.documentElement.requestFullscreen?.()}>Fullscreen</button>
      </div>
      <div className="program-stage"><Stage /></div>
    </div>
  )
}
