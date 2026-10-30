import type { CardKind, CardLayout, Orientation, Scene } from './types'

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

export const PRESETS: Scene[] = [
  { id: 'studio-desk', name: 'Studio Desk', bezel: 'studio', menuShown: false, layouts: studioDesk },
  { id: 'browser-cam', name: 'Browser + Cam', bezel: 'violet', menuShown: false, layouts: browserCam },
  { id: 'side-cam', name: 'Side Cam', bezel: 'ink', menuShown: false, layouts: sideCam },
  { id: 'app-menu', name: 'App + Menu', bezel: 'violet', menuShown: true, layouts: browserCam },
  { id: 'avatar-stage', name: 'Avatar Stage', bezel: 'mono', menuShown: false, layouts: avatarStage },
  { id: 'raw', name: 'Raw', bezel: 'mono', menuShown: false, layouts: raw },
]

export const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
