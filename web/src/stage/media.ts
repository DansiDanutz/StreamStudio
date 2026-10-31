/** Object URLs carry no extension, so we tag them with the media kind in the hash. */
export const tagUrl = (f: File) => URL.createObjectURL(f) + (f.type.startsWith('image/') ? '#img' : '#vid')
export const isImageUrl = (u: string) =>
  /#img$/.test(u) || /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(u) || u.startsWith('data:image')

/* ---- live sources for the Main card ----
 * 'url:https://…'  a web page in a scaled browser frame (sites that forbid framing need 'tab:')
 * 'tab:'           a shared tab/window/screen (getDisplayMedia); the stream lives here, not in the store */
export const isUrlSource = (s: string | null) => !!s && s.startsWith('url:')
export const urlOf = (s: string) => s.slice(4)
export const toUrlSource = (u: string) => `url:${/^https?:\/\//i.test(u.trim()) ? u.trim() : `https://${u.trim()}`}`

export type LiveKind = 'tab' | 'cam'
const streams: Record<LiveKind, MediaStream | null> = { tab: null, cam: null }
const listeners = new Set<() => void>()
export const liveStream = (k: LiveKind) => streams[k]
export const onLiveStream = (fn: () => void) => { listeners.add(fn); return () => void listeners.delete(fn) }
export const liveKindOf = (src: string | null): LiveKind | null => (src === 'tab:' ? 'tab' : src === 'cam:' ? 'cam' : null)

const keep = (k: LiveKind, s: MediaStream) => {
  streams[k]?.getTracks().forEach((t) => t.stop())
  streams[k] = s
  s.getVideoTracks()[0]?.addEventListener('ended', () => { if (streams[k] === s) { streams[k] = null; listeners.forEach((f) => f()) } })
  listeners.forEach((f) => f())
  return `${k}:`
}

/** Share a tab/window/screen (needs a click). Resolves to the 'tab:' source, or null if cancelled.
 *  A stream belongs to one window: the Program window asks once for its own. */
export async function shareTab(): Promise<string | null> {
  try { return keep('tab', await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 30 }, audio: true })) } catch { return null }
}

/** Use a camera (the built-in one, or a capture card / Continuity Camera). */
export async function shareCamera(): Promise<string | null> {
  try { return keep('cam', await navigator.mediaDevices.getUserMedia({ video: { width: 1920, height: 1080, frameRate: 30 }, audio: false })) } catch { return null }
}
