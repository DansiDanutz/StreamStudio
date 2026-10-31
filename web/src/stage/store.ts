import { create } from 'zustand'
import { COLLECTIONS, PRESETS, clone } from './presets'
import { GRID, type CardKind, type CardLayout, type MediaCard, type Orientation, type Rect, type Scene } from './types'

const KEY = 'streamstudio.scenes.v3'
const OLD_KEY = 'streamstudio.scenes.v2'

/** Scenes in strip order: by collection (Openers → Social, unknown last), then their order in the list. */
export function orderedScenes(scenes: Scene[]): Scene[] {
  const rank = (c?: string) => { const i = (COLLECTIONS as readonly string[]).indexOf(c ?? ''); return i < 0 ? COLLECTIONS.length : i }
  return scenes.map((s, i) => ({ s, i })).sort((a, b) => rank(a.s.collection) - rank(b.s.collection) || a.i - b.i).map((x) => x.s)
}

/** Give every scene a collection; a v2 library gains the new templates once. */
export function migrateScenes(list: Scene[], fromV2: boolean): Scene[] {
  const byId = new Map(PRESETS.map((p) => [p.id, p]))
  const out: Scene[] = list.map((s) => ({ ...s, collection: s.collection ?? byId.get(s.id)?.collection ?? 'Talk' }))
  if (fromV2) for (const p of PRESETS) if (!out.some((s) => s.id === p.id)) out.push(clone(p))
  return out
}

export type SyncState = 'local' | 'server' | 'saving' | 'error'

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

  // ---- scene library
  /** Where scenes are saved: the Mac Studio server, or only this browser. */
  sync: SyncState
  setSync: (s: SyncState) => void
  /** Replace the library (e.g. loaded from the server). Keeps the active scene when it still exists. */
  replaceScenes: (list: Scene[]) => void
  newScene: (templateId: string, collection?: string) => void
  duplicateScene: (id: string) => void
  renameScene: (id: string, name: string) => void
  /** Move a scene into `collection`, before `beforeId` (or at the end of that collection). */
  moveScene: (id: string, collection: string, beforeId?: string | null) => void
  importScenes: (list: Scene[]) => number
}

const persisted = (): Scene[] | null => {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) return migrateScenes(JSON.parse(raw) as Scene[], false)
    const old = localStorage.getItem(OLD_KEY)
    return old ? migrateScenes(JSON.parse(old) as Scene[], true) : null
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

const newId = () => `scene_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const uniqueName = (scenes: Scene[], base: string) => {
  const names = new Set(scenes.map((s) => s.name))
  if (!names.has(base)) return base
  base = base.replace(/ \d+$/, '')
  let i = 2
  while (names.has(`${base} ${i}`)) i++
  return `${base} ${i}`
}

export const snap = (v: number, grid = GRID) => Math.round(v / grid) * grid
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export const useStage = create<State>((set, get) => {
  const initial = persisted() ?? clone(PRESETS)
  const first = orderedScenes(initial)[0]
  const update = (fn: (s: Scene) => void) =>
    set((st) => {
      const scenes = st.scenes.map((s) => (s.id === st.activeId ? (fn((s = clone(s))), s) : s))
      persist(scenes)
      return { scenes }
    })

  return {
    scenes: initial,
    activeId: first.id,
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
        return { scenes, activeId: st.activeId === id ? orderedScenes(scenes)[0].id : st.activeId }
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

    sync: 'local',
    setSync: (sync) => set({ sync }),
    replaceScenes: (list) => set((st) => {
      if (!list.length) return {}
      const scenes = migrateScenes(list, false)
      persist(scenes)
      return { scenes, activeId: scenes.some((x) => x.id === st.activeId) ? st.activeId : orderedScenes(scenes)[0].id }
    }),
    newScene: (templateId, collection) => set((st) => {
      const t = PRESETS.find((p) => p.id === templateId) ?? PRESETS[0]
      const scene: Scene = { ...clone(t), id: newId(), name: uniqueName(st.scenes, t.name), collection: collection ?? t.collection }
      const scenes = [...st.scenes, scene]
      persist(scenes)
      return { scenes, activeId: scene.id, selected: null, selectedMedia: null }
    }),
    duplicateScene: (id) => set((st) => {
      const i = st.scenes.findIndex((s) => s.id === id)
      if (i < 0) return {}
      const copy = { ...clone(st.scenes[i]), id: newId(), name: uniqueName(st.scenes, st.scenes[i].name) }
      const scenes = [...st.scenes.slice(0, i + 1), copy, ...st.scenes.slice(i + 1)]
      persist(scenes)
      return { scenes, activeId: copy.id }
    }),
    renameScene: (id, name) => set((st) => {
      const n = name.trim()
      if (!n) return {}
      const scenes = st.scenes.map((s) => (s.id === id ? { ...s, name: n } : s))
      persist(scenes)
      return { scenes }
    }),
    moveScene: (id, collection, beforeId = null) => set((st) => {
      const moving = st.scenes.find((s) => s.id === id)
      if (!moving || id === beforeId) return {}
      const rest = st.scenes.filter((s) => s.id !== id)
      const moved = moving.collection === collection ? moving : { ...moving, collection }
      let at = beforeId ? rest.findIndex((s) => s.id === beforeId) : -1
      if (at < 0) { // end of that collection (or end of the list)
        const last = rest.map((s, i) => (s.collection === collection ? i : -1)).filter((i) => i >= 0).pop()
        at = last === undefined ? rest.length : last + 1
      }
      const scenes = [...rest.slice(0, at), moved, ...rest.slice(at)]
      persist(scenes)
      return { scenes }
    }),
    importScenes: (list) => {
      const valid = list.filter((s) => s && typeof s.name === 'string' && s.layouts?.landscape && s.layouts?.portrait)
      if (!valid.length) return 0
      set((st) => {
        const incoming = migrateScenes(valid.map((s) => ({ ...clone(s), id: newId() })), false)
        const scenes = [...st.scenes, ...incoming]
        persist(scenes)
        return { scenes, activeId: incoming[0].id }
      })
      return valid.length
    },
  }
})
