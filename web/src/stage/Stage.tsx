import { useLayoutEffect, useRef, useState } from 'react'
import { Card } from './Card'
import { AvatarCard } from './cards/AvatarCard'
import { MainCard } from './cards/MainCard'
import { MenuCard } from './cards/MenuCard'
import { useStage } from './store'
import { OUTPUT } from './types'

const PLATE: Record<'landscape' | 'portrait', string> = {
  landscape: '/studio/plate-landscape-final.png',
  portrait: '/studio/plate-portrait-final.png', // not generated yet: falls back to the landscape plate, cover-fit
}

/** The Base card: the output frame, scaled to fit its container, with the studio plate behind everything. */
export function Stage() {
  const orientation = useStage((s) => s.orientation)
  const scene = useStage((s) => s.active())
  const guides = useStage((s) => s.guides)
  const select = useStage((s) => s.select)
  const host = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 960, h: 540 })

  useLayoutEffect(() => {
    const el = host.current!
    const fit = () => {
      const { w, h } = OUTPUT[orientation]
      const r = el.getBoundingClientRect()
      const k = Math.min(r.width / w, r.height / h)
      setSize({ w: Math.floor(w * k), h: Math.floor(h * k) })
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(el)
    return () => ro.disconnect()
  }, [orientation])

  const [plate, setPlate] = useState(PLATE[orientation])
  useLayoutEffect(() => setPlate(PLATE[orientation]), [orientation])

  return (
    <div ref={host} className="stage-host" onPointerDown={() => select(null)}>
      <div
        className={`base bezel-${scene.bezel} ${orientation}`}
        style={{ width: size.w, height: size.h, fontSize: orientation === 'landscape' ? size.w / 100 : size.w / 56 /* 1em ≈ 1% of the long edge */ }}
      >
        {scene.bezel === 'studio' && (
          <img className="plate" src={plate} alt="" draggable={false}
            onError={() => plate !== PLATE.landscape && setPlate(PLATE.landscape)} />
        )}
        {guides && <div className="safe" />}
        <Card kind="main" baseW={size.w} baseH={size.h}><MainCard /></Card>
        <Card kind="avatar" baseW={size.w} baseH={size.h}><AvatarCard /></Card>
        <Card kind="menu" baseW={size.w} baseH={size.h} className={scene.menuShown ? '' : 'card-ghost'}><MenuCard /></Card>
        <div className="base-label">{OUTPUT[orientation].w}×{OUTPUT[orientation].h} · {scene.name}</div>
      </div>
    </div>
  )
}
