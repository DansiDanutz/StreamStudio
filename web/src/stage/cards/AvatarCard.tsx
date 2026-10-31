import { useState } from 'react'
import { useDirector } from '../../director/store'
import { lipsMatch } from '../../director/types'
import { IS_PROGRAM, useProgram } from '../../output/link'
import { gesture as findGesture, gestureClip } from '../../avatar/gestures'
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
/** Seating when the card is full-frame: presenter height `scale`, hands (at 85% of the clip) land at `handsY`,
 *  centred at `x`; the desk layer is drawn over the presenter so they sit behind it. Matches cutout.py. */
const HANDS_IN_CLIP = 0.85
const SEAT = { landscape: { x: 0.47, handsY: 0.68, scale: 0.66 }, portrait: { x: 0.5, handsY: 0.8, scale: 0.75 } }
const DESK: Record<'landscape' | 'portrait', string> = { landscape: '/studio/plate-landscape-final.desk.png', portrait: '/studio/plate-portrait-final.desk.png' }

export function AvatarCard() {
  const orientation = useStage((s) => s.orientation)
  const override = useStage((s) => s.avatarSrc)
  const setSource = useStage((s) => s.setSource)
  const playing = useDirector((s) => s.playing)
  const seg = useDirector((s) => (s.current >= 0 ? s.script.segments[s.current] : undefined))
  const next = useDirector((s) => s.next)
  // On air with a lip-synced clip: that clip is the voice (unmuted, no loop) and its end advances the script.
  // With separate narration the face is the idle clip, muted, and the narration track drives the timing.
  const onAir = playing && !!seg && lipsMatch(seg)
  // With a Program window open, the sound plays there (and is recorded there); the editor stays quiet.
  const quiet = useProgram((p) => p.connected) && !IS_PROGRAM
  const advance = () => { if (!IS_PROGRAM) next() } // only the editor drives the script
  const narration = playing && seg?.voice === 'narration' && seg.audio ? seg.audio : undefined
  const src = onAir ? seg!.clip! : (override ?? DEFAULT[orientation])
  const cutoutPref = useStage((s) => s.cutout)
  const fullFrame = useStage((s) => { const l = s.active().layouts[s.orientation].avatar; return l.w >= 0.999 && l.h >= 0.999 })
  const liveFull = useDirector((s) => { const l = s.live?.avatar; return l ? l.w >= 0.999 && l.h >= 0.999 : undefined })
  const isFull = liveFull ?? fullFrame
  // The cut-out is seated at the studio desk, so it only makes sense full frame; small cards show the raw clip.
  const cutout = cutoutPref && isFull
  const [missing, setMissing] = useState<Record<string, true>>({})
  const wanted = cutout ? CUTOUT[src] : undefined
  const alpha = wanted && !missing[wanted] ? wanted : undefined // fall back to the raw clip until a cut-out exists
  const seat = SEAT[orientation]
  const bottomY = seat.handsY + (1 - HANDS_IN_CLIP) * seat.scale
  // With a cut-out the card is see-through: the plate shows behind, the presenter sits at the desk,
  // and the desk layer (plate cut to the desk) is drawn on top so they are behind it.
  const style = alpha
    ? { position: 'absolute' as const, left: `${seat.x * 100}%`, bottom: `${(1 - bottomY) * 100}%`, height: `${seat.scale * 100}%`, width: 'auto', transform: 'translateX(-50%)', objectFit: 'contain' as const, background: 'transparent' }
    : undefined
  const showDesk = !!alpha && isFull
  // A gesture on air replaces the base clip until it ends (its voice clip starts after it).
  const gest = useDirector((s) => s.gesture)
  const g = gest && !gest.missing ? findGesture(gest.id) : undefined
  const gClip = g ? gestureClip(g) : undefined
  const seatedStyle = { position: 'absolute' as const, left: `${seat.x * 100}%`, bottom: `${(1 - bottomY) * 100}%`, height: `${seat.scale * 100}%`, width: 'auto', objectFit: 'contain' as const, background: 'transparent' }
  const gStyle = isFull
    ? { ...seatedStyle, transform: `translateX(-50%)${g?.mirrorOf ? ' scaleX(-1)' : ''}` }
    : { transform: g?.mirrorOf ? 'scaleX(-1)' : undefined }
  return (
    <div className={`avatar-wrap ${alpha ? 'is-cutout' : ''}`}>
      {gClip && gest
        ? <video key={`g${gest.seq}`} className={isFull ? 'cutout' : 'fill cover'} style={gStyle} src={gClip} autoPlay muted playsInline
            onEnded={() => useDirector.getState().endGesture(gest.seq)}
            onError={() => useDirector.getState().markGestureMissing(gest.seq)} />
        : <video key={(alpha ?? src) + (onAir ? '-air' : '')} className={alpha ? 'cutout' : 'fill cover'} style={style}
            src={alpha ?? src} autoPlay loop={!onAir} muted={!onAir || quiet} playsInline
            onEnded={() => onAir && advance()}
            onError={(e) => (alpha ? setMissing((m) => ({ ...m, [alpha]: true })) : ((e.target as HTMLVideoElement).style.opacity = '0'))} />}
      {narration && <audio key={narration} src={narration} autoPlay muted={quiet} onEnded={advance} />}
      {showDesk && <img className="desk" src={DESK[orientation]} alt="" draggable={false} onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />}
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
