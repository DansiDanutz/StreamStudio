import { useEffect, useState } from 'react'

type State = 'idle' | 'working' | 'ready' | 'error'
const POLL_MS = 2000

/** Transcribe a finished take on the Mac Studio (whisper.cpp, free) and link its captions. */
export function TakeTranscript({ id, ready = false }: { id: string; ready?: boolean }) {
  const [state, setState] = useState<State>(ready ? 'ready' : 'idle')
  const [job, setJob] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!job) return
    const t = setInterval(async () => {
      try {
        const j = (await (await fetch(`/api/jobs/${job}`)).json()) as { status: string; error?: string }
        if (j.status === 'done') { setState('ready'); setJob(null) }
        else if (j.status === 'error' || j.status === 'cancelled') { setState('error'); setErr(j.error ?? 'Transcription failed.'); setJob(null) }
      } catch { /* keep trying */ }
    }, POLL_MS)
    return () => clearInterval(t)
  }, [job])

  const start = async () => {
    setErr(null)
    setState('working')
    try {
      const r = await fetch(`/api/recordings/${id}/transcribe`, { method: 'POST' })
      const body = await r.json()
      if (!r.ok) throw new Error(body.detail ?? 'Could not start the transcript.')
      setJob(body.job_id)
    } catch (e) { setState('error'); setErr((e as Error).message) }
  }

  if (state === 'ready') return <> · <a href={`/api/recordings/${id}.srt`} download>captions (.srt)</a></>
  if (state === 'working') return <> · transcribing…</>
  return <> · <button className="link" onClick={start}>Transcribe</button>{err && <span className="warn"> {err}</span>}</>
}
