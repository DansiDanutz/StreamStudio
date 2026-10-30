import { create } from 'zustand'
import { useStage } from '../stage/store'
import type { CardKind, CardLayout, Rect } from '../stage/types'
import { autoDirect, splitScript } from './autoDirect'
import { layoutForCue } from './cueLayouts'
import { estimateMs, newSegment, type Cue, type Script, type Segment, type Zoom } from './types'

const KEY = 'streamstudio.script.v1'

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

const SAMPLE = `Welcome to Dan's Lab. I'm Dan, and this is where we explore artificial intelligence, test new tools, and turn ideas into things that work.

Today I want to show you NervixPay. Look at the dashboard on the screen: this is the merchant view, with every payment coming in live.

Notice this button in the top right. One click and the agent settles the invoice in USDC.

Here's the result: the full flow, end to end, in under four seconds.

If this is useful, subscribe, and I'll see you in the next one.`

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
    id: 'script_default', title: 'NervixPay intro',
    segments: splitScript(SAMPLE).map((t) => newSegment(t)),
  }

  return {
    script: initial,
    playing: false,
    current: -1,
    live: null,
    zoom: null,
    cue: 'split',

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
      set({ playing: false, current: -1, live: null, zoom: null, cue: 'split' })
    },
  }
})
