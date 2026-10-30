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
  const src = override ?? DEFAULT[orientation]
  return (
    <div className="avatar-wrap">
      <video key={src} className="fill cover" src={src} autoPlay loop muted playsInline
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
