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

let tabStream: MediaStream | null = null
const listeners = new Set<() => void>()
export const sharedTab = () => tabStream
export const onSharedTab = (fn: () => void) => { listeners.add(fn); return () => void listeners.delete(fn) }

/** Ask the browser to share a tab (needs a click). Resolves to the 'tab:' source, or null if cancelled. */
export async function shareTab(): Promise<string | null> {
  try {
    const s = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 30 }, audio: true })
    tabStream?.getTracks().forEach((t) => t.stop())
    tabStream = s
    s.getVideoTracks()[0]?.addEventListener('ended', () => { if (tabStream === s) { tabStream = null; listeners.forEach((f) => f()) } })
    listeners.forEach((f) => f())
    return 'tab:'
  } catch {
    return null
  }
}
