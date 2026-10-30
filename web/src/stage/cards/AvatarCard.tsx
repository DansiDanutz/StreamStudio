import { useDirector } from '../../director/store'
import { useStage } from '../store'

/** Avatar card. S1: plays an avatar clip (Dan's lip-sync render) matched to the orientation.
 *  S4 adds the cut-out (background removal), scripted segments and live mode. */
const DEFAULT: Record<'landscape' | 'portrait', string> = {
  landscape: '/avatar/dan-landscape-test.mp4',
  portrait: '/avatar/dan-portrait-test.mp4',
}

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
  return (
    <div className="avatar-wrap">
      <video key={src + (onAir ? '-air' : '')} className="fill cover" src={src} autoPlay loop={!onAir} muted={!onAir} playsInline
        onEnded={() => onAir && next()}
        onError={(e) => ((e.target as HTMLVideoElement).style.opacity = '0')} />
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
