import { useStage } from '../store'

/** Main card: what we capture. S1 ships a file source (video/image) so the stage is testable;
 *  screen share, URL and camera sources arrive in S2. */
export function MainCard() {
  const src = useStage((s) => s.mainSrc)
  const setSource = useStage((s) => s.setSource)

  if (!src) {
    return (
      <label className="drop" onPointerDown={(e) => e.stopPropagation()}>
        <span className="drop-title">Main card</span>
        <span className="drop-sub">Drop a video or image, or click to choose. Screen share, URL and camera come in S2.</span>
        <input type="file" accept="video/*,image/*" hidden onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) setSource('main', URL.createObjectURL(f))
        }} />
      </label>
    )
  }
  const isVideo = !/\.(png|jpe?g|webp|gif)(\?|$)/i.test(src) && !src.startsWith('data:image')
  return isVideo
    ? <video className="fill" src={src} autoPlay loop muted playsInline />
    : <img className="fill" src={src} alt="" />
}
