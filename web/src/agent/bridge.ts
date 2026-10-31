/** Connects the open editor to the agent bus: publishes the library, runs agent actions on the
 *  stage, and reports what is on stage. Only the editor (the controller) runs this. */

import { buildCatalog } from './catalog'
import { useStage } from '../stage/store'
import { useDirector } from '../director/store'
import { useProgram } from '../output/link'
import { WORKFLOWS, workflowDefaults } from '../director/workflows'
import { LIBRARY } from '../stage/Library'
import { toUrlSource } from '../stage/media'
import { newSegment, parseMediaEvents, type AvatarShape, type Cue, type Segment, type Zoom } from '../director/types'
import { compileTimeline } from '../director/timeline'
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
  'media.event': (a) => { const ev = str(a.event, 'event'); parseMediaEvents(ev); useDirector.getState().mediaEvent(ev); return { media: Object.keys(useDirector.getState().mediaLive) } },
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
  'timeline.get': () => timelineNow(),
  'segment.preview': (a) => { const i = segIndex(a.index); useDirector.getState().preview(i); return { index: i } },
  'segment.update': (a) => {
    const i = segIndex(a.index)
    const patch = cleanPatch(a.patch)
    useDirector.getState().updateSegment(useDirector.getState().script.segments[i].id, { ...patch, pinned: true })
    return { index: i, segment: useDirector.getState().script.segments[i] }
  },
  'segment.add': (a) => {
    const d = useDirector.getState()
    const seg: Segment = { ...newSegment(String((a.segment as Args | undefined)?.text ?? ''), 'split'), pinned: true, ...cleanPatch(a.segment) }
    const segs = [...d.script.segments]
    const at = a.after == null ? segs.length : segIndex(a.after) + 1
    segs.splice(at, 0, seg)
    d.insertSegments(segs, 'replace', d.script.title)
    return { index: at, id: seg.id }
  },
  'segment.remove': (a) => { const d = useDirector.getState(); const i = segIndex(a.index); d.removeSegment(d.script.segments[i].id); return { removed: i } },
  'script.set': (a) => {
    if (!Array.isArray(a.segments)) throw new Error("'segments' must be a list")
    const segs = (a.segments as Args[]).map((x) => ({ ...newSegment(String(x.text ?? ''), 'split'), pinned: true, ...cleanPatch(x) }))
    useDirector.getState().insertSegments(segs, 'replace', typeof a.title === 'string' ? a.title : undefined)
    return { segments: segs.length }
  },
  'script.play': (a) => { useDirector.getState().play(Number(a.from ?? 0)); return { playing: true } },
  'script.stop': () => { useDirector.getState().stop(); return { playing: false } },
  'avatar.shape': (a) => { useDirector.getState().setAvatarShape(str(a.shape, 'shape') as AvatarShape); return {} },
  'orientation.set': (a) => { useStage.getState().setOrientation(a.orientation === 'portrait' ? 'portrait' : 'landscape'); return {} },
}

const FIELDS = ['text', 'cue', 'scene', 'gesture', 'target', 'via', 'visual', 'table', 'media', 'zoom', 'voice', 'clip', 'audio', 'transitionMs'] as const
/** Keep only known segment fields, check the cue, and re-time the text. */
function cleanPatch(p: unknown): Partial<Segment> {
  if (p == null) return {}
  if (typeof p !== 'object') throw new Error("'patch' must be an object")
  const out: Record<string, unknown> = {}
  for (const k of FIELDS) if (k in (p as Args)) out[k] = (p as Args)[k] ?? undefined
  if (out.cue !== undefined && !CUES.includes(out.cue as Cue)) throw new Error(`cue must be one of ${CUES.join(', ')}`)
  if (typeof out.media === 'string' && out.media) parseMediaEvents(out.media) // throws a clear message if malformed
  if (typeof out.visual === 'string' && /^https?:\/\//.test(out.visual)) out.visual = toUrlSource(out.visual)
  if (typeof out.text === 'string') out.durationMs = Math.max(1500, Math.round((out.text.split(/\s+/).filter(Boolean).length / 150) * 60000) + 400)
  return out as Partial<Segment>
}
function segIndex(v: unknown): number {
  const segs = useDirector.getState().script.segments
  const i = typeof v === 'number' ? v : typeof v === 'string' && /^\d+$/.test(v) ? Number(v) : segs.findIndex((s) => s.id === v)
  if (!Number.isInteger(i) || i < 0 || i >= segs.length) throw new Error(`no segment ${String(v)} (there are ${segs.length})`)
  return i
}
export function timelineNow() {
  const st = useStage.getState()
  return compileTimeline(useDirector.getState().script, st.scenes, st.activeId, st.active().media?.[st.orientation] ?? [])
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
    timeline: timelineNow(),
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
