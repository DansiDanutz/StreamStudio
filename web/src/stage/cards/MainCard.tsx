import { useDirector } from '../../director/store'
import { useStage } from '../store'
import { isImageUrl, tagUrl } from '../media'

/** Main card: what we capture. S1 ships a file source (video/image) so the stage is testable;
 *  screen share, URL and camera sources arrive in S2. */
export function MainCard() {
  const src = useStage((s) => s.mainSrc)
  const setSource = useStage((s) => s.setSource)
  const zoom = useDirector((s) => s.zoom)

  if (!src) {
    return (
      <label className="drop" onPointerDown={(e) => e.stopPropagation()}>
        <span className="drop-title">Main card</span>
        <span className="drop-sub">Drop a video or image, or click to choose. Screen share, URL and camera come in S2.</span>
        <input type="file" accept="video/*,image/*" hidden onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) setSource('main', tagUrl(f))
        }} />
      </label>
    )
  }
  const isVideo = !isImageUrl(src)
  // Zoom: scale about the target point; the transition is CSS so it eases with the layout tween.
  const style = zoom
    ? { transform: `scale(${zoom.scale})`, transformOrigin: `${zoom.x * 100}% ${zoom.y * 100}%` }
    : { transform: 'scale(1)', transformOrigin: '50% 50%' }
  return (
    <div className="zoom" style={style}>
      {isVideo
        ? <video className="fill" src={src} autoPlay loop muted playsInline />
        : <img className="fill" src={src} alt="" />}
    </div>
  )
}
