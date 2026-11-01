import { OBJECTS, objectClip, objectStill } from '../overlays/objects'
import { tagUrl } from './media'

/** What can be dragged onto the stage as a new card. Objects carry their alpha arrival clip. */
export interface LibraryItem {
  id: string
  label: string
  src: string
  poster: string
  playback: 'once' | 'loop'
  framed: boolean
  /** width as a fraction of the frame when dropped, and media aspect (w/h) */
  w: number
  aspect: number
}

/** Brand pieces: the DansLab logo-reveal intro (HyperFrames port of the channel intro, with its sound). */
export const BRAND: LibraryItem[] = [
  { id: 'danslab-intro', label: 'DansLab intro · logo reveal', src: '/brand/danslab-intro.mp4', poster: '/brand/danslab-intro.jpg', playback: 'once', framed: false, w: 1, aspect: 16 / 9 },
]

export const LIBRARY: LibraryItem[] = [...OBJECTS.map((o) => ({
  id: o.id,
  label: o.name,
  src: objectClip(o, 'arrive'),
  poster: objectStill(o),
  playback: 'once',
  framed: false,
  w: 0.24,
  aspect: 940 / 750,
}) as LibraryItem), ...BRAND]

export const DRAG_MIME = 'application/x-streamstudio-item'
/** A clip or take dragged from the Library: JSON {label, src}. */
export const DRAG_SRC_MIME = 'application/x-streamstudio-src'

export const fileToItem = (f: File): LibraryItem => ({
  id: 'file', label: f.name.replace(/\.[^.]+$/, ''), src: tagUrl(f), poster: '', playback: f.type.startsWith('image/') ? 'once' : 'loop',
  framed: true, w: 0.36, aspect: 16 / 9,
})
