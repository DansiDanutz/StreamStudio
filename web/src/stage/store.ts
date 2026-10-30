import { create } from 'zustand'
import { PRESETS, clone } from './presets'
import { GRID, type CardKind, type CardLayout, type Orientation, type Rect, type Scene } from './types'

const KEY = 'streamstudio.scenes.v2'

interface State {
  scenes: Scene[]
  activeId: string
  orientation: Orientation
  guides: boolean
  selected: CardKind | null
  // sources (object URLs for now; the backend asset library replaces this in S2)
  mainSrc: string | null
  avatarSrc: string | null

  active: () => Scene
  layout: (kind: CardKind) => CardLayout
  setOrientation: (o: Orientation) => void
  toggleOrientation: () => void
  toggleMenu: () => void
  toggleGuides: () => void
  select: (k: CardKind | null) => void
  setRect: (kind: CardKind, r: Partial<Rect>, snap?: boolean) => void
  bringToFront: (kind: CardKind) => void
  toggleVisible: (kind: CardKind) => void
  toggleLocked: (kind: CardKind) => void
  loadPreset: (id: string) => void
  saveAs: (name: string) => void
  setActive: (id: string) => void
  deleteScene: (id: string) => void
  setSource: (kind: 'main' | 'avatar', url: string | null) => void
}

const persisted = (): Scene[] | null => {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Scene[]) : null
  } catch {
    return null
  }
}
const persist = (scenes: Scene[]) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(scenes))
  } catch {
    /* storage unavailable: fine, scenes live in memory */
  }
}

export const snap = (v: number, grid = GRID) => Math.round(v / grid) * grid
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export const useStage = create<State>((set, get) => {
  const initial = persisted() ?? clone(PRESETS)
  const update = (fn: (s: Scene) => void) =>
    set((st) => {
      const scenes = st.scenes.map((s) => (s.id === st.activeId ? (fn((s = clone(s))), s) : s))
      persist(scenes)
      return { scenes }
    })

  return {
    scenes: initial,
    activeId: initial[0].id,
    orientation: 'landscape',
    guides: true,
    selected: null,
    mainSrc: null,
    avatarSrc: null,

    active: () => get().scenes.find((s) => s.id === get().activeId) ?? get().scenes[0],
    layout: (kind) => get().active().layouts[get().orientation][kind],
    setOrientation: (orientation) => set({ orientation }),
    toggleOrientation: () =>
      set((s) => ({ orientation: s.orientation === 'landscape' ? 'portrait' : 'landscape' })),
    toggleMenu: () => update((s) => void (s.menuShown = !s.menuShown)),
    toggleGuides: () => set((s) => ({ guides: !s.guides })),
    select: (selected) => set({ selected }),

    setRect: (kind, r, doSnap = true) =>
      update((s) => {
        const l = s.layouts[get().orientation][kind]
        if (l.locked) return
        const n = { ...l, ...r }
        if (doSnap) {
          n.x = snap(n.x); n.y = snap(n.y); n.w = snap(n.w); n.h = snap(n.h)
        }
        n.w = clamp(n.w, 0.06, 1)
        n.h = clamp(n.h, 0.06, 1)
        n.x = clamp(n.x, 0, 1 - n.w)
        n.y = clamp(n.y, 0, 1 - n.h)
        Object.assign(l, n)
      }),

    bringToFront: (kind) =>
      update((s) => {
        const ls = s.layouts[get().orientation]
        const top = Math.max(...Object.values(ls).map((l) => l.z))
        if (ls[kind].z < top) ls[kind].z = top + 1
      }),
    toggleVisible: (kind) =>
      update((s) => void (s.layouts[get().orientation][kind].visible = !s.layouts[get().orientation][kind].visible)),
    toggleLocked: (kind) =>
      update((s) => void (s.layouts[get().orientation][kind].locked = !s.layouts[get().orientation][kind].locked)),

    loadPreset: (id) => {
      const p = PRESETS.find((x) => x.id === id)
      if (!p) return
      update((s) => {
        s.layouts = clone(p.layouts); s.bezel = p.bezel; s.menuShown = p.menuShown
      })
    },
    saveAs: (name) =>
      set((st) => {
        const src = st.scenes.find((s) => s.id === st.activeId)!
        const copy = { ...clone(src), id: `scene_${Date.now().toString(36)}`, name }
        const scenes = [...st.scenes, copy]
        persist(scenes)
        return { scenes, activeId: copy.id }
      }),
    setActive: (activeId) => set({ activeId, selected: null }),
    deleteScene: (id) =>
      set((st) => {
        if (st.scenes.length <= 1) return {}
        const scenes = st.scenes.filter((s) => s.id !== id)
        persist(scenes)
        return { scenes, activeId: st.activeId === id ? scenes[0].id : st.activeId }
      }),
    setSource: (kind, url) => set(kind === 'main' ? { mainSrc: url } : { avatarSrc: url }),
  }
})
