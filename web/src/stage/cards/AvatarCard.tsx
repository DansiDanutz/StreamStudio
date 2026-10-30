import { useState } from 'react'
import { useDirector } from '../../director/store'
import { useStage } from '../store'

/** Avatar card. S1: plays an avatar clip (Dan's lip-sync render) matched to the orientation.
 *  S4 adds the cut-out (background removal), scripted segments and live mode. */
const DEFAULT: Record<'landscape' | 'portrait', string> = {
  landscape: '/avatar/dan-landscape-test.mp4',
  portrait: '/avatar/dan-portrait-test.mp4',
}
/** Transparent (VP9 + alpha) cut-outs produced by `streamstudio.avatar.cutout`, keyed by clip URL. */
const CUTOUT: Record<string, string> = {
  '/avatar/dan-landscape-test.mp4': '/avatar/cutout/dan-landscape-test.cutout.webm',
  '/avatar/dan-portrait-test.mp4': '/avatar/cutout/dan-portrait-test.cutout.webm',
}
/** Where the cut-out stands when the card is full-frame: bottom edge at `anchorY`, height `scale`, centred at `x`.
 *  Matches the defaults in cutout.py so the preview and the composite agree. */
const STAND = { landscape: { x: 0.46, anchorY: 0.88, scale: 0.78 }, portrait: { x: 0.5, anchorY: 0.95, scale: 0.9 } }

export function AvatarCard() {
  const orientation = useStage((s) => s.orientation)
  const override = useStage((s) => s.avatarSrc)
  const setSource = useStage((s) => s.setSource)
  const playing = useDirector((s) => s.playing)
  const segClip = useDirector((s) => (s.current >= 0 ? s.script.segments[s.current]?.clip : undefined))
  const next = useDirector((s) => s.next)
  // On air with a segment clip: that clip is the voice (unmuted, no loop) and its end advances the script.
  const onAir = playing && !!segClip
  const src = onAir ? segClip! : (override ?? DEFAULT[orientation])
  const cutout = useStage((s) => s.cutout)
  const [missing, setMissing] = useState<Record<string, true>>({})
  const wanted = cutout ? CUTOUT[src] : undefined
  const alpha = wanted && !missing[wanted] ? wanted : undefined // fall back to the raw clip until a cut-out exists
  const stand = STAND[orientation]
  // With a cut-out the card is see-through: the studio plate shows behind, and the presenter stands at the desk.
  const style = alpha
    ? { position: 'absolute' as const, left: `${stand.x * 100}%`, bottom: `${(1 - stand.anchorY) * 100}%`, height: `${stand.scale * 100}%`, width: 'auto', transform: 'translateX(-50%)', objectFit: 'contain' as const, background: 'transparent' }
    : undefined
  return (
    <div className={`avatar-wrap ${alpha ? 'is-cutout' : ''}`}>
      <video key={(alpha ?? src) + (onAir ? '-air' : '')} className={alpha ? 'cutout' : 'fill cover'} style={style}
        src={alpha ?? src} autoPlay loop={!onAir} muted={!onAir} playsInline
        onEnded={() => onAir && next()}
        onError={(e) => (alpha ? setMissing((m) => ({ ...m, [alpha]: true })) : ((e.target as HTMLVideoElement).style.opacity = '0'))} />
      <label className="avatar-pick" onPointerDown={(e) => e.stopPropagation()} title="Replace avatar clip">
        ⤓
        <input type="file" accept="video/*" hidden onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) setSource('avatar', URL.createObjectURL(f))
        }} />
      </label>
      <span className="lipsync" aria-hidden><i /><i /><i /><i /></span>
    </div>
  )
}
