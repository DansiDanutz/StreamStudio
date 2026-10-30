import { useEffect, useRef, useState } from 'react'
import { SKETCHES, type Glyph } from './sketches'

/** Draws sketches on the desk plane. The plane is the desk's quad: far edge at `edgeY` of the frame,
 *  near edge at the bottom; a CSS 3D transform foreshortens it like a real table top. */
export function DeskSketch({ stack, edgeY = 0.664 }: { stack: string[]; edgeY?: number }) {
  return (
    <div className="desk-plane-host" style={{ top: `${edgeY * 100}%` }} aria-hidden>
      <div className="desk-plane">
        <svg viewBox="0 0 1000 400" preserveAspectRatio="none" className="desk-svg">
          <defs>
            <filter id="chalk-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.2" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {stack.map((id, i) => SKETCHES[id]?.glyphs.map((g) => <GlyphView key={`${id}-${g.id}-${i}`} g={g} />))}
        </svg>
      </div>
    </div>
  )
}

function GlyphView({ g }: { g: Glyph }) {
  const refs = useRef<(SVGPathElement | null)[]>([])
  const [lens, setLens] = useState<number[]>([])
  useEffect(() => {
    setLens(refs.current.map((p) => (p ? p.getTotalLength() : 0)))
  }, [g])
  const s = (g.scale ?? 1) * 0.58 // glyphs are authored large; the desk gets them at ~58%
  return (
    <g transform={`translate(${g.x} ${g.y}) scale(${s})`} filter="url(#chalk-glow)">
      {g.strokes.map((st, i) => (
        <path key={i} ref={(el) => { refs.current[i] = el }} d={st.d} className={`chalk chalk-${st.color ?? 'teal'}`}
          strokeWidth={st.width ?? 2.5}
          style={lens[i] ? { strokeDasharray: lens[i], strokeDashoffset: lens[i], animation: `draw ${Math.max(0.5, Math.min(1.6, lens[i] / 450))}s ease-out ${st.delay ?? 0}s forwards` } : { opacity: 0 }} />
      ))}
      {g.label && (
        <text className="chalk-label" x={0} y={(g.labelDy ?? 90) * 0.9} textAnchor="middle" style={{ animation: `fadein .6s ease ${1.2}s forwards` }}>{g.label}</text>
      )}
    </g>
  )
}
