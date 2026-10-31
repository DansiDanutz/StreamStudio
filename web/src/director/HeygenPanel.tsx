import { useEffect, useState } from 'react'
import { useDirector } from './store'
import { MOTION, SOURCE_GESTURES, motionFor, pickGesture, SEATED, type GestureId } from '../avatar/gestures'
import type { Segment } from './types'

type Cfg = { has_key: boolean; api_key: string; avatar_id: string; voice_id: string; look_name: string }
type Look = { id: string; name: string; avatar_type: string; default_voice_id: string | null; preview_image_url: string | null }
type Account = { billing_type: string; premium_remaining: number | null; wallet_remaining: number | null; spending_usd: number | null }
type Item = { kind: 'segment' | 'gesture'; script?: string; silent_s?: number; motion?: string; gesture?: string; segment_id?: string }
type Plan = { seconds: number; clips: number; with_motion: number; ready: { clip: string; segment_id?: string }[]; jobs: { job_id: string; clip: string; segment_id?: string; kind: string }[] }

const api = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error((j as { detail?: string }).detail ?? `HTTP ${r.status}`)
  return j as T
}

/** The segment's gesture, if any, becomes part of its clip (Dan points while he talks). */
function segmentItem(s: Segment): Item {
  let motion: string | undefined
  if (s.gesture) {
    const to = useDirector.getState().targetRect(s.target ?? (s.via ? `hotspot:${s.via}` : 'main')) ?? { x: 0.7, y: 0.3, w: 0.2, h: 0.2 }
    const id = (s.gesture === 'auto' ? pickGesture(SEATED.landscape, to) : s.gesture) as GestureId
    motion = motionFor(id) || undefined
  }
  return { kind: 'segment', script: s.text, motion, segment_id: s.id }
}

/** Render Dan's clips on HeyGen: every script line without a clip, and the gesture set. Paid, so it
 *  always shows the estimate and the balance first and only renders on an explicit click. */
export function HeygenPanel({ onDone }: { onDone: () => void }) {
  const script = useDirector((s) => s.script)
  const { updateSegment } = useDirector.getState()
  const [cfg, setCfg] = useState<Cfg | null>(null)
  const [looks, setLooks] = useState<Look[]>([])
  const [acct, setAcct] = useState<Account | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [plan, setPlan] = useState<{ items: Item[]; est: Plan; label: string } | null>(null)
  const [running, setRunning] = useState<Record<string, string>>({}) // job id -> status text
  const offline = cfg === null && err?.startsWith('offline')

  const refresh = async () => {
    try {
      const c = await api<Cfg>('/api/heygen/config')
      setCfg(c)
      if (c.has_key) {
        const [l, a] = await Promise.all([api<Look[]>('/api/heygen/looks'), api<Account>('/api/heygen/account')])
        setLooks(l)
        setAcct(a)
        if (!c.avatar_id) {
          const dan = l.find((x) => /dan in his studio/i.test(x.name)) ?? l[0]
          if (dan) setCfg(await api<Cfg>('/api/heygen/config', { method: 'PUT', body: JSON.stringify({ avatar_id: dan.id, voice_id: dan.default_voice_id ?? '', look_name: dan.name }) }))
        }
      }
      setErr(null)
    } catch (e) {
      setErr(cfg ? (e as Error).message : 'offline: the HeyGen panel needs the StreamStudio server on the Mac Studio.')
    }
  }
  useEffect(() => { void refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const estimate = async (items: Item[], label: string) => {
    setErr(null)
    try { setPlan({ items, label, est: await api<Plan>('/api/heygen/render', { method: 'POST', body: JSON.stringify({ items }) }) }) } catch (e) { setErr((e as Error).message) }
  }
  const go = async () => {
    if (!plan) return
    try {
      const res = await api<Plan>('/api/heygen/render', { method: 'POST', body: JSON.stringify({ items: plan.items, confirm: true }) })
      for (const r of res.ready) if (r.segment_id) updateSegment(r.segment_id, { clip: r.clip, voice: 'clip', gesture: undefined })
      setPlan(null)
      for (const j of res.jobs) void follow(j)
    } catch (e) { setErr((e as Error).message) }
  }
  const follow = async (j: Plan['jobs'][number]) => {
    for (;;) {
      const job = await api<{ status: string; message: string; error: string | null; result: string | null }>(`/api/jobs/${j.job_id}`).catch(() => null)
      if (!job) return
      setRunning((m) => ({ ...m, [j.job_id]: job.status === 'done' ? 'ready' : job.status === 'error' ? `failed: ${job.error ?? ''}` : job.message || job.status }))
      if (job.status === 'done') {
        if (j.segment_id) updateSegment(j.segment_id, { clip: j.clip, voice: 'clip', gesture: undefined })
        void refresh()
        return
      }
      if (job.status === 'error' || job.status === 'cancelled') return
      await new Promise((r) => setTimeout(r, 4000))
    }
  }

  const needVoice = script.segments.filter((s) => s.text.trim() && (!s.clip || s.voice === 'narration'))
  const balance = acct?.premium_remaining ?? acct?.wallet_remaining
  return (
    <div className="wf hg">
      <div className="lbl">HeyGen</div>
      <div className="wf-title">Your lines and gestures, rendered as you</div>
      {offline ? <p className="wf-hint">{err}</p> : !cfg ? <p className="wf-hint">Loading…</p> : !cfg.has_key ? (
        <form className="wf-field" onSubmit={async (e) => {
          e.preventDefault()
          const k = String(new FormData(e.currentTarget).get('k') || '')
          try { setCfg(await api<Cfg>('/api/heygen/config', { method: 'PUT', body: JSON.stringify({ api_key: k }) })); void refresh() } catch (x) { setErr((x as Error).message) }
        }}>
          <span>Paste your HeyGen API key (<a href="https://platform.heygen.com/api-keys" target="_blank" rel="noreferrer">platform.heygen.com/api-keys</a>). It is saved on your Mac Studio only.</span>
          <input name="k" type="password" autoComplete="off" placeholder="HeyGen API key" />
          <button className="primary">Save key</button>
        </form>
      ) : (
        <>
          <label className="wf-field"><span>Look</span>
            <select value={cfg.avatar_id} onChange={async (e) => {
              const l = looks.find((x) => x.id === e.target.value)
              if (l) setCfg(await api<Cfg>('/api/heygen/config', { method: 'PUT', body: JSON.stringify({ avatar_id: l.id, voice_id: l.default_voice_id ?? '', look_name: l.name }) }))
            }}>
              {looks.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
          <p className="wf-hint">Key {cfg.api_key} · {balance != null ? `balance ${balance} ${acct?.premium_remaining != null ? 'premium credits' : ''}` : 'balance unknown'}</p>
          <div className="wf-actions">
            <button disabled={!needVoice.length} onClick={() => estimate(needVoice.map(segmentItem), `${needVoice.length} script line${needVoice.length === 1 ? '' : 's'}`)}>
              Voice my script ({needVoice.length})
            </button>
            <button onClick={() => estimate(SOURCE_GESTURES.map((g) => ({ kind: 'gesture', gesture: g, silent_s: 3, motion: `Mouth closed, not speaking. ${MOTION[g]}` })), 'the 8 gesture clips')}>
              Make the gesture clips (8)
            </button>
          </div>
          {plan && (
            <div className="hg-plan">
              <b>{plan.label}</b>
              {plan.est.clips === 0
                ? <p>Already rendered: nothing to pay. {plan.est.ready.length} clip(s) attached.</p>
                : <p>{plan.est.clips} clip{plan.est.clips === 1 ? '' : 's'} · ≈{plan.est.seconds}s of Avatar IV{plan.est.with_motion ? ` · ${plan.est.with_motion} with custom motion (about 2× cost)` : ''}.<br />
                    Guide: ≈1 premium credit per 3 s, about {Math.ceil((plan.est.seconds / 3) * (plan.est.with_motion ? 2 : 1))} credits{balance != null ? ` of your ${balance}` : ''}. HeyGen bills the exact amount.</p>}
              <div className="wf-actions">
                <button onClick={() => setPlan(null)}>Cancel</button>
                <button className="primary" onClick={go}>{plan.est.clips ? `Render ${plan.est.clips} clip${plan.est.clips === 1 ? '' : 's'}` : 'Attach'}</button>
              </div>
            </div>
          )}
          {Object.keys(running).length > 0 && (
            <ul className="hg-jobs">{Object.entries(running).map(([id, st]) => <li key={id}>{st}</li>)}</ul>
          )}
        </>
      )}
      {err && !offline && <p className="wf-hint warn">{err}</p>}
      <button onClick={onDone}>Back to the script</button>
    </div>
  )
}
