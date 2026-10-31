import { useEffect, useRef, useState } from 'react'
import { useDirector } from '../../director/store'
import { useStage } from '../store'
import { isImageUrl, isUrlSource, liveKindOf, liveStream, onLiveStream, shareCamera, shareTab, tagUrl, toUrlSource, urlOf, type LiveKind } from '../media'

/** Browser frame: the page renders at a desktop size and is scaled to the card, so a card that
 *  grows out of the studio monitor looks like the same screen coming closer. */
const VIEW_W = 1440

/** Main card: what we capture. Sources: a file, a web page (URL), or a shared tab/window. */
export function MainCard() {
  const src = useStage((s) => s.mainSrc)
  const setSource = useStage((s) => s.setSource)
  const zoom = useDirector((s) => s.zoom)
  const [asking, setAsking] = useState(false)

  if (!src) {
    return (
      <div className="drop" onPointerDown={(e) => e.stopPropagation()}>
        <span className="drop-title">Main card</span>
        <span className="drop-sub">What do you want to show?</span>
        <div className="drop-actions">
          <label className="btn">File<input type="file" accept="video/*,image/*" hidden onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) setSource('main', tagUrl(f))
          }} /></label>
          {asking
            ? <form onSubmit={(e) => { e.preventDefault(); const v = new FormData(e.currentTarget).get('u') as string; if (v) setSource('main', toUrlSource(v)) }}>
                <input name="u" autoFocus placeholder="fake-real.live" defaultValue="https://fake-real.live" />
              </form>
            : <button className="btn" onClick={() => setAsking(true)}>Web page</button>}
          <button className="btn" onClick={async () => { const s = await shareTab(); if (s) setSource('main', s) }}>Share a tab</button>
          <button className="btn" onClick={async () => { const s = await shareCamera(); if (s) setSource('main', s) }}>Camera</button>
        </div>
      </div>
    )
  }
  // Zoom: scale about the target point; the transition is CSS so it eases with the layout tween.
  const style = zoom
    ? { transform: `scale(${zoom.scale})`, transformOrigin: `${zoom.x * 100}% ${zoom.y * 100}%` }
    : { transform: 'scale(1)', transformOrigin: '50% 50%' }
  return (
    <div className="zoom" style={style}>
      {liveKindOf(src) ? <LiveView kind={liveKindOf(src)!} />
        : isUrlSource(src) ? <BrowserView url={urlOf(src)} />
        : isImageUrl(src) ? <img className="fill" src={src} alt="" />
        : <video className="fill" src={src} autoPlay loop muted playsInline />}
      <button className="source-x" title="Change what the Main card shows" onPointerDown={(e) => e.stopPropagation()} onClick={() => setSource('main', null)}>⟲</button>
    </div>
  )
}

function BrowserView({ url }: { url: string }) {
  const box = useRef<HTMLDivElement>(null)
  const [k, setK] = useState(1)
  useEffect(() => {
    const el = box.current!
    const fit = () => setK(el.clientWidth / VIEW_W)
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const host = (() => { try { return new URL(url).host } catch { return url } })()
  return (
    <div ref={box} className="browser">
      <div className="browser-bar"><i /><i /><i /><span>{host}</span></div>
      <div className="browser-page">
        <iframe title={host} src={url} style={{ width: VIEW_W, height: `${100 / k}%`, transform: `scale(${k})` }}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups" referrerPolicy="no-referrer" />
      </div>
    </div>
  )
}

function LiveView({ kind }: { kind: LiveKind }) {
  const v = useRef<HTMLVideoElement>(null)
  const [, bump] = useState(0)
  useEffect(() => onLiveStream(() => bump((n) => n + 1)), [])
  const stream = liveStream(kind)
  useEffect(() => { if (v.current) v.current.srcObject = stream }, [stream])
  if (!stream) {
    // A stream lives in one window: the Program window (or a reload) needs its own.
    return (
      <div className="drop live-ask" onPointerDown={(e) => e.stopPropagation()}>
        <span className="drop-sub">{kind === 'tab' ? 'Share the tab to show here.' : 'Connect the camera here.'}</span>
        <button className="btn" onClick={() => void (kind === 'tab' ? shareTab() : shareCamera())}>{kind === 'tab' ? 'Share a tab' : 'Use the camera'}</button>
      </div>
    )
  }
  return <video ref={v} className="fill" autoPlay muted playsInline />
}
