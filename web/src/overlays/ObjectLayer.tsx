import { useEffect, useRef, useState } from 'react'
import { OBJECTS, PLACEHOLDER, objectClip, type ObjectDef, type ObjectPhase } from './objects'

export type TableState = Record<string, { phase: ObjectPhase; seq: number; dim?: boolean }>

/** Draws the objects standing on the desk. Clips are on black and screen-blended over the plate. */
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

function ObjectView({ o, phase, seq, dim }: { o: ObjectDef; phase: Exclude<ObjectPhase, 'gone'>; seq: number; dim: boolean }) {
  const [src, setSrc] = useState(objectClip(o, phase))
  const [cur, setCur] = useState<Exclude<ObjectPhase, 'gone'>>(phase)
  const ref = useRef<HTMLVideoElement>(null)
  useEffect(() => { setCur(phase); setSrc(objectClip(o, phase)) }, [o, phase, seq])
  // The clip is 1920×1080 with the object centred: size it so the object's footprint lands at (x, y).
  const h = o.scale / 0.3 // clips frame the object at ~30% of their height
  const style = {
    left: `${o.x * 100}%`, top: `${o.y * 100}%`, height: `${h * 100}%`, aspectRatio: '16/9',
    transform: 'translate(-50%, -62%)', opacity: dim ? 0.35 : 1,
  }
  return (
    <video ref={ref} key={src + seq} className="object-clip" style={style} src={src} autoPlay muted playsInline
      loop={cur === 'idle'}
      onEnded={() => { if (cur !== 'idle') { setCur('idle'); setSrc(objectClip(o, 'idle')) } }}
      onError={() => { if (!src.includes('_placeholder')) setSrc(PLACEHOLDER(cur)) }} />
  )
}
