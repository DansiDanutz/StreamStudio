import { useEffect, useState } from 'react'
import { HERO, OBJECTS, objectClip, objectStill, type ObjectDef, type ObjectPhase } from './objects'

export type TableState = Record<string, { phase: ObjectPhase; seq: number; dim?: boolean }>

/** Objects standing on the desk. Each object is its matted still (cutout.png) or, once generated, its
 *  video clips. An arriving object rises in at the hero spot, holds, then glides to its own place. */
export function ObjectLayer({ table }: { table: TableState }) {
  return (
    <div className="object-layer" aria-hidden>
      {OBJECTS.map((o) => {
        const st = table[o.id]
        if (!st || st.phase === 'gone') return null
        return <ObjectView key={o.id} o={o} phase={st.phase} seq={st.seq} dim={!!st.dim} />
      })}
    </div>
  )
}

const HOLD_MS = 2600 // time at the hero spot while Dan introduces it

function ObjectView({ o, phase, seq, dim }: { o: ObjectDef; phase: Exclude<ObjectPhase, 'gone'>; seq: number; dim: boolean }) {
  const [atHero, setAtHero] = useState(phase === 'arrive')
  const [hasClip, setHasClip] = useState(true)
  useEffect(() => {
    if (phase !== 'arrive') return
    setAtHero(true)
    const t = setTimeout(() => setAtHero(false), HOLD_MS)
    return () => clearTimeout(t)
  }, [phase, seq])
  const spot = atHero ? HERO : o
  // width in % of frame; the cut-outs are normalised so the light disc sits at ~78% of their height
  const style = {
    left: `${spot.x * 100}%`, top: `${spot.y * 100}%`, width: `${spot.scale * 100 * 1.7}%`,
    transform: 'translate(-50%, -78%)', opacity: dim ? 0.4 : 1,
  }
  const cls = `object ${phase === 'arrive' ? 'is-arriving' : ''} ${phase === 'react' ? 'is-reacting' : ''}`
  return (
    <div className={cls} style={style} key={seq}>
      {hasClip
        ? <video className="object-media" src={objectClip(o, phase === 'react' ? 'react' : 'idle')} autoPlay muted playsInline loop onError={() => setHasClip(false)} />
        : <img className="object-media" src={objectStill(o)} alt="" draggable={false} />}
    </div>
  )
}
