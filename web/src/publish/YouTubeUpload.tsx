import { useCallback, useEffect, useState } from 'react'

interface Status { client: boolean; connected: boolean; channel: { id: string; title: string } | null; download_ready: boolean }
interface Take { id: string; mp4: boolean; transcript: boolean }
interface Job { status: string; progress: number; message: string; error?: string | null; result?: { url: string; studio: string } | null }

const POLL_MS = 2000
const PRIVACY = ['private', 'unlisted', 'public'] as const

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  const body = await r.json()
  if (!r.ok) throw new Error(body.detail ?? `HTTP ${r.status}`)
  return body as T
}

/** Upload a finished take with the kit's title and description. Private unless chosen otherwise. */
export function YouTubeUpload({ title, description }: { title: string; description: string }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [takes, setTakes] = useState<Take[]>([])
  const [take, setTake] = useState('')
  const [privacy, setPrivacy] = useState<(typeof PRIVACY)[number]>('private')
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [st, list] = await Promise.all([json<Status>('/api/youtube'), json<Take[]>('/api/recordings')])
      const ready = list.filter((t) => t.mp4)
      setStatus(st)
      setTakes(ready)
      setTake((cur) => cur || ready[0]?.id || '')
    } catch (e) { setErr((e as Error).message) }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  // the Google sign-in happens in another tab: look again when this window gets focus back
  useEffect(() => {
    const onFocus = () => { void refresh() }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refresh])

  useEffect(() => {
    if (!jobId) return
    const t = setInterval(async () => {
      try {
        const j = await json<Job>(`/api/jobs/${jobId}`)
        setJob(j)
        if (['done', 'error', 'cancelled'].includes(j.status)) setJobId(null)
      } catch { /* keep trying */ }
    }, POLL_MS)
    return () => clearInterval(t)
  }, [jobId])

  const importClient = async () => {
    setErr(null)
    try { await json('/api/youtube/client', { method: 'POST' }); await refresh() } catch (e) { setErr((e as Error).message) }
  }
  const upload = async () => {
    setErr(null)
    setJob(null)
    try {
      const r = await json<{ job_id: string }>(`/api/recordings/${take}/youtube`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ title, description, privacy }),
      })
      setJobId(r.job_id)
    } catch (e) { setErr((e as Error).message) }
  }

  let body
  if (!status) body = <p className="muted">Checking YouTube…</p>
  else if (!status.client) body = (
    <p>Download the Desktop OAuth client JSON from Google Cloud, then{' '}
      <button onClick={importClient} disabled={!status.download_ready}>Import it</button>
      {!status.download_ready && <span className="muted"> (none in Downloads yet)</span>}</p>
  )
  else if (!status.connected) body = (
    <p><a className="kit-btn" href="/api/youtube/connect" target="_blank" rel="noreferrer">Connect YouTube</a>{' '}
      <span className="muted">Sign in and click Allow, then come back here.</span></p>
  )
  else if (!takes.length) body = <p className="muted">Connected to {status.channel?.title ?? 'YouTube'}. Record a take first.</p>
  else body = (
    <div className="kit-yt-row">
      <select aria-label="Take" value={take} onChange={(e) => setTake(e.target.value)}>
        {takes.map((t) => <option key={t.id} value={t.id}>{t.id.slice(4)}{t.transcript ? ' · captions' : ''}</option>)}
      </select>
      <select aria-label="Privacy" value={privacy} onChange={(e) => setPrivacy(e.target.value as typeof privacy)}>
        {PRIVACY.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <button onClick={upload} disabled={!!jobId || !take}>Upload to {status.channel?.title ?? 'YouTube'}</button>
    </div>
  )

  return (
    <div className="kit-field kit-yt">
      <span>YouTube{status?.channel ? ` · ${status.channel.title}` : ''}</span>
      {body}
      {job && job.status !== 'done' && job.status !== 'error' && <p className="muted">{job.message || 'Queued'} · {Math.round(job.progress * 100)}%</p>}
      {job?.status === 'done' && job.result && <p>Uploaded ({privacy}): <a href={job.result.studio} target="_blank" rel="noreferrer">open in YouTube Studio</a></p>}
      {job?.status === 'error' && <p className="warn">{job.error?.split('\n')[0] ?? 'Upload failed.'}</p>}
      {err && <p className="warn">{err}</p>}
    </div>
  )
}
