import { useRef, useState, type DragEvent, type PointerEvent } from 'react'
import { useStage } from './store'
import { useDirector } from '../director/store'
import { isImageUrl, tagUrl } from './media'
import type { MediaCard } from './types'

type Mode = 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
const HANDLES: Mode[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

/** A user-added card: any video or image, placed and sized by drag. Drop a file on it to replace its media.
 *  `once` clips (object arrivals) play to the end and hold the last frame; click ↻ to replay. */
export function MediaCardView({ card, baseW, baseH }: { card: MediaCard; baseW: number; baseH: number }) {
  const selected = useStage((s) => s.selectedMedia === card.id)
  const { setMediaRect, selectMedia, updateMedia, removeMedia } = useStage.getState()
  const drag = useRef<{ mode: Mode; sx: number; sy: number; start: MediaCard['layout'] } | null>(null)
  const vid = useRef<HTMLVideoElement>(null)
  const [over, setOver] = useState(false)
  const [broken, setBroken] = useState(false)
  const drive = useDirector((s) => s.mediaLive[card.id])
  const l = drive ? { ...card.layout, ...drive } : card.layout

  const onDown = (mode: Mode) => (e: PointerEvent) => {
    e.stopPropagation()
    selectMedia(card.id)
    if (l.locked) return
    ;(e.target as Element).setPointerCapture(e.pointerId)
    drag.current = { mode, sx: e.clientX, sy: e.clientY, start: { ...l } }
  }
  const onMove = (e: PointerEvent) => {
    const d = drag.current
    if (!d) return
    const dx = (e.clientX - d.sx) / baseW
    const dy = (e.clientY - d.sy) / baseH
    const s = d.start
    const r = { x: s.x, y: s.y, w: s.w, h: s.h }
    if (d.mode === 'move') { r.x += dx; r.y += dy }
    if (d.mode.includes('e')) r.w += dx
    if (d.mode.includes('s')) r.h += dy
    if (d.mode.includes('w')) { r.x += dx; r.w -= dx }
    if (d.mode.includes('n')) { r.y += dy; r.h -= dy }
    // corner handles keep the media's aspect unless Shift is held
    if (d.mode.length === 2 && !e.shiftKey) {
      const k = s.h / s.w
      const nh = r.w * k
      if (d.mode.includes('n')) r.y += r.h - nh
      r.h = nh
    }
    setMediaRect(card.id, r, !e.altKey)
  }
  const onUp = () => { drag.current = null }

  const onDrop = (e: DragEvent) => {
    const f = e.dataTransfer.files?.[0]
    setOver(false)
    if (!f) return
    e.preventDefault()
    e.stopPropagation()
    setBroken(false)
    updateMedia(card.id, { src: tagUrl(f), label: f.name.replace(/\.[^.]+$/, ''), playback: f.type.startsWith('image/') ? 'once' : card.playback })
  }

  if (!l.visible) return null
  const image = isImageUrl(card.src)
  return (
    <div
      className={`mcard ${drive ? 'is-live' : ''} ${card.framed ? 'is-framed' : ''} ${selected ? 'is-selected' : ''} ${over ? 'is-over' : ''}`}
      style={{ left: `${l.x * 100}%`, top: `${l.y * 100}%`, width: `${l.w * 100}%`, height: `${l.h * 100}%`, zIndex: l.z, borderRadius: l.radius * baseW }}
      onPointerDown={onDown('move')} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
      onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); e.stopPropagation(); setOver(true) } }}
      onDragLeave={() => setOver(false)} onDrop={onDrop}
    >
      {image || broken
        ? <img className="mcard-media" src={broken && card.poster ? card.poster : card.src} alt="" draggable={false} />
        : <video ref={vid} key={card.src + (drive?.seq ?? '')} className="mcard-media" src={card.src} autoPlay muted playsInline loop={card.playback === 'loop'}
            onError={() => setBroken(true)} />}
      {selected && (
        <>
          {HANDLES.map((h) => <span key={h} className={`handle handle-${h} editor-only`} onPointerDown={onDown(h)} onPointerMove={onMove} onPointerUp={onUp} />)}
          <div className="mcard-bar editor-only" onPointerDown={(e) => e.stopPropagation()}>
            <span className="mcard-name">{card.label}</span>
            <button title="Dan points at this card (T)" onClick={() => useDirector.getState().pointAt(`media:${card.id}`)}>☝</button>
            {!image && <button title="Replay" onClick={() => { const v = vid.current; if (v) { v.currentTime = 0; void v.play() } }}>↻</button>}
            {!image && <button title="Play once / loop" className={card.playback === 'loop' ? 'on' : ''} onClick={() => updateMedia(card.id, { playback: card.playback === 'loop' ? 'once' : 'loop' })}>∞</button>}
            <button title="Card frame" className={card.framed ? 'on' : ''} onClick={() => updateMedia(card.id, { framed: !card.framed })}>▢</button>
            <label title="Replace media (or drop a file on the card)">⤓<input type="file" accept="video/*,image/*" hidden onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) { setBroken(false); updateMedia(card.id, { src: tagUrl(f), label: f.name.replace(/\.[^.]+$/, '') }) }
            }} /></label>
            <button title="Remove (Delete)" onClick={() => removeMedia(card.id)}>✕</button>
          </div>
        </>
      )}
    </div>
  )
}
