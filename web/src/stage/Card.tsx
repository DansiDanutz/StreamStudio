import { useRef, type PointerEvent, type ReactNode } from 'react'
import { useDirector } from '../director/store'
import { useStage } from './store'
import type { CardKind } from './types'

interface Props {
  kind: CardKind
  /** Base card size in CSS px, for converting pointer deltas into fractions. */
  baseW: number
  baseH: number
  className?: string
  children: ReactNode
}

type Mode = 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
const HANDLES: Mode[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

/** A card inside the Base card: positioned in fractions, draggable and resizable with pointer events. */
export function Card({ kind, baseW, baseH, className = '', children }: Props) {
  const saved = useStage((s) => s.active().layouts[s.orientation][kind])
  const live = useDirector((s) => s.live?.[kind])
  // While the director drives, cards follow the tweened live geometry (menu is never driven).
  const layout = live ? { ...saved, ...live, visible: live.visible ?? saved.visible, radius: live.radius ?? saved.radius, z: live.z ?? saved.z } : saved
  const selected = useStage((s) => s.selected === kind)
  const { setRect, select, bringToFront } = useStage.getState()
  const drag = useRef<{ mode: Mode; sx: number; sy: number; start: typeof layout } | null>(null)

  const onDown = (mode: Mode) => (e: PointerEvent) => {
    if (layout.locked) return
    e.stopPropagation()
    ;(e.target as Element).setPointerCapture(e.pointerId)
    drag.current = { mode, sx: e.clientX, sy: e.clientY, start: { ...layout } }
    select(kind)
    bringToFront(kind)
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
    setRect(kind, r, !e.altKey) // hold Alt for free (unsnapped) placement
  }
  const onUp = () => { drag.current = null }

  if (!layout.visible) return null
  return (
    <div
      className={`card card-${kind} ${selected ? 'is-selected' : ''} ${layout.locked ? 'is-locked' : ''} ${live ? 'is-live' : ''} ${layout.w >= 0.999 && layout.h >= 0.999 ? 'is-fullframe' : ''} ${className}`}
      style={{
        left: `${layout.x * 100}%`, top: `${layout.y * 100}%`,
        width: `${layout.w * 100}%`, height: `${layout.h * 100}%`,
        zIndex: layout.z, borderRadius: layout.radius * baseW,
      }}
      onPointerDown={onDown('move')}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
    >
      <div className="card-body">{children}</div>
      {selected && !layout.locked && HANDLES.map((h) => (
        <span key={h} className={`handle handle-${h}`} onPointerDown={onDown(h)} onPointerMove={onMove} onPointerUp={onUp} />
      ))}
      {selected && <span className="card-tag">{kind}{layout.locked ? ' · locked' : ''}</span>}
    </div>
  )
}
