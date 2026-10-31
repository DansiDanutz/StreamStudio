import { create } from 'zustand'
import { useStage } from '../stage/store'
import type { CardKind, CardLayout, Rect } from '../stage/types'
import { autoDirect, splitScript } from './autoDirect'
import { guardLayout, layoutForCue } from './cueLayouts'
import { estimateMs, guardCue, lipsMatch, newSegment, type AvatarShape, type Cue, type Script, type Segment, type Zoom } from './types'
import { RESET_ON } from '../overlays/sketches'
import { OBJECTS } from '../overlays/objects'
import type { TableState } from '../overlays/ObjectLayer'
import { GESTURES, SEATED, aimAt, gesture as findGesture, hasClip, nearestMade, type GestureId } from '../avatar/gestures'
import { hotspot } from '../stage/hotspots'

/** A gesture on air: the clip plays in the Avatar card; without a clip, a pointer cue is drawn instead. */
export interface GestureOnAir { id: GestureId; seq: number; ms: number; from: Rect; to: Rect | null; missing?: boolean }

const KEY = 'streamstudio.script.v6'
const SHAPE_KEY = 'streamstudio.avatarShape'

export type LiveLayouts = Partial<Record<CardKind, Rect & { visible?: boolean; radius?: number; z?: number }>>

interface State {
  script: Script
  playing: boolean
  /** Index of the segment on air, or -1. */
  current: number
  /** Animated card geometry while the director is driving; null = saved scene layout. */
  live: LiveLayouts | null
  zoom: Zoom | null
  /** The cue currently applied (manual or from the segment). */
  cue: Cue
  /** True while the on-air segment's face was moved to the small card by the lip-sync guard. */
  guarded: boolean
  /** Shape of the avatar card when it is not full frame. */
  avatarShape: AvatarShape
  setAvatarShape: (s: AvatarShape) => void
  gesture: GestureOnAir | null
  /** Start a gesture now. `to` = what it aims at (for the pointer cue). */
  doGesture: (id: GestureId, to?: Rect | null) => number
  endGesture: (seq: number) => void
  markGestureMissing: (seq: number) => void
  /** Resolve a segment target ('main', 'hotspot:monitor', 'media:<id>') to a frame rect. */
  targetRect: (target?: string) => Rect | null
  /** Dan points at any card or place: 'main', 'media:<id>', 'hotspot:<id>'. Returns the gesture used. */
  pointAt: (target: string) => GestureId | null
  /** Desk sketches currently on the table, in draw order. */
  sketches: string[]
  pushSketch: (id: string | null) => void
  /** 3D objects on the table and their phase. */
  table: TableState
  tableEvent: (ev: string) => void

  setText: (text: string) => void
  updateSegment: (id: string, patch: Partial<Segment>) => void
  addSegment: () => void
  /** Insert ready-made segments (from a workflow): replace the script or append to it. */
  insertSegments: (segs: Segment[], mode: 'replace' | 'append', title?: string) => void
  removeSegment: (id: string) => void
  runAutoDirect: () => void
  /** `guard` = enforce the lip-sync rule on the resulting layout (always on during play). */
  applyCue: (cue: Cue, zoom?: Zoom | null, ms?: number, guard?: boolean, via?: Rect | null) => void
  play: (from?: number) => void
  stop: () => void
  next: () => void
}

const persisted = (): Script | null => {
  try { const r = localStorage.getItem(KEY); return r ? JSON.parse(r) : null } catch { return null }
}
const persist = (s: Script) => { try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* ok */ } }

// Default script: "the world of AI" opener (docs/scripts/intro-world-of-ai.md). 3D objects arrive on the table.
export const INTRO: { text: string; table?: string }[] = [
  { text: 'Let me introduce you to the world of AI. The technology of the future, on this table, today.', table: 'clear' },
  { text: "First: Claude. This is where I think, plan and write. When I'm wrong, it says so. Best at reasoning, long context, and code review.", table: 'arrive:claude-code' },
  { text: 'Codex. My pair programmer in the terminal. Fastest way from an idea to running code.', table: 'arrive:codex' },
  { text: 'Grok, with GrokBot on top: real-time market data, and my paper-trading agent that learns every day.', table: 'arrive:cluster' },
  { text: 'Hermes. The messenger of my fleet; it runs the machines and talks to every other agent.', table: 'arrive:hermes' },
  { text: 'Kimi. Long documents, research, the reader of the team.', table: 'arrive:kimi' },
  { text: 'And GLM. Fast, cheap, local when I need it.', table: 'arrive:glm' },
  { text: 'And one more. OpenClaw, the lobster. The most exciting, most attractive thing I saw this year. And I gave up on it.', table: 'arrive:openclaw' },
  { text: "Not because it was bad. That's how fast AI moves: the thing that made me fall in love got replaced in months.", table: 'leave:openclaw' },
  { text: "Six minds, one table. I'm the conductor. Let's make something.", table: 'react:all' },
]

let raf = 0
let gestureSeq = 0
let timer: ReturnType<typeof setTimeout> | null = null
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

export const useDirector = create<State>((set, get) => {
  const save = (fn: (s: Script) => Script) => set((st) => { const script = fn(st.script); persist(script); return { script } })

  /** Where the presenter's body is in the frame right now (seated cut-out, or the avatar card). */
  const presenterRect = (): Rect => {
    const stage = useStage.getState()
    const a = get().live?.avatar ?? stage.active().layouts[stage.orientation].avatar
    const full = a.w >= 0.999 && a.h >= 0.999
    return full ? SEATED[stage.orientation] : { x: a.x, y: a.y, w: a.w, h: a.h }
  }

  /** Tween the live geometry from the current rects to `target` over `ms`. */
  const tween = (target: Record<CardKind, CardLayout>, ms: number) => {
    cancelAnimationFrame(raf)
    const stage = useStage.getState()
    const from: Record<CardKind, Rect & { visible: boolean }> = { main: null!, avatar: null!, menu: null! }
    for (const k of ['main', 'avatar', 'menu'] as CardKind[]) {
      const live = get().live?.[k]
      const saved = stage.active().layouts[stage.orientation][k]
      from[k] = { x: live?.x ?? saved.x, y: live?.y ?? saved.y, w: live?.w ?? saved.w, h: live?.h ?? saved.h, visible: live?.visible ?? saved.visible }
    }
    const t0 = performance.now()
    const step = (now: number) => {
      const t = ms <= 0 ? 1 : Math.min(1, (now - t0) / ms)
      const e = ease(t)
      const live: LiveLayouts = {}
      for (const k of ['main', 'avatar'] as CardKind[]) {
        const a = from[k], b = target[k]
        // A card that is appearing starts from the target size (fade handled by CSS); one that is
        // disappearing keeps its geometry and just hides at the end.
        live[k] = {
          x: a.x + (b.x - a.x) * e, y: a.y + (b.y - a.y) * e,
          w: a.w + (b.w - a.w) * e, h: a.h + (b.h - a.h) * e,
          visible: b.visible || (a.visible && t < 1),
          radius: b.radius,
          z: b.z,
        }
      }
      set({ live })
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
  }

  const scheduleEnd = (seg: Segment, lead = 0) => {
    if (timer) clearTimeout(timer)
    // With a voice (clip or narration audio), AvatarCard calls next() on `ended`; the timer is a safety net.
    const voiced = lipsMatch(seg) || (seg.voice === 'narration' && !!seg.audio)
    const ms = voiced ? seg.durationMs + 30_000 : seg.durationMs
    timer = setTimeout(() => get().playing && get().next(), ms + lead)
  }

  const initial = persisted() ?? {
    id: 'script_world', title: 'The world of AI',
    segments: INTRO.map((s) => ({ ...newSegment(s.text, 'avatar'), pinned: true, table: s.table })),
  }

  return {
    script: initial,
    playing: false,
    current: -1,
    live: null,
    zoom: null,
    cue: 'split',
    guarded: false,
    gesture: null,
    doGesture: (id, to = null) => {
      const g = findGesture(id) ?? GESTURES[0]
      const seq = ++gestureSeq // never reused: a stale safety timer must not end a newer gesture
      set({ gesture: { id: g.id, seq, ms: g.ms, from: presenterRect(), to } })
      setTimeout(() => get().endGesture(seq), g.ms + 2500) // safety: a stuck clip never blocks the show
      if (!hasClip(g.id)) get().markGestureMissing(seq) // no clip yet: the pointer cue stands in
      return seq
    },
    endGesture: (seq) => { if (get().gesture?.seq === seq) set({ gesture: null }) },
    markGestureMissing: (seq) => {
      const g = get().gesture
      if (!g || g.seq !== seq || g.missing) return
      set({ gesture: { ...g, missing: true } })
      setTimeout(() => get().endGesture(seq), g.ms) // the pointer cue runs for the gesture's length
    },
    targetRect: (target = 'main') => {
      const stage = useStage.getState()
      if (target.startsWith('hotspot:')) return hotspot(target.slice(8))?.rect ?? null
      if (target.startsWith('media:')) {
        const m = (stage.active().media?.[stage.orientation] ?? []).find((c) => c.id === target.slice(6) || c.label === target.slice(6))
        return m ? m.layout : null
      }
      const k = (target === 'avatar' || target === 'menu' ? target : 'main') as CardKind
      const l = get().live?.[k]
      const saved = stage.active().layouts[stage.orientation][k]
      return l ? { x: l.x, y: l.y, w: l.w, h: l.h } : saved
    },
    pointAt: (target) => {
      const to = get().targetRect(target)
      if (!to) return null
      const id = aimAt(presenterRect(), to)
      get().doGesture(id, to)
      return id
    },
    avatarShape: (() => { try { return (localStorage.getItem(SHAPE_KEY) as AvatarShape) || 'circle' } catch { return 'circle' } })(),
    setAvatarShape: (avatarShape) => {
      try { localStorage.setItem(SHAPE_KEY, avatarShape) } catch { /* ok */ }
      set({ avatarShape })
      const { live, cue, playing, current, script } = get()
      if (live) get().applyCue(cue, get().zoom, 300, playing && !lipsMatch(script.segments[current] ?? {}))
    },
    sketches: [],
    table: {},
    tableEvent: (ev) => {
      // several events in one field: 'remove:openclaw;react:all'
      if (ev.includes(';')) { ev.split(';').forEach((e) => e.trim() && get().tableEvent(e.trim())); return }
      set((s) => {
      const [kind, arg = ''] = ev.split(':')
      if (kind === 'clear') return { table: {} }
      const ids = arg === 'all' ? Object.keys(s.table).filter((k) => s.table[k].phase !== 'gone' && s.table[k].phase !== 'leave') : arg.split(',').map((x) => x.trim()).filter(Boolean)
      const table: TableState = { ...s.table }
      for (const id of ids) {
        if (!OBJECTS.some((o) => o.id === id)) continue
        const prev = table[id] ?? { phase: 'gone' as const, seq: 0 }
        if (kind === 'arrive') table[id] = { phase: 'arrive', seq: prev.seq + 1, arrivedAt: performance.now() }
        if (kind === 'react') table[id] = { ...prev, phase: 'react', seq: prev.seq + 1, dim: false }
        if (kind === 'dim') table[id] = { ...prev, dim: true }
        if (kind === 'remove') table[id] = { phase: 'gone', seq: prev.seq + 1 }
        if (kind === 'leave') table[id] = { phase: 'leave', seq: prev.seq + 1 }
      }
      return { table }
    })
    },
    pushSketch: (id) => set((s) => (id === null ? { sketches: [] } : RESET_ON.has(id) ? { sketches: [id] } : { sketches: [...s.sketches, id] })),

    setText: (text) => save((s) => ({ ...s, segments: splitScript(text).map((t, i) => ({ ...(s.segments[i] ?? newSegment()), text: t, durationMs: estimateMs(t) })) })),
    updateSegment: (id, patch) => save((s) => ({ ...s, segments: s.segments.map((x) => (x.id === id ? { ...x, ...patch, ...(patch.text !== undefined ? { durationMs: estimateMs(patch.text) } : {}) } : x)) })),
    addSegment: () => save((s) => ({ ...s, segments: [...s.segments, newSegment()] })),
    insertSegments: (segs, mode, title) => {
      if (get().playing) get().stop()
      save((s) => ({ ...s, title: mode === 'replace' && title ? title : s.title, segments: mode === 'replace' ? segs : [...s.segments, ...segs] }))
    },
    removeSegment: (id) => save((s) => ({ ...s, segments: s.segments.filter((x) => x.id !== id) })),
    runAutoDirect: () => save((s) => autoDirect(s)),

    applyCue: (cue, zoom = null, ms = 600, guard = false, via = null) => {
      const stage = useStage.getState()
      const shape = get().avatarShape
      let target = layoutForCue(cue, stage.active().layouts[stage.orientation], stage.orientation, shape)
      if (guard) target = guardLayout(target, stage.orientation, shape)
      if (via) {
        // The Main card opens out of (or closes back into) a place in the studio, e.g. the monitor.
        const savedMain = stage.active().layouts[stage.orientation].main
        const nowVisible = get().live?.main?.visible ?? savedMain.visible
        if (!nowVisible && target.main.visible) set({ live: { ...(get().live ?? {}), main: { ...via, visible: true, radius: 0, z: 1 } } })
        if (nowVisible && !target.main.visible) target = { ...target, main: { ...target.main, ...via, visible: false, radius: 0 } }
      }
      set({ cue, zoom })
      tween(target, ms)
    },

    play: (from = 0) => {
      const seg = get().script.segments[from]
      if (!seg) return get().stop()
      // Lip-sync guard: the face is only large when the voice is the clip's own audio.
      const cue = guardCue(seg.cue, seg)
      const guard = !lipsMatch(seg)
      if (seg.scene && useStage.getState().scenes.some((x) => x.id === seg.scene)) useStage.getState().setActive(seg.scene)
      set({ playing: true, current: from, guarded: guard && cue !== seg.cue })
      const via = hotspot(seg.via)?.rect ?? null
      // Gesture first (point, then the layout follows the hand); the voice starts when the gesture ends.
      let lead = 0
      if (seg.gesture) {
        const target = seg.target ?? (seg.via ? `hotspot:${seg.via}` : 'main')
        const to = get().targetRect(target)
        const id = (seg.gesture === 'auto' ? aimAt(presenterRect(), to ?? { x: 0.7, y: 0.3, w: 0.2, h: 0.2 }) : nearestMade(seg.gesture as GestureId) ?? seg.gesture) as GestureId
        const g = findGesture(id)
        if (g) { get().doGesture(g.id, to); lead = g.ms }
      }
      const startLayout = () => get().playing && get().current === from && get().applyCue(cue, seg.zoom ?? null, seg.transitionMs, guard, via)
      if (lead) setTimeout(startLayout, Math.round(lead * 0.55)); else startLayout()
      if (seg.visual) useStage.getState().setSource('main', seg.visual)
      if (seg.sketch) setTimeout(() => get().playing && get().pushSketch(seg.sketch!), 300)
      if (seg.table) setTimeout(() => get().playing && get().tableEvent(seg.table!), 400)
      scheduleEnd(seg, lead)
    },
    next: () => {
      const i = get().current + 1
      if (i >= get().script.segments.length) return get().stop()
      get().play(i)
    },
    stop: () => {
      if (timer) clearTimeout(timer)
      cancelAnimationFrame(raf)
      set({ playing: false, current: -1, live: null, zoom: null, cue: 'split', guarded: false, gesture: null, sketches: [], table: {} })
    },
  }
})
