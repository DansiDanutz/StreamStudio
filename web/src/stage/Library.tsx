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

export const LIBRARY: LibraryItem[] = OBJECTS.map((o) => ({
  id: o.id,
  label: o.name,
  src: objectClip(o, 'arrive'),
  poster: objectStill(o),
  playback: 'once',
  framed: false,
  w: 0.24,
  aspect: 940 / 750,
}))

export const DRAG_MIME = 'application/x-streamstudio-item'

/** Library panel: drag an item (or a video/image file) onto the stage to add it as a card. */
export function Library({ onAddFile }: { onAddFile: (f: File) => void }) {
  return (
    <div className="library">
      <div className="lib-head">
        <div className="lbl">Library</div>
        <p>Drag onto the stage to add a card. Drop a video on any card to replace what plays in it.</p>
      </div>
      <div className="lib-grid">
        {LIBRARY.map((it) => (
          <div key={it.id} className="lib-item" draggable title={`Drag ${it.label} onto the stage`}
            onDragStart={(e) => { e.dataTransfer.setData(DRAG_MIME, it.id); e.dataTransfer.effectAllowed = 'copy' }}>
            <img src={it.poster} alt="" draggable={false} />
            <span>{it.label}</span>
          </div>
        ))}
        <label className="lib-item lib-upload" title="Add your own video or image as a card">
          <span className="plus">+</span>
          <span>Video or image</span>
          <input type="file" accept="video/*,image/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onAddFile(f) }} />
        </label>
      </div>
    </div>
  )
}

export const fileToItem = (f: File): LibraryItem => ({
  id: 'file', label: f.name.replace(/\.[^.]+$/, ''), src: tagUrl(f), poster: '', playback: f.type.startsWith('image/') ? 'once' : 'loop',
  framed: true, w: 0.36, aspect: 16 / 9,
})
