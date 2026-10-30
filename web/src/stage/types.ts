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

export interface Scene {
  id: string
  name: string
  bezel: Bezel
  /** When false (default) the Menu card is transparent in the output. */
  menuShown: boolean
  layouts: Record<Orientation, Record<CardKind, CardLayout>>
}

export const OUTPUT: Record<Orientation, { w: number; h: number }> = {
  landscape: { w: 1920, h: 1080 },
  portrait: { w: 1080, h: 1920 },
}

export const GRID = 0.02 // snap grid, fraction of base width
