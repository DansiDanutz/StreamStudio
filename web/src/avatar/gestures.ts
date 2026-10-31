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

/** HeyGen motion prompts (Avatar IV) for the clips we render; mirrored gestures reuse their source. */
export const MOTION: Partial<Record<GestureId, string>> = {
  // Directions are the viewer's: "right" = the right side of the frame = Dan's LEFT arm.
  // (HeyGen reads "right arm" as his own right, which points to the left of the frame.)
  'point-up-right': 'His left arm raises and points up toward the right side of the frame, at a screen behind him, holds one beat, then returns both hands to the desk. Calm, confident.',
  'point-right': 'His left arm extends and points toward the right side of the frame at shoulder height, holds one beat, then returns both hands to the desk.',
  'point-down-right': 'His left hand points down at the desk on the right side of the frame, one finger extended, holds one beat, then returns both hands to the desk. The other hand stays still on the desk.',
  'present-right': 'His left hand opens palm-up toward the right side of the frame as if presenting something, holds one beat, then returns to the desk.',
  welcome: 'Both hands open outward, palms up, welcoming, then return together on the desk. Warm smile.',
  'thumbs-up': 'One hand gives a thumbs-up at chest height, holds one beat, then returns to the desk. Friendly.',
  wave: 'One hand raises and waves twice, friendly, then returns to the desk.',
  think: 'One hand rises to the chin, thoughtful look for one beat, then returns to the desk.',
}

/** The clips to render: every gesture that is not a mirror. */
export const SOURCE_GESTURES = GESTURES.filter((g) => !g.mirrorOf).map((g) => g.id)

/** A motion prompt for a gesture inside a spoken clip (the gesture happens while talking). */
export const motionFor = (id: GestureId) => {
  const g = gesture(id)
  const base = MOTION[g?.mirrorOf ?? id] ?? ''
  if (!g?.mirrorOf) return base
  // mirror: swap the frame side and the arm
  return base.replace(/right side/g, '§').replace(/left side/g, 'right side').replace(/§/g, 'left side')
    .replace(/His left/g, 'His right')
}

/* ---- what we actually have clips for (assets/avatar/gestures/manifest.json) ---- */

let made: Set<GestureId> | null = null
/** Load once which gesture clips exist; until then every gesture is assumed available. */
export async function loadGestureManifest(f: typeof fetch = fetch): Promise<void> {
  try {
    const r = await f('/avatar/gestures/manifest.json', { cache: 'no-store' })
    const j = (await r.json()) as { gestures?: Record<string, number> }
    made = new Set(Object.keys(j.gestures ?? {}) as GestureId[])
  } catch { /* offline/hosted demo: keep trying clips, the pointer cue covers misses */ }
}
export const setMadeGestures = (ids: GestureId[] | null) => { made = ids ? new Set(ids) : null }
export const hasClip = (id: GestureId) => { const g = gesture(id); return !made || !!(g && made.has(g.mirrorOf ?? g.id)) }

/** The closest gesture we have a clip for, aiming the same way (side first, then height). */
export function nearestMade(id: GestureId): GestureId | null {
  if (hasClip(id)) return id
  const want = gesture(id)?.aim
  if (!want) return null
  const cands = GESTURES.filter((g) => g.aim && hasClip(g.id))
  if (!cands.length) return null
  const cost = (a: { x: number; y: number }) => (a.x === want.x ? 0 : 10) + Math.abs(a.y - want.y)
  return cands.sort((a, b) => cost(a.aim!) - cost(b.aim!))[0].id
}

/** Aim at anything: the gesture we will play for this presenter → target, given the clips we have. */
export function aimAt(presenter: Rect, target: Rect): GestureId {
  const ideal = pickGesture(presenter, target)
  return nearestMade(ideal) ?? ideal
}
