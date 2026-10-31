import type { Rect } from './types'

/** Places in the studio plate (fractions of the 16:9 frame, measured on plate-landscape-final.png)
 *  that the presenter can point at, and that a Main card can open out of ("enter the monitor"). */
export interface Hotspot { id: string; label: string; rect: Rect }

export const HOTSPOTS: Hotspot[] = [
  { id: 'monitor', label: 'Fake-Real monitor', rect: { x: 0.642, y: 0.268, w: 0.185, h: 0.222 } },
  { id: 'trading', label: 'Trading screen', rect: { x: 0.838, y: 0.25, w: 0.162, h: 0.25 } },
  { id: 'table', label: 'Table (hero spot)', rect: { x: 0.42, y: 0.66, w: 0.16, h: 0.2 } },
]

export const hotspot = (id?: string) => HOTSPOTS.find((h) => h.id === id)
