/** The Episode page (`?episode=<id>`): the scenes with their errors, the three buttons
 *  (Approve script, Approve budget with the cost screen, Publish), and Advance when the factory
 *  needs Dan. Polls the record every 5 s while the worker is busy. Usable on a phone over the
 *  tailnet (390 px wide). Stage 2 adds warnings, inline edit, per-scene chips and the schedule. */

import { useCallback, useEffect, useState } from 'react'
import * as api from './api'
import { progressLabel, primaryAction, usd, type Episode, type Estimate } from './api'

const POLL_MS = 5_000
const BUSY: api.EpisodeStatus[] = ['budget_approved', 'in_progress']

export function EpisodePage({ id }: { id: string }) {
  const [ep, setEp] = useState<Episode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [est, setEst] = useState<Estimate | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try { setEp(await api.getEpisode(id)); setError(null) } catch (e) { setError(String((e as Error).message)) }
  }, [id])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!ep || !BUSY.includes(ep.status)) return
    const t = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(t)
  }, [ep, load])

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try { await fn(); setError(null) } catch (e) { setError(String((e as Error).message)) } finally { setBusy(false) }
    await load()
  }

  if (error && !ep) return <div className="episode"><p className="episode-error">{error}</p></div>
  if (!ep) return <div className="episode"><p>Loading…</p></div>

  const action = primaryAction(ep.status)
  const errors = ep.validation.errors
  const errorCount = Object.values(errors).reduce((n, v) => n + v.length, 0)

  return (
    <div className="episode">
      <header className="episode-head">
        <div>
          <div className="episode-kicker">Episode · {ep.id}</div>
          <h1>{ep.title}</h1>
          <div className="episode-progress">{progressLabel(ep)}</div>
        </div>
        <div className="episode-actions">
          {action === 'approve-script' && (
            <button disabled={busy || errorCount > 0} onClick={() => run(() => api.approveScript(ep.id))}>Approve script</button>
          )}
          {action === 'approve-budget' && !est && (
            <button disabled={busy} onClick={() => run(async () => setEst(await api.estimate(ep.id)))}>Approve budget…</button>
          )}
          {action === 'publish' && (
            <button disabled={busy} onClick={() => run(() => api.publish(ep.id))}>Publish now</button>
          )}
          {action === 'advance' && (
            <button disabled={busy} onClick={() => run(() => api.advance(ep.id))}>Advance</button>
          )}
          {action === 'purge' && (
            <button disabled={busy} onClick={() => run(() => api.purge(ep.id))}>Purge workings</button>
          )}
        </div>
      </header>

      {error && <p className="episode-error">{error}</p>}

      {ep.status === 'needs_dan' && (
        <section className="episode-needs">
          <strong>Needs you.</strong> {ep.last_log ?? 'The factory stopped.'} Fix the cause, then press Advance.
        </section>
      )}

      {est && ep.status === 'script_approved' && (
        <section className="episode-cost">
          <h2>This render costs</h2>
          <dl>
            <dt>Clips to render</dt><dd>{est.clips} ({est.ready} already rendered)</dd>
            <dt>Seconds</dt><dd>{est.seconds.toFixed(1)} s{est.with_motion ? `, ${est.with_motion} with motion` : ''}</dd>
            <dt>Cost</dt><dd>{usd(est.usd)}</dd>
            <dt>Re-render allowance</dt><dd>{est.allowance.attempts} attempts, up to {usd(est.allowance.usd)}</dd>
            <dt>This month after</dt><dd className={est.over_ceiling ? 'over' : ''}>{usd(est.month_total_after_usd)} of {usd(est.ceiling_usd)} ceiling</dd>
            {est.wallet_remaining_usd !== null && <><dt>HeyGen wallet after</dt><dd>{usd(est.wallet_remaining_usd - est.usd)}</dd></>}
          </dl>
          {est.over_ceiling && <p className="episode-error">Over the monthly ceiling: raise it in the settings or wait for next month.</p>}
          <div className="episode-actions">
            <button disabled={busy || est.over_ceiling} className="primary" onClick={() => run(async () => { await api.approveBudget(ep.id, est.confirm_token); setEst(null) })}>
              Approve {usd(est.usd + est.allowance.usd)}
            </button>
            <button disabled={busy} onClick={() => setEst(null)}>Not now</button>
          </div>
          <p className="episode-muted">The token expires in {Math.round(est.expires_in_s / 60)} minutes. Nothing is paid until you approve.</p>
        </section>
      )}

      {ep.outputs.youtube_video_id && (
        <section className="episode-video">
          <a href={`https://youtu.be/${ep.outputs.youtube_video_id}`} target="_blank" rel="noreferrer">youtu.be/{ep.outputs.youtube_video_id}</a>
          {' · '}
          <a href={`https://studio.youtube.com/video/${ep.outputs.youtube_video_id}/edit`} target="_blank" rel="noreferrer">YouTube Studio</a>
        </section>
      )}

      <section className="episode-scenes">
        <h2>Scenes <span className="episode-muted">{ep.script.scenes.length}{errorCount ? ` · ${errorCount} error${errorCount === 1 ? '' : 's'}` : ''}</span></h2>
        <ol>
          {ep.script.scenes.map((sc) => {
            const st = ep.scenes_state[sc.id] ?? {}
            const errs = errors[sc.id] ?? []
            return (
              <li key={sc.id} className={errs.length ? 'bad' : ''}>
                <div className="scene-row">
                  <span className="scene-id">{sc.id}</span>
                  <span className="scene-kind">{sc.kind === 'card' ? 'card' : 'avatar'}{sc.question ? ` · Q${sc.question}` : ''}{sc.reveal ? ' · reveal' : ''}</span>
                  <span className="scene-state">{st.composed_hash ? 'composed' : st.clip ? 'clip ready' : st.take ? `take ${st.take}` : ''}</span>
                </div>
                <div className="scene-text">{sc.text || sc.voice}</div>
                {sc.voice && sc.text && sc.voice !== sc.text && <div className="scene-voice">voice: {sc.voice}</div>}
                {errs.map((e) => <div key={e} className="scene-error">{e}</div>)}
              </li>
            )
          })}
        </ol>
      </section>

      {ep.budget.approved_at && (
        <section className="episode-budget">
          <h2>Budget</h2>
          <div className="episode-muted">
            Approved {ep.budget.approved_at}: {ep.budget.clips} clips, {usd(ep.budget.usd)} plus {usd(ep.budget.allowance.usd)} allowance.
            Spent so far: {ep.budget.spent.renders} renders, {usd(ep.budget.spent.usd)}.
          </div>
        </section>
      )}

      <section className="episode-log">
        <h2>Log</h2>
        <ul>
          {ep.log.slice(-12).reverse().map((l, i) => (
            <li key={i}><span className="episode-muted">{l.at.slice(11, 19)}</span> {l.scene ? `${l.scene}: ` : ''}{l.message}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
