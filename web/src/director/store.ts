import { create } from 'zustand'
import { useStage } from '../stage/store'
import type { CardKind, CardLayout, Rect } from '../stage/types'
import { autoDirect, splitScript } from './autoDirect'
import { layoutForCue } from './cueLayouts'
import { estimateMs, newSegment, type Cue, type Script, type Segment, type Zoom } from './types'
import { RESET_ON } from '../overlays/sketches'
import { OBJECTS } from '../overlays/objects'
import type { TableState } from '../overlays/ObjectLayer'

const KEY = 'streamstudio.script.v4'

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
  /** Desk sketches currently on the table, in draw order. */
  sketches: string[]
  pushSketch: (id: string | null) => void
  /** 3D objects on the table and their phase. */
  table: TableState
  tableEvent: (ev: string) => void

  setText: (text: string) => void
  updateSegment: (id: string, patch: Partial<Segment>) => void
  addSegment: () => void
  removeSegment: (id: string) => void
  runAutoDirect: () => void
  applyCue: (cue: Cue, zoom?: Zoom | null, ms?: number) => void
  play: (from?: number) => void
  stop: () => void
  next: () => void
}

const persisted = (): Script | null => {
  try { const r = localStorage.getItem(KEY); return r ? JSON.parse(r) : null } catch { return null }
}
const persist = (s: Script) => { try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* ok */ } }

// Default script: "the world of AI" opener (docs/scripts/intro-world-of-ai.md). 3D objects arrive on the table.
const INTRO: { text: string; table?: string }[] = [
  { text: 'Let me introduce you to the world of AI. The technology of the future, on this table, today.', table: 'clear' },
  { text: "First: Claude. This is where I think, plan and write. When I'm wrong, it says so. Best at reasoning, long context, and code review.", table: 'arrive:claude-code' },
  { text: 'Codex. My pair programmer in the terminal. Fastest way from an idea to running code.', table: 'arrive:codex' },
  { text: 'Grok, with GrokBot on top: real-time market data, and my paper-trading agent that learns every day.', table: 'arrive:cluster' },
  { text: 'Hermes. The messenger of my fleet; it runs the machines and talks to every other agent.', table: 'arrive:hermes' },
  { text: 'Kimi. Long documents, research, the reader of the team.', table: 'arrive:kimi' },
  { text: 'And GLM. Fast, cheap, local when I need it.', table: 'arrive:glm' },
  { text: "Six minds, one table. I'm the conductor. Let's make something.", table: 'react:all' },
]

let raf = 0
let timer: ReturnType<typeof setTimeout> | null = null
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

export const useDirector = create<State>((set, get) => {
  const save = (fn: (s: Script) => Script) => set((st) => { const script = fn(st.script); persist(script); return { script } })

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

  const scheduleEnd = (seg: Segment) => {
    if (timer) clearTimeout(timer)
    // With a clip, AvatarCard calls next() on `ended`; the timer is a safety net.
    const ms = seg.clip ? seg.durationMs + 30_000 : seg.durationMs
    timer = setTimeout(() => get().playing && get().next(), ms)
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
    sketches: [],
    table: {},
    tableEvent: (ev) => set((s) => {
      const [kind, arg = ''] = ev.split(':')
      if (kind === 'clear') return { table: {} }
      const ids = arg === 'all' ? Object.keys(s.table).filter((k) => s.table[k].phase !== 'gone') : arg.split(',').map((x) => x.trim()).filter(Boolean)
      const table: TableState = { ...s.table }
      for (const id of ids) {
        if (!OBJECTS.some((o) => o.id === id)) continue
        const prev = table[id] ?? { phase: 'gone' as const, seq: 0 }
        if (kind === 'arrive') table[id] = { phase: 'arrive', seq: prev.seq + 1 }
        if (kind === 'react') table[id] = { phase: 'react', seq: prev.seq + 1, dim: false }
        if (kind === 'dim') table[id] = { ...prev, dim: true }
        if (kind === 'remove') table[id] = { phase: 'gone', seq: prev.seq + 1 }
      }
      return { table }
    }),
    pushSketch: (id) => set((s) => (id === null ? { sketches: [] } : RESET_ON.has(id) ? { sketches: [id] } : { sketches: [...s.sketches, id] })),

    setText: (text) => save((s) => ({ ...s, segments: splitScript(text).map((t, i) => ({ ...(s.segments[i] ?? newSegment()), text: t, durationMs: estimateMs(t) })) })),
    updateSegment: (id, patch) => save((s) => ({ ...s, segments: s.segments.map((x) => (x.id === id ? { ...x, ...patch, ...(patch.text !== undefined ? { durationMs: estimateMs(patch.text) } : {}) } : x)) })),
    addSegment: () => save((s) => ({ ...s, segments: [...s.segments, newSegment()] })),
    removeSegment: (id) => save((s) => ({ ...s, segments: s.segments.filter((x) => x.id !== id) })),
    runAutoDirect: () => save((s) => autoDirect(s)),

    applyCue: (cue, zoom = null, ms = 600) => {
      const stage = useStage.getState()
      const target = layoutForCue(cue, stage.active().layouts[stage.orientation], stage.orientation)
      set({ cue, zoom })
      tween(target, ms)
    },

    play: (from = 0) => {
      const seg = get().script.segments[from]
      if (!seg) return get().stop()
      set({ playing: true, current: from })
      get().applyCue(seg.cue, seg.zoom ?? null, seg.transitionMs)
      if (seg.visual) useStage.getState().setSource('main', seg.visual)
      if (seg.sketch) setTimeout(() => get().playing && get().pushSketch(seg.sketch!), 300)
      if (seg.table) setTimeout(() => get().playing && get().tableEvent(seg.table!), 400)
      scheduleEnd(seg)
    },
    next: () => {
      const i = get().current + 1
      if (i >= get().script.segments.length) return get().stop()
      get().play(i)
    },
    stop: () => {
      if (timer) clearTimeout(timer)
      cancelAnimationFrame(raf)
      set({ playing: false, current: -1, live: null, zoom: null, cue: 'split', sketches: [], table: {} })
    },
  }
})
