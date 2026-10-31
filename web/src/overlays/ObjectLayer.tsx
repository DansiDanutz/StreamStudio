import { useEffect, useRef, useState } from 'react'
import { HERO, OBJECTS, objectClip, objectStill, type ObjectDef, type ObjectPhase } from './objects'

export type TableState = Record<string, { phase: ObjectPhase; seq: number; dim?: boolean }>

/** Objects on the desk. Each object has a transparent arrive clip (particles gather into the object) and a
 *  leave clip (the object breaks into particles). After arriving it holds on the last frame (the complete
 *  object) and floats; `react` pulses it; `leave` plays the dissolve and then it is gone.
 *  Falls back to the matted still (cutout.png) when an object has no clips yet. */
export function ObjectLayer({ table, onGone }: { table: TableState; onGone?: (id: string) => void }) {
  return (
    <div className="object-layer" aria-hidden>
      {OBJECTS.map((o) => {
        const st = table[o.id]
        if (!st || st.phase === 'gone') return null
        return <ObjectView key={o.id} o={o} phase={st.phase} seq={st.seq} dim={!!st.dim} onGone={() => onGone?.(o.id)} />
      })}
    </div>
  )
}

const HOLD_MS = 2600 // time at the hero spot while Dan introduces it
const DISC_PX = 520 // every clip and still is normalised so the light disc is this wide

function ObjectView({ o, phase, seq, dim, onGone }: { o: ObjectDef; phase: Exclude<ObjectPhase, 'gone'>; seq: number; dim: boolean; onGone: () => void }) {
  const [atHero, setAtHero] = useState(phase === 'arrive')
  const [noClip, setNoClip] = useState(false)
  const [natW, setNatW] = useState(880)
  const vid = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    if (phase !== 'arrive') return
    setAtHero(true)
    const t = setTimeout(() => setAtHero(false), HOLD_MS)
    return () => clearTimeout(t)
  }, [phase, seq])
  const clip = phase === 'leave' ? 'leave' : 'arrive'
  // arrive plays once and freezes on its last frame; for idle/react (no arrival seen) jump straight to the end
  const onMeta = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const v = e.currentTarget
    setNatW(v.videoWidth || 880)
    if (phase === 'idle' || phase === 'react') { v.pause(); v.currentTime = Math.max(0, v.duration - 0.05) }
  }
  const spot = atHero ? HERO : o
  const style = {
    left: `${spot.x * 100}%`, top: `${spot.y * 100}%`, width: `${spot.scale * 100 * (natW / DISC_PX)}%`,
    transform: 'translate(-50%, -75%)', opacity: dim ? 0.4 : 1,
  }
  const cls = `object ${phase === 'arrive' && noClip ? 'is-arriving' : ''} ${phase === 'react' ? 'is-reacting' : ''} ${phase !== 'leave' ? 'is-floating' : ''}`
  return (
    <div className={cls} style={style}>
      {noClip
        ? <img className="object-media" src={objectStill(o)} alt="" draggable={false} onLoad={(e) => setNatW(e.currentTarget.naturalWidth)} />
        : <video ref={vid} key={clip + seq} className="object-media" src={objectClip(o, clip)} autoPlay={phase === 'arrive' || phase === 'leave'} muted playsInline
            onLoadedMetadata={onMeta} onEnded={() => { if (phase === 'leave') onGone() }} onError={() => { setNoClip(true); if (phase === 'leave') onGone() }} />}
    </div>
  )
}
