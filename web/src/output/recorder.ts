/** Records the Program window: captures this tab, crops it to the Base card (Region Capture, Chrome),
 *  and records video + the tab's sound with MediaRecorder. MP4 when the browser can, else WebM. */

type Crop = { fromElement: (el: Element) => Promise<unknown> }
type CroppableTrack = MediaStreamTrack & { cropTo?: (t: unknown) => Promise<void> }

/** WebM streams chunk by chunk (needed for live, and the server makes the MP4 anyway); MP4 is only
 *  preferred when there is no server and the take is downloaded as is. Chrome's MP4 recorder holds
 *  most of the data until the end, so it can't feed a live stream. */
export const pickMime = (can: (t: string) => boolean = (t) => MediaRecorder.isTypeSupported(t), streamable = true) =>
  (streamable
    ? ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4']
    : ['video/mp4;codecs=avc1.640028,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm']
  ).find(can) ?? ''

export interface Take { blob: Blob; mime: string; seconds: number }

export class Recorder {
  private rec: MediaRecorder | null = null
  private stream: MediaStream | null = null
  private chunks: Blob[] = []
  private t0 = 0
  private header: Blob | null = null
  cropped = false
  /** Extra consumer of the encoded chunks (the live stream). Gets the header chunk first. */
  private tap: ((b: Blob) => void) | null = null
  setTap(fn: ((b: Blob) => void) | null) {
    this.tap = fn
    if (fn && this.header) fn(this.header) // joining mid-take: replay the init segment
  }

  get recording() { return !!this.rec && this.rec.state === 'recording' }
  get seconds() { return this.recording ? Math.floor((performance.now() - this.t0) / 1000) : 0 }

  async start(target: Element, timeslice = 1000, streamable = true, frameRate: 30 | 60 = 30): Promise<void> {
    const md = navigator.mediaDevices as MediaDevices & { getDisplayMedia: (o: object) => Promise<MediaStream> }
    this.stream = await md.getDisplayMedia({
      video: { frameRate, displaySurface: 'browser' },
      audio: { suppressLocalAudioPlayback: false },
      preferCurrentTab: true, selfBrowserSurface: 'include', surfaceSwitching: 'exclude', systemAudio: 'include',
    })
    const track = this.stream.getVideoTracks()[0] as CroppableTrack
    const CropTarget = (globalThis as unknown as { CropTarget?: Crop }).CropTarget
    this.cropped = false
    if (CropTarget && track.cropTo) {
      try { await track.cropTo(await CropTarget.fromElement(target)); this.cropped = true } catch { /* whole tab */ }
    }
    const mime = pickMime(undefined, streamable)
    this.chunks = []
    this.header = null
    this.rec = new MediaRecorder(this.stream, { mimeType: mime || undefined, videoBitsPerSecond: 16_000_000, audioBitsPerSecond: 192_000 })
    this.rec.ondataavailable = (e) => {
      if (!e.data.size) return
      if (!this.header) this.header = e.data
      this.chunks.push(e.data)
      this.tap?.(e.data)
    }
    track.addEventListener('ended', () => { if (this.recording) this.rec!.stop() })
    this.rec.start(timeslice)
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

/** Live: forwards encoded chunks to the Mac Studio, which pushes RTMP to YouTube. */
export class LiveLink {
  private ws: WebSocket | null = null
  private queue: Blob[] = []
  onEnd: ((reason: string) => void) | null = null

  get on() { return !!this.ws && this.ws.readyState <= 1 }

  open(): Promise<void> {
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/live/ws`
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url)
      ws.binaryType = 'arraybuffer'
      this.ws = ws
      ws.onopen = () => { resolve(); this.flush() }
      ws.onerror = () => reject(new Error('cannot reach the StreamStudio server'))
      ws.onclose = (e) => {
        this.ws = null
        this.onEnd?.(e.code === 4400 ? 'No stream key saved.' : e.code === 4409 ? 'Already live from another window.' : e.code === 1000 || e.code === 1005 ? '' : 'The live connection dropped.')
      }
    })
  }
  send(b: Blob) { this.queue.push(b); this.flush() }
  private async flush() {
    const ws = this.ws
    if (!ws || ws.readyState !== 1) return
    while (this.queue.length) ws.send(await this.queue.shift()!.arrayBuffer())
  }
  /** Ask the server to finish the broadcast; resolves when it has. */
  close(): Promise<void> {
    const ws = this.ws
    if (!ws) return Promise.resolve()
    return new Promise((resolve) => {
      ws.addEventListener('close', () => resolve(), { once: true })
      try { ws.send('stop') } catch { ws.close() }
      setTimeout(() => { try { ws.close() } catch { /* gone */ } resolve() }, 20_000)
    })
  }
}
