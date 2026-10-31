import { create } from 'zustand'
import { useStage } from '../stage/store'
import { useDirector } from '../director/store'

/** Editor ↔ Program window link (same origin, BroadcastChannel).
 *  The editor is the controller: it runs the Director and posts its state; the Program window is a
 *  clean 16:9/9:16 output that only mirrors it, plays the sound, and records. */

const CHANNEL = 'streamstudio.program'
const STAGE_KEYS = ['scenes', 'activeId', 'orientation', 'mainSrc', 'avatarSrc', 'cutout'] as const
const DIRECTOR_KEYS = ['script', 'playing', 'current', 'live', 'zoom', 'cue', 'guarded', 'avatarShape', 'gesture', 'sketches', 'table'] as const

type Msg =
  | { t: 'hello' }
  | { t: 'state'; stage: Record<string, unknown>; director: Record<string, unknown> }
  | { t: 'status'; recording: boolean; seconds: number; live?: boolean }
  | { t: 'bye' }

export const IS_PROGRAM = typeof location !== 'undefined' && new URLSearchParams(location.search).get('program') === '1'

/** What the editor knows about the Program window. */
export const useProgram = create<{ connected: boolean; recording: boolean; seconds: number; live: boolean }>(() => ({ connected: false, recording: false, seconds: 0, live: false }))

const pick = <T extends object, K extends readonly (keyof T)[]>(o: T, keys: K) =>
  Object.fromEntries(keys.map((k) => [k, o[k]])) as Record<string, unknown>

let ch: BroadcastChannel | null = null
const chan = () => (ch ??= typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel(CHANNEL) : null)

/** Editor side: post state on every change (coalesced per frame), answer hellos, track the Program. */
export function startController() {
  const c = chan()
  if (!c) return () => {}
  let queued = false
  let lastSeen = 0
  const post = () => {
    queued = false
    c.postMessage({ t: 'state', stage: pick(useStage.getState(), STAGE_KEYS), director: pick(useDirector.getState(), DIRECTOR_KEYS) } satisfies Msg)
  }
  const schedule = () => { if (!queued && useProgram.getState().connected) { queued = true; requestAnimationFrame(post) } }
  const u1 = useStage.subscribe(schedule)
  const u2 = useDirector.subscribe(schedule)
  c.onmessage = (e: MessageEvent<Msg>) => {
    const m = e.data
    if (m.t === 'hello') { lastSeen = Date.now(); useProgram.setState({ connected: true }); post() }
    if (m.t === 'status') { lastSeen = Date.now(); useProgram.setState({ connected: true, recording: m.recording, seconds: m.seconds, live: !!m.live }) }
    if (m.t === 'bye') useProgram.setState({ connected: false, recording: false })
  }
  const alive = setInterval(() => { if (useProgram.getState().connected && Date.now() - lastSeen > 5000) useProgram.setState({ connected: false, recording: false }) }, 2000)
  return () => { u1(); u2(); clearInterval(alive) }
}

/** Program side: say hello, mirror every state message, report recording status. */
export function startProgram(status: () => { recording: boolean; seconds: number; live: boolean }) {
  const c = chan()
  if (!c) return () => {}
  c.onmessage = (e: MessageEvent<Msg>) => {
    const m = e.data
    if (m.t !== 'state') return
    useStage.setState(m.stage as never)
    useDirector.setState(m.director as never)
  }
  c.postMessage({ t: 'hello' } satisfies Msg)
  const beat = setInterval(() => c.postMessage({ t: 'status', ...status() } satisfies Msg), 1000)
  const bye = () => c.postMessage({ t: 'bye' } satisfies Msg)
  window.addEventListener('beforeunload', bye)
  return () => { clearInterval(beat); window.removeEventListener('beforeunload', bye); bye() }
}

export const openProgram = (orientation: 'landscape' | 'portrait') => {
  const [w, h] = orientation === 'landscape' ? [1280, 760] : [460, 860]
  window.open('/?program=1', 'streamstudio-program', `popup,width=${w},height=${h}`)
}
