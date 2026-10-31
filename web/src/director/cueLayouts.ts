/** Cue → card geometry. Each cue is a layout for the three cards, derived from the scene's
 *  own saved layout so Dan's drag-and-drop choices survive: `split` IS the saved layout;
 *  the other cues are computed from it. */

import type { CardKind, CardLayout, Orientation } from '../stage/types'
import { MAX_UNSYNCED_AREA, type AvatarShape, type Cue } from './types'

type Layouts = Record<CardKind, CardLayout>

const PAD = 0.03

/** Small presenter card, bottom-left. Circle: square in pixels; portrait: 3:4 in pixels. */
export function pipRect(orientation: Orientation, shape: AvatarShape = 'circle') {
  const land = orientation === 'landscape'
  const pxAspect = land ? 16 / 9 : 9 / 16 // frame w/h, to make the card square/3:4 in pixels
  const w = land ? 0.15 : 0.3
  const h = w * pxAspect * (shape === 'circle' ? 1 : 4 / 3)
  return { x: land ? 0.045 : 0.06, y: 1 - h - (land ? 0.07 : 0.05), w, h }
}

/** Enforce the lip-sync guard on any layout: a large, visible face becomes the small card. */
export function guardLayout(L: Layouts, orientation: Orientation, shape: AvatarShape = 'circle'): Layouts {
  const a = L.avatar
  if (!a.visible || a.w * a.h <= MAX_UNSYNCED_AREA) return L
  return { ...L, avatar: { ...a, ...pipRect(orientation, shape), z: Math.max(a.z, 3), radius: 0 } }
}

export function layoutForCue(cue: Cue, saved: Layouts, orientation: Orientation, shape: AvatarShape = 'circle'): Layouts {
  const L = JSON.parse(JSON.stringify(saved)) as Layouts
  const land = orientation === 'landscape'
  switch (cue) {
    case 'split':
      return L
    case 'avatar': {
      // Presenter fills the frame with no card chrome (the aiTrends look). Content hidden.
      L.avatar = { ...L.avatar, visible: true, x: 0, y: 0, w: 1, h: 1, z: 1, radius: 0 }
      L.main = { ...L.main, visible: false }
      return L
    }
    case 'duo': {
      // Presenter large and centred-left; content shrinks to a small window top-right.
      L.avatar = { ...L.avatar, visible: true, x: land ? 0.08 : 0.05, y: land ? 0.1 : 0.12, w: land ? 0.42 : 0.9, h: land ? 0.86 : 0.6, z: 2 }
      L.main = { ...L.main, visible: true, x: land ? 0.58 : 0.3, y: land ? 0.1 : 0.74, w: land ? 0.36 : 0.65, h: land ? 0.36 : 0.2, z: 1 }
      return L
    }
    case 'content': {
      // Content maximized inside the bezel; presenter minimized bottom-left.
      L.main = { ...L.main, visible: true, x: PAD, y: PAD * (land ? 1.78 : 0.56), w: 1 - 2 * PAD, h: 1 - 2 * PAD * (land ? 1.78 : 0.56), z: 1 }
      L.avatar = { ...L.avatar, visible: true, ...pipRect(orientation, shape), z: 2 }
      return L
    }
    case 'full': {
      L.main = { ...L.main, visible: true, x: 0, y: 0, w: 1, h: 1, z: 1, radius: 0 }
      L.avatar = { ...L.avatar, visible: false }
      return L
    }
    case 'pip': {
      // Presenter small over the studio (the table stays the focus); no content card.
      L.avatar = { ...L.avatar, visible: true, ...pipRect(orientation, shape), z: 3, radius: 0 }
      L.main = { ...L.main, visible: false }
      return L
    }
  }
}
