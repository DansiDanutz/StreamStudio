import { useLayoutEffect, useRef, useState } from 'react'
import { Card } from './Card'
import { AvatarCard } from './cards/AvatarCard'
import { MainCard } from './cards/MainCard'
import { MenuCard } from './cards/MenuCard'
import { useStage } from './store'
import { Starfield } from './Starfield'
import { useDirector } from '../director/store'
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
  const live = useDirector((s) => s.live)
  // Focus rule: the studio plate is for the presenter alone. As soon as any card is on screen
  // (anything but a full-frame avatar), the backdrop recedes to a calm starfield.
  const layouts = scene.layouts[orientation]
  const eff = (k: 'main' | 'avatar') => ({ ...layouts[k], ...(live?.[k] ?? {}) })
  const av = eff('avatar'), mn = eff('main')
  const avatarAlone = av.visible !== false && av.w >= 0.999 && av.h >= 0.999 && mn.visible === false
  const backdrop: 'studio' | 'space' | typeof scene.bezel = scene.bezel === 'studio' ? (avatarAlone ? 'studio' : 'space') : scene.bezel
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
        className={`base bezel-${backdrop} ${orientation}`}
        style={{ width: size.w, height: size.h, fontSize: orientation === 'landscape' ? size.w / 100 : size.w / 56 /* 1em ≈ 1% of the long edge */ }}
      >
        {scene.bezel === 'studio' && (
          <>
            {/* Both backdrops stay mounted and cross-fade, so studio ↔ space is a dissolve, never a cut. */}
            <div className={`backdrop ${backdrop === 'space' ? 'is-on' : ''}`}><Starfield /></div>
            <img className={`plate backdrop ${backdrop === 'studio' ? 'is-on' : ''}`} src={plate} alt="" draggable={false}
              onError={() => plate !== PLATE.landscape && setPlate(PLATE.landscape)} />
          </>
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
