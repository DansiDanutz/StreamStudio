import { useDirector } from '../director/store'

/** Stand-in for a gesture whose clip has not been made yet: a light sweep from the presenter's
 *  hands to the target and a pulse around it, for the gesture's length. Output-safe and subtle. */
export function PointerCue() {
  const g = useDirector((s) => s.gesture)
  if (!g || !g.to) return null
  if (!g.missing) {
    // a real gesture clip is playing: just a soft ring on what Dan points at
    return (
      <svg key={g.seq} className="pointer-cue" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ ['--ms' as string]: `${g.ms}ms` }}>
        <rect className="pc-ring soft" x={g.to.x * 100} y={g.to.y * 100} width={g.to.w * 100} height={g.to.h * 100} rx="0.8" />
      </svg>
    )
  }
  const fx = (g.from.x + g.from.w / 2) * 100
  const fy = (g.from.y + g.from.h * 0.7) * 100
  const tx = (g.to.x + g.to.w / 2) * 100
  const ty = (g.to.y + g.to.h / 2) * 100
  return (
    <svg key={g.seq} className="pointer-cue" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ ['--ms' as string]: `${g.ms}ms` }}>
      <defs>
        <linearGradient id={`pc${g.seq}`} x1={fx} y1={fy} x2={tx} y2={ty} gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#ffd28a" stopOpacity=".95" />
        </linearGradient>
      </defs>
      <path className="pc-line" d={`M${fx},${fy} Q${(fx + tx) / 2},${Math.min(fy, ty) - 8} ${tx},${ty}`} stroke={`url(#pc${g.seq})`} />
      <rect className="pc-ring" x={g.to.x * 100} y={g.to.y * 100} width={g.to.w * 100} height={g.to.h * 100} rx="0.8" />
    </svg>
  )
}
