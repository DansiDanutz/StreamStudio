import type { CardKind, CardLayout, Orientation, Scene } from './types'
import { pipRect } from '../director/cueLayouts'

const L = (x: number, y: number, w: number, h: number, z = 1, extra: Partial<CardLayout> = {}): CardLayout => ({
  x, y, w, h, z, visible: true, locked: false, radius: 0.012, ...extra,
})

type Layouts = Record<Orientation, Record<CardKind, CardLayout>>

// Measured from the reference frames (docs/DESIGN.md): presenter 16% wide bottom-left,
// 5% left margin, content card with ~3% bezel padding, menu top-right 19% wide.
const browserCam: Layouts = {
  landscape: {
    main: L(0.03, 0.053, 0.94, 0.894, 1),
    avatar: L(0.05, 0.55, 0.16, 0.36, 2, { radius: 0.014 }),
    menu: L(0.77, 0.07, 0.19, 0.42, 3, { radius: 0.011 }),
  },
  portrait: {
    main: L(0.04, 0.0225, 0.92, 0.6, 1),
    avatar: L(0.04, 0.66, 0.4, 0.28, 2, { radius: 0.03 }),
    menu: L(0.5, 0.66, 0.46, 0.28, 3, { radius: 0.025 }),
  },
}

const avatarStage: Layouts = {
  landscape: {
    main: L(0, 0, 1, 1, 1, { visible: false }),
    avatar: L(0, 0, 1, 1, 1, { radius: 0 }),
    menu: L(0.77, 0.07, 0.19, 0.42, 3, { radius: 0.011 }),
  },
  portrait: {
    main: L(0, 0, 1, 1, 1, { visible: false }),
    avatar: L(0, 0, 1, 1, 1, { radius: 0 }),
    menu: L(0.5, 0.66, 0.46, 0.28, 3, { radius: 0.025 }),
  },
}

const sideCam: Layouts = {
  landscape: {
    main: L(0.24, 0.053, 0.73, 0.894, 1),
    avatar: L(0.02, 0.3, 0.2, 0.45, 2, { radius: 0.014 }),
    menu: L(0.77, 0.07, 0.19, 0.42, 3, { radius: 0.011 }),
  },
  portrait: browserCam.portrait,
}

const raw: Layouts = {
  landscape: {
    main: L(0, 0, 1, 1, 1, { radius: 0 }),
    avatar: L(0.05, 0.55, 0.16, 0.36, 2, { visible: false, radius: 0.014 }),
    menu: L(0.77, 0.07, 0.19, 0.42, 3, { radius: 0.011 }),
  },
  portrait: {
    main: L(0, 0, 1, 1, 1, { radius: 0 }),
    avatar: L(0.04, 0.66, 0.4, 0.28, 2, { visible: false, radius: 0.03 }),
    menu: L(0.5, 0.66, 0.46, 0.28, 3, { radius: 0.025 }),
  },
}

// Dan's studio plate: the content floats on the right like a screen in the room, the avatar
// sits at the desk on the left, and the menu goes top-right over the clear wall.
const studioDesk: Layouts = {
  landscape: {
    main: L(0.38, 0.08, 0.58, 0.66, 2),
    avatar: L(0.03, 0.26, 0.32, 0.7, 1, { radius: 0.014 }),
    menu: L(0.77, 0.6, 0.19, 0.36, 3, { radius: 0.011 }),
  },
  portrait: {
    main: L(0.04, 0.04, 0.92, 0.5, 2),
    avatar: L(0.04, 0.56, 0.5, 0.4, 1, { radius: 0.03 }),
    menu: L(0.58, 0.56, 0.38, 0.4, 3, { radius: 0.025 }),
  },
}

// Presenter alone in the 3D studio, full frame: the opener set (objects arrive on the table).
const worldOfAi: Layouts = {
  landscape: { ...avatarStage.landscape },
  portrait: { ...avatarStage.portrait },
}

// Presenter in the small circle over the studio: the lip-sync-safe talking set.
const circle = (o: Orientation) => L(pipRect(o).x, pipRect(o).y, pipRect(o).w, pipRect(o).h, 3, { radius: 0 })
const studioCircle: Layouts = {
  landscape: { ...avatarStage.landscape, avatar: circle('landscape') },
  portrait: { ...avatarStage.portrait, avatar: circle('portrait') },
}

/** Scene collections, in strip order. */
export const COLLECTIONS = ['Openers', 'Talk', 'Demo', 'Data', 'Social'] as const
export type Collection = (typeof COLLECTIONS)[number]

/** Templates: the starting scenes, and what "+ New" builds from. */
export const PRESETS: Scene[] = [
  { id: 'world-of-ai', name: 'World of AI', collection: 'Openers', bezel: 'studio', menuShown: false, layouts: worldOfAi },
  { id: 'studio-desk', name: 'Studio Desk', collection: 'Talk', bezel: 'studio', menuShown: false, layouts: studioDesk },
  { id: 'studio-circle', name: 'Studio + Circle', collection: 'Talk', bezel: 'studio', menuShown: false, layouts: studioCircle },
  { id: 'avatar-stage', name: 'Avatar Stage', collection: 'Talk', bezel: 'mono', menuShown: false, layouts: avatarStage },
  { id: 'browser-cam', name: 'Browser + Cam', collection: 'Demo', bezel: 'violet', menuShown: false, layouts: browserCam },
  { id: 'side-cam', name: 'Side Cam', collection: 'Demo', bezel: 'ink', menuShown: false, layouts: sideCam },
  { id: 'app-menu', name: 'App + Menu', collection: 'Demo', bezel: 'violet', menuShown: true, layouts: browserCam },
  { id: 'raw', name: 'Raw', collection: 'Data', bezel: 'mono', menuShown: false, layouts: raw },
]

export const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
