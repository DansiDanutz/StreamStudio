/** Records the Program window: captures this tab, crops it to the Base card (Region Capture, Chrome),
 *  and records video + the tab's sound with MediaRecorder. MP4 when the browser can, else WebM. */

type Crop = { fromElement: (el: Element) => Promise<unknown> }
type CroppableTrack = MediaStreamTrack & { cropTo?: (t: unknown) => Promise<void> }

export const pickMime = (can: (t: string) => boolean = (t) => MediaRecorder.isTypeSupported(t)) =>
  ['video/mp4;codecs=avc1.640028,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm'].find(can) ?? ''

export interface Take { blob: Blob; mime: string; seconds: number }

export class Recorder {
  private rec: MediaRecorder | null = null
  private stream: MediaStream | null = null
  private chunks: Blob[] = []
  private t0 = 0
  cropped = false

  get recording() { return !!this.rec && this.rec.state === 'recording' }
  get seconds() { return this.recording ? Math.floor((performance.now() - this.t0) / 1000) : 0 }

  async start(target: Element): Promise<void> {
    const md = navigator.mediaDevices as MediaDevices & { getDisplayMedia: (o: object) => Promise<MediaStream> }
    this.stream = await md.getDisplayMedia({
      video: { frameRate: 30, displaySurface: 'browser' },
      audio: { suppressLocalAudioPlayback: false },
      preferCurrentTab: true, selfBrowserSurface: 'include', surfaceSwitching: 'exclude', systemAudio: 'include',
    })
    const track = this.stream.getVideoTracks()[0] as CroppableTrack
    const CropTarget = (globalThis as unknown as { CropTarget?: Crop }).CropTarget
    this.cropped = false
    if (CropTarget && track.cropTo) {
      try { await track.cropTo(await CropTarget.fromElement(target)); this.cropped = true } catch { /* whole tab */ }
    }
    const mime = pickMime()
    this.chunks = []
    this.rec = new MediaRecorder(this.stream, { mimeType: mime || undefined, videoBitsPerSecond: 16_000_000, audioBitsPerSecond: 192_000 })
    this.rec.ondataavailable = (e) => { if (e.data.size) this.chunks.push(e.data) }
    track.addEventListener('ended', () => { if (this.recording) this.rec!.stop() })
    this.rec.start(1000)
    this.t0 = performance.now()
  }

  stop(): Promise<Take> {
    const rec = this.rec
    if (!rec) return Promise.reject(new Error('not recording'))
    const seconds = this.seconds
    return new Promise((resolve) => {
      rec.onstop = () => {
        this.stream?.getTracks().forEach((t) => t.stop())
        const mime = (rec.mimeType || 'video/webm').split(';')[0]
        resolve({ blob: new Blob(this.chunks, { type: mime }), mime, seconds })
        this.rec = null
      }
      if (rec.state !== 'inactive') rec.stop(); else rec.onstop?.(new Event('stop'))
    })
  }
}

/** Upload a take to the Mac Studio (queues the MP4 job). Returns the recording id, or null offline. */
export async function uploadTake(take: Take): Promise<string | null> {
  try {
    const r = await fetch('/api/recordings', { method: 'POST', headers: { 'content-type': take.mime }, body: take.blob })
    if (!r.ok) return null
    return ((await r.json()) as { id: string }).id
  } catch {
    return null
  }
}
