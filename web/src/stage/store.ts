import { create } from 'zustand'
import { PRESETS, clone } from './presets'
import { GRID, type CardKind, type CardLayout, type MediaCard, type Orientation, type Rect, type Scene } from './types'

const KEY = 'streamstudio.scenes.v2'

interface State {
  scenes: Scene[]
  activeId: string
  orientation: Orientation
  guides: boolean
  selected: CardKind | null
  /** Selected media card id (independent of the core-card selection). */
  selectedMedia: string | null
  // sources (object URLs for now; the backend asset library replaces this in S2)
  mainSrc: string | null
  avatarSrc: string | null
  /** Use the transparent cut-out of the avatar (presenter in the studio) instead of the raw clip. */
  cutout: boolean

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
  toggleCutout: () => void
  media: () => MediaCard[]
  addMedia: (m: Omit<MediaCard, 'id' | 'layout'> & { at: { x: number; y: number }; w?: number; aspect?: number }) => string
  updateMedia: (id: string, patch: Partial<Omit<MediaCard, 'id' | 'layout'>>) => void
  setMediaRect: (id: string, r: Partial<Rect>, snap?: boolean) => void
  removeMedia: (id: string) => void
  selectMedia: (id: string | null) => void
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
    selectedMedia: null,
    mainSrc: null,
    avatarSrc: null,
    cutout: true,

    active: () => get().scenes.find((s) => s.id === get().activeId) ?? get().scenes[0],
    layout: (kind) => get().active().layouts[get().orientation][kind],
    setOrientation: (orientation) => set({ orientation }),
    toggleOrientation: () =>
      set((s) => ({ orientation: s.orientation === 'landscape' ? 'portrait' : 'landscape' })),
    toggleMenu: () => update((s) => void (s.menuShown = !s.menuShown)),
    toggleGuides: () => set((s) => ({ guides: !s.guides })),
    select: (selected) => set({ selected, selectedMedia: selected ? null : get().selectedMedia }),

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
    toggleCutout: () => set((s) => ({ cutout: !s.cutout })),

    media: () => get().active().media?.[get().orientation] ?? [],
    addMedia: ({ at, w = 0.22, aspect = 16 / 9, ...m }) => {
      const id = `media_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`
      const o = get().orientation
      const frameAspect = o === 'landscape' ? 16 / 9 : 9 / 16
      const h = Math.min(1, (w * frameAspect) / aspect)
      update((s) => {
        const list = s.media?.[o] ?? []
        const z = 10 + list.length
        const card: MediaCard = { ...m, id, layout: { x: clamp(at.x - w / 2, 0, 1 - w), y: clamp(at.y - h / 2, 0, 1 - h), w, h, z, visible: true, locked: false, radius: m.framed ? 0.012 : 0 } }
        s.media = { landscape: s.media?.landscape ?? [], portrait: s.media?.portrait ?? [], [o]: [...list, card] }
      })
      set({ selectedMedia: id, selected: null })
      return id
    },
    updateMedia: (id, patch) => update((s) => {
      const o = get().orientation
      s.media?.[o]?.forEach((c) => { if (c.id === id) Object.assign(c, patch, patch.framed !== undefined ? { layout: { ...c.layout, radius: patch.framed ? 0.012 : 0 } } : {}) })
    }),
    setMediaRect: (id, r, doSnap = true) => update((s) => {
      const c = s.media?.[get().orientation]?.find((x) => x.id === id)
      if (!c || c.layout.locked) return
      const n = { ...c.layout, ...r }
      if (doSnap) { n.x = snap(n.x); n.y = snap(n.y); n.w = snap(n.w); n.h = snap(n.h) }
      n.w = clamp(n.w, 0.03, 1); n.h = clamp(n.h, 0.03, 1)
      n.x = clamp(n.x, -n.w * 0.5, 1 - n.w * 0.5); n.y = clamp(n.y, -n.h * 0.5, 1 - n.h * 0.5)
      c.layout = n
    }),
    removeMedia: (id) => {
      update((s) => {
        const o = get().orientation
        if (s.media?.[o]) s.media[o] = s.media[o].filter((c) => c.id !== id)
      })
      if (get().selectedMedia === id) set({ selectedMedia: null })
    },
    selectMedia: (selectedMedia) => set({ selectedMedia, selected: selectedMedia ? null : get().selected }),
  }
})
