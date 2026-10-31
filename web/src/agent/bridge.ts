/** Connects the open editor to the agent bus: publishes the library, runs agent actions on the
 *  stage, and reports what is on stage. Only the editor (the controller) runs this. */

import { buildCatalog } from './catalog'
import { useStage } from '../stage/store'
import { useDirector } from '../director/store'
import { useProgram } from '../output/link'
import { WORKFLOWS, workflowDefaults } from '../director/workflows'
import { LIBRARY } from '../stage/Library'
import { toUrlSource } from '../stage/media'
import type { AvatarShape, Cue, Zoom } from '../director/types'
import type { GestureId } from '../avatar/gestures'

type Args = Record<string, unknown>
const str = (v: unknown, name: string) => { if (typeof v !== 'string' || !v) throw new Error(`'${name}' is required`); return v }
const CUES: Cue[] = ['avatar', 'duo', 'split', 'content', 'full', 'pip']

export const EXECUTORS: Record<string, (a: Args) => unknown> = {
  'scene.activate': (a) => {
    const id = str(a.id, 'id').replace(/^scene:/, '')
    if (!useStage.getState().scenes.some((s) => s.id === id)) throw new Error(`no scene ${id}`)
    if (!useDirector.getState().playing) useDirector.getState().stop()
    useStage.getState().setActive(id)
    return { scene: id }
  },
  'scene.new': (a) => { useStage.getState().newScene(str(a.template, 'template').replace(/^template:/, ''), a.collection as string | undefined); return { scene: useStage.getState().activeId } },
  'cue.apply': (a) => {
    const cue = str(a.cue, 'cue') as Cue
    if (!CUES.includes(cue)) throw new Error(`cue must be one of ${CUES.join(', ')}`)
    useDirector.getState().applyCue(cue, (a.zoom as Zoom) ?? null, 600, true) // the lip-sync guard is never bypassed for agents
    return { cue }
  },
  'point.at': (a) => {
    const id = useDirector.getState().pointAt(str(a.target, 'target').replace(/^target:/, ''))
    if (!id) throw new Error(`nothing to point at for ${String(a.target)}`)
    return { gesture: id }
  },
  'gesture.play': (a) => { const seq = useDirector.getState().doGesture(str(a.id, 'id').replace(/^gesture:/, '') as GestureId, null); return { seq } },
  'table.event': (a) => { useDirector.getState().tableEvent(str(a.event, 'event')); return { table: Object.keys(useDirector.getState().table) } },
  'media.add': (a) => {
    const id = typeof a.item === 'string' ? a.item.replace(/^(object|media):/, '') : ''
    const it = LIBRARY.find((x) => x.id === id)
    const src = (a.src as string | undefined) ?? it?.src
    if (!src) throw new Error("give 'item' (a library id) or 'src'")
    const mid = useStage.getState().addMedia({
      label: it?.label ?? String(a.label ?? 'Media'), src, poster: it?.poster || undefined,
      playback: it?.playback ?? 'loop', framed: it?.framed ?? true,
      at: { x: Number(a.x ?? 0.5), y: Number(a.y ?? 0.45) }, w: Number(a.w ?? it?.w ?? 0.3), aspect: it?.aspect ?? 16 / 9,
    })
    return { media: mid }
  },
  'media.remove': (a) => { useStage.getState().removeMedia(str(a.id, 'id').replace(/^media:/, '')); return {} },
  'main.source': (a) => {
    const v = a.src
    const src = v == null || v === '' ? null : /^(https?:)?\/\/|^[\w-]+\.[a-z]{2,}/i.test(String(v)) && !String(v).startsWith('/') ? toUrlSource(String(v)) : String(v)
    useStage.getState().setSource('main', src)
    return { main: src }
  },
  'workflow.insert': (a) => {
    const w = WORKFLOWS.find((x) => x.id === str(a.id, 'id').replace(/^workflow:/, ''))
    if (!w) throw new Error(`no workflow ${String(a.id)}`)
    w.scenes.forEach((id) => useStage.getState().ensureTemplate(id))
    const segs = w.build({ ...workflowDefaults(w), ...((a.fields as Record<string, string>) ?? {}) })
    useDirector.getState().insertSegments(segs, a.mode === 'append' ? 'append' : 'replace', w.name)
    return { segments: segs.length }
  },
  'script.play': (a) => { useDirector.getState().play(Number(a.from ?? 0)); return { playing: true } },
  'script.stop': () => { useDirector.getState().stop(); return { playing: false } },
  'avatar.shape': (a) => { useDirector.getState().setAvatarShape(str(a.shape, 'shape') as AvatarShape); return {} },
  'orientation.set': (a) => { useStage.getState().setOrientation(a.orientation === 'portrait' ? 'portrait' : 'landscape'); return {} },
}

export function snapshot() {
  const st = useStage.getState(), d = useDirector.getState(), p = useProgram.getState()
  const seg = d.current >= 0 ? d.script.segments[d.current] : undefined
  return {
    scene: { id: st.activeId, name: st.active().name },
    orientation: st.orientation,
    cue: d.cue,
    playing: d.playing,
    segment: seg ? { index: d.current, text: seg.text } : null,
    gesture: d.gesture?.id ?? null,
    table: Object.keys(d.table),
    program: { connected: p.connected, recording: p.recording, live: p.live },
  }
}

/** Start the bridge (editor only). Returns a stop function. Quietly does nothing without a server. */
export function startAgentBridge(): () => void {
  let es: EventSource | null = null
  let stopped = false
  void fetch('/api/library/web', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(buildCatalog()) })
    .then((r) => {
      if (!r.ok || stopped) return
      es = new EventSource('/api/agent/stream')
      es.addEventListener('do', (e) => {
        const { id, action, args } = JSON.parse((e as MessageEvent).data) as { id: string; action: string; args: Args }
        let body: { ok: boolean; result?: unknown; error?: string }
        try {
          const run = EXECUTORS[action]
          if (!run) throw new Error(`unknown action ${action}`)
          body = { ok: true, result: run(args ?? {}) }
        } catch (err) { body = { ok: false, error: (err as Error).message } }
        void fetch(`/api/agent/result/${id}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
      })
    })
    .catch(() => {})
  let t: ReturnType<typeof setTimeout> | null = null
  const post = () => { t = null; void fetch('/api/agent/state', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(snapshot()) }).catch(() => {}) }
  const schedule = () => { if (!t) t = setTimeout(post, 500) }
  const u1 = useStage.subscribe(schedule), u2 = useDirector.subscribe(schedule), u3 = useProgram.subscribe(schedule)
  schedule()
  return () => { stopped = true; es?.close(); u1(); u2(); u3(); if (t) clearTimeout(t) }
}
