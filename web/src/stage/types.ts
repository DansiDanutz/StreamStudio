/** Stage model. All card geometry is in fractions (0..1) of the Base card, so a layout
 *  survives any output resolution. Orientation picks which geometry set is active. */

export type Orientation = 'landscape' | 'portrait'
export type CardKind = 'main' | 'avatar' | 'menu'

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export interface CardLayout extends Rect {
  z: number
  visible: boolean
  locked: boolean
  radius: number // fraction of base width
}

export type Bezel = 'studio' | 'space' | 'violet' | 'ink' | 'teal' | 'mono'

/** A card the user adds to the stage: a video/image (often an animated object with alpha) placed by
 *  drag-and-drop, moved and resized like the core cards, with its own source. */
export interface MediaCard {
  id: string
  label: string
  /** Video or image URL. Alpha WebM clips (objects) composite with no box. */
  src: string
  /** Optional still shown when the video can't play (and used as the library thumbnail). */
  poster?: string
  layout: CardLayout
  /** Play once and hold the last frame (object arrival) or loop. */
  playback: 'once' | 'loop'
  /** Draw a card frame (border, radius, shadow) around the media. Off for transparent objects. */
  framed: boolean
}

export interface Scene {
  id: string
  name: string
  bezel: Bezel
  /** When false (default) the Menu card is transparent in the output. */
  menuShown: boolean
  layouts: Record<Orientation, Record<CardKind, CardLayout>>
  /** Cards added by the user, per orientation. */
  media?: Record<Orientation, MediaCard[]>
}

export const OUTPUT: Record<Orientation, { w: number; h: number }> = {
  landscape: { w: 1920, h: 1080 },
  portrait: { w: 1080, h: 1920 },
}

export const GRID = 0.02 // snap grid, fraction of base width
