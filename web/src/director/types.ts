/** Director model. The script is the master clock: each segment carries the voice (avatar clip),
 *  the visual (Main-card source), and a cue that decides the layout and zoom. */

/** avatar = presenter fills the frame, no card chrome; duo = presenter large + small content;
 *  split = the saved scene layout; content = content maximized, presenter small; full = content only;
 *  pip = presenter in a small portrait/circle card over the studio, no content (the lip-sync fallback). */
export type Cue = 'avatar' | 'duo' | 'split' | 'content' | 'full' | 'pip'

/** Shape of the avatar card whenever it is not full frame. */
export type AvatarShape = 'circle' | 'portrait'

export interface Zoom {
  /** Centre of the zoom in fractions of the Main card (0..1). */
  x: number
  y: number
  /** 1 = no zoom. 1.6 is a comfortable "look at this" zoom. */
  scale: number
}

export interface Segment {
  id: string
  /** Spoken text. Drives duration when there is no clip, and the auto-direct rules. */
  text: string
  /** Avatar clip URL for this segment (voice + face). Optional in a dry run. */
  clip?: string
  /** Where the voice comes from. 'clip' (default when there is a clip): the clip's own lip-synced audio.
   *  'narration': a separate voice track (`audio`) over a face that was not rendered for it. */
  voice?: 'clip' | 'narration'
  /** Narration audio URL, used when voice = 'narration'. */
  audio?: string
  /** Main-card source for this segment (image or video URL). Empty keeps the previous one. */
  visual?: string
  cue: Cue
  zoom?: Zoom
  /** Transition into this segment, ms. */
  transitionMs: number
  /** Duration when there is no clip, ms (from text length). */
  durationMs: number
  /** Set by the user: auto-direct must not overwrite this segment's cue. */
  pinned?: boolean
  /** Desk sketch to draw when this segment starts (see overlays/sketches.ts). */
  sketch?: string
  /** Scene to switch to when this segment starts (scene id from the strip). Empty keeps the current one. */
  scene?: string
  /** Presenter gesture at the start of the segment: 'auto' aims at `target`; or a gesture id. */
  gesture?: string
  /** What the presenter points at: 'main', 'hotspot:<id>' (the studio monitor…), or 'media:<card id>'. */
  target?: string
  /** Hotspot the Main card opens out of / closes back into ("enter the monitor"). */
  via?: string
  /** Media cards when this segment starts, chained with ';':
   *  'show:<card>' · 'hide:<card>' · 'move:<card>@x,y,w' (fractions) · 'focus:<card>' (big, centred) · 'reset:<card>'.
   *  <card> is the card's label (e.g. Codex) or id. */
  media?: string
  /** Table event when this segment starts: 'arrive:claude', 'react:claude,codex', 'react:all', 'dim:all', 'clear'. */
  table?: string
}

export interface Script {
  id: string
  title: string
  segments: Segment[]
}

export const WORDS_PER_MIN = 150

export const estimateMs = (text: string) => {
  const words = text.trim().split(/\s+/).filter(Boolean).length
  return Math.max(1500, Math.round((words / WORDS_PER_MIN) * 60_000) + 400)
}

export const newSegment = (text = '', cue: Cue = 'split'): Segment => ({
  id: `seg_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
  text,
  cue,
  transitionMs: 600,
  durationMs: estimateMs(text),
})

/* ---- Lip-sync guard (hard rule, see CLAUDE.md) ----
 * The face may be large (full frame, or the big card of `duo`) ONLY when the voice is the clip's own
 * lip-synced audio. Any other voice puts the face in a small portrait/circle card, where a mismatch
 * between lips and words is too small to notice. */

/** True when the lips on screen were rendered for the words being heard. */
export const lipsMatch = (seg: Pick<Segment, 'clip' | 'voice'>) => !!seg.clip && seg.voice !== 'narration'

/** The cue actually allowed for a segment: big-face cues degrade when the lips do not match. */
export function guardCue(cue: Cue, seg: Pick<Segment, 'clip' | 'voice'>): Cue {
  if (lipsMatch(seg)) return cue
  if (cue === 'avatar') return 'pip'
  if (cue === 'duo') return 'content'
  return cue
}

/** Largest share of the frame (by area) the face may take when the lips do not match. */
export const MAX_UNSYNCED_AREA = 0.06

/* ---- media card events (Segment.media) ---- */
export interface MediaEvent { op: 'show' | 'hide' | 'move' | 'focus' | 'reset'; card: string; x?: number; y?: number; w?: number }

export function parseMediaEvents(src = ''): MediaEvent[] {
  const out: MediaEvent[] = []
  for (const part of src.split(';').map((x) => x.trim()).filter(Boolean)) {
    const m = /^(show|hide|move|focus|reset):([^@]+?)(?:@\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?)?$/i.exec(part)
    if (!m) throw new Error(`bad media event "${part}" (use show:Card, hide:Card, move:Card@x,y,w, focus:Card, reset:Card)`)
    const ev: MediaEvent = { op: m[1].toLowerCase() as MediaEvent['op'], card: m[2].trim() }
    if (m[3] !== undefined) { ev.x = Number(m[3]); ev.y = Number(m[4]); if (m[5] !== undefined) ev.w = Number(m[5]) }
    if (ev.op === 'move' && ev.x === undefined) throw new Error(`move needs a position: move:${ev.card}@x,y,w`)
    out.push(ev)
  }
  return out
}
