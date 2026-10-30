/** Director model. The script is the master clock: each segment carries the voice (avatar clip),
 *  the visual (Main-card source), and a cue that decides the layout and zoom. */

/** avatar = presenter fills the frame, no card chrome; duo = presenter large + small content;
 *  split = the saved scene layout; content = content maximized, presenter small; full = content only. */
export type Cue = 'avatar' | 'duo' | 'split' | 'content' | 'full'

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
