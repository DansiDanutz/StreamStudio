import { useStage, orderedScenes } from './store'
import type { Scene } from './types'

/** Keeps the scene library on the Mac Studio (/api/scenes). The browser copy (localStorage) is the
 *  fallback: with no server (the hosted demo, or the API down) scenes stay local.
 *  Server wins on load; afterwards every change is written back, debounced per scene. */

const DEBOUNCE_MS = 500
type Fetch = typeof fetch

export function sceneBody(s: Scene, position: number) {
  const { id: _id, name, collection, ...data } = s
  return { name, collection: collection ?? 'Talk', position, data }
}

export async function initSceneSync(f: Fetch = fetch): Promise<'server' | 'local'> {
  const st = useStage.getState()
  let remote: Scene[]
  try {
    const r = await f('/api/scenes')
    if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) throw new Error(String(r.status))
    remote = (await r.json()) as Scene[]
  } catch {
    st.setSync('local')
    return 'local'
  }
  if (remote.length) st.replaceScenes(remote)
  const pending = new Map<string, ReturnType<typeof setTimeout>>()
  let inflight = 0
  const put = (s: Scene, pos: number) => {
    inflight++
    useStage.getState().setSync('saving')
    f(`/api/scenes/${encodeURIComponent(s.id)}`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(sceneBody(s, pos)) })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)) })
      .then(() => { if (--inflight === 0) useStage.getState().setSync('server') })
      .catch(() => { inflight--; useStage.getState().setSync('error') })
  }
  const schedule = (s: Scene, pos: number) => {
    clearTimeout(pending.get(s.id))
    pending.set(s.id, setTimeout(() => { pending.delete(s.id); put(s, pos) }, DEBOUNCE_MS))
  }
  // An empty server library is seeded with what this browser has.
  let prev: Scene[] = remote.length ? useStage.getState().scenes : []
  const pushDiff = (scenes: Scene[]) => {
    const order = orderedScenes(scenes)
    const prevPos = new Map(orderedScenes(prev).map((s, i) => [s.id, { s, i }]))
    order.forEach((s, i) => { const p = prevPos.get(s.id); if (!p || p.s !== s || p.i !== i) schedule(s, i) })
    for (const id of prevPos.keys()) {
      if (!scenes.some((s) => s.id === id)) {
        clearTimeout(pending.get(id))
        f(`/api/scenes/${encodeURIComponent(id)}`, { method: 'DELETE' }).catch(() => useStage.getState().setSync('error'))
      }
    }
    prev = scenes
  }
  pushDiff(useStage.getState().scenes)
  useStage.subscribe((s) => { if (s.scenes !== prev) pushDiff(s.scenes) })
  useStage.getState().setSync('server')
  return 'server'
}
