import type { Rect } from '../stage/types'

/** Presenter gestures: short silent clips (mouth closed, 2–3 s) that start and end in the seated
 *  neutral pose, so they cut in and out of the base clip invisibly. Left-hand directions are the
 *  right-hand clips mirrored (the cut-out has no background, so a mirror is free).
 *  Generation kit: docs/prompts/avatar-gestures.md · processing: streamstudio.avatar.gestures. */
export type GestureId =
  | 'point-up-right' | 'point-right' | 'point-down-right'
  | 'point-up-left' | 'point-left' | 'point-down-left'
  | 'present-right' | 'present-left'
  | 'welcome' | 'thumbs-up' | 'wave' | 'think'

export interface Gesture {
  id: GestureId
  label: string
  /** Pointing gestures aim somewhere; beats (welcome, wave…) don't. */
  aim?: { x: -1 | 0 | 1; y: -1 | 0 | 1 }
  /** Rendered from this clip, mirrored horizontally. */
  mirrorOf?: GestureId
  /** Fallback length when the clip has not been made yet, ms. */
  ms: number
}

export const GESTURES: Gesture[] = [
  { id: 'point-up-right', label: 'Point up-right', aim: { x: 1, y: -1 }, ms: 2200 },
  { id: 'point-right', label: 'Point right', aim: { x: 1, y: 0 }, ms: 2200 },
  { id: 'point-down-right', label: 'Point down-right', aim: { x: 1, y: 1 }, ms: 2200 },
  { id: 'point-up-left', label: 'Point up-left', aim: { x: -1, y: -1 }, mirrorOf: 'point-up-right', ms: 2200 },
  { id: 'point-left', label: 'Point left', aim: { x: -1, y: 0 }, mirrorOf: 'point-right', ms: 2200 },
  { id: 'point-down-left', label: 'Point down-left', aim: { x: -1, y: 1 }, mirrorOf: 'point-down-right', ms: 2200 },
  { id: 'present-right', label: 'Open palm to the right', aim: { x: 1, y: 0 }, ms: 2400 },
  { id: 'present-left', label: 'Open palm to the left', aim: { x: -1, y: 0 }, mirrorOf: 'present-right', ms: 2400 },
  { id: 'welcome', label: 'Welcome (both palms open)', ms: 2400 },
  { id: 'thumbs-up', label: 'Thumbs up', ms: 2000 },
  { id: 'wave', label: 'Wave (hello / bye)', ms: 2400 },
  { id: 'think', label: 'Think (hand to chin)', ms: 2600 },
]

export const gesture = (id?: string) => GESTURES.find((g) => g.id === id)

/** URL of the clip that renders a gesture (the mirrored source for left-hand ones). */
export const gestureClip = (g: Gesture) => `/avatar/gestures/${g.mirrorOf ?? g.id}.cutout.webm`

/** Pick the pointing gesture that aims from the presenter's hands at `target` (both in frame fractions).
 *  Up when the target's centre is above the shoulders, down when below the hands, else level. */
export function pickGesture(presenter: Rect, target: Rect, present = false): GestureId {
  const hx = presenter.x + presenter.w / 2
  const shoulders = presenter.y + presenter.h * 0.42
  const hands = presenter.y + presenter.h * 0.78
  const tx = target.x + target.w / 2
  const ty = target.y + target.h / 2
  const side = tx >= hx ? 'right' : 'left'
  if (present) return `present-${side}`
  const level = ty < shoulders ? 'up-' : ty > hands ? 'down-' : ''
  return `point-${level}${side}` as GestureId
}

/** Where the presenter is in the frame when seated full-frame at the desk (matches AvatarCard SEAT). */
export const SEATED: Record<'landscape' | 'portrait', Rect> = {
  landscape: { x: 0.47 - 0.2, y: 0.68 - 0.85 * 0.66, w: 0.4, h: 0.66 },
  portrait: { x: 0.2, y: 0.8 - 0.85 * 0.75, w: 0.6, h: 0.75 },
}
