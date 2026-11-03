import { describe, expect, it, vi } from 'vitest'
import { pickMime, Recorder, uploadTake } from './recorder'
import { liveKindOf } from '../stage/media'

describe('recording output', () => {
  it('streams WebM when a server takes the chunks; MP4 only for a download-only take', () => {
    expect(pickMime(() => true)).toBe('video/webm;codecs=vp9,opus')
    expect(pickMime(() => true, false)).toMatch(/^video\/mp4/)
    expect(pickMime((t) => t.startsWith('video/webm'), false)).toBe('video/webm;codecs=vp9,opus')
    expect(pickMime(() => false)).toBe('')
  })
  it('requests the chosen capture rate and defaults to 30 fps', async () => {
    const getDisplayMedia = vi.fn().mockRejectedValue(new Error('capture cancelled'))
    vi.stubGlobal('navigator', { mediaDevices: { getDisplayMedia } })
    try {
      for (const rate of [undefined, 60] as const) {
        await expect(new Recorder().start(document.body, 500, true, rate))
          .rejects.toThrow('capture cancelled')
        expect(getDisplayMedia).toHaveBeenLastCalledWith(expect.objectContaining({
          video: expect.objectContaining({ frameRate: rate ?? 30 }),
        }))
      }
    } finally {
      vi.unstubAllGlobals()
    }
  })
  it('delivers the final chunk once when the browser ends sharing', async () => {
    const track = Object.assign(new EventTarget(), { stop: vi.fn() })
    const stream = { getVideoTracks: () => [track], getTracks: () => [track] }
    class Capture {
      static isTypeSupported() { return true }
      state = 'inactive'
      mimeType = 'video/webm'
      ondataavailable?: (event: { data: Blob }) => void
      onstop?: () => void
      start() { this.state = 'recording' }
      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob(['final']) })
        this.onstop?.()
      }
    }
    vi.stubGlobal('navigator', { mediaDevices: { getDisplayMedia: async () => stream } })
    vi.stubGlobal('MediaRecorder', Capture)
    try {
      const recorder = new Recorder()
      const saved = vi.fn()
      recorder.onTake = saved
      await recorder.start(document.body)
      track.dispatchEvent(new Event('ended'))
      track.dispatchEvent(new Event('ended'))
      expect(saved).toHaveBeenCalledTimes(1)
      expect(saved.mock.calls[0][0].blob.size).toBe(5)
      expect(track.stop).toHaveBeenCalledOnce()
    } finally {
      vi.unstubAllGlobals()
    }
  })
  it('skips upload when the encoder returns an empty blob', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    try {
      expect(await uploadTake({ blob: new Blob(), mime: 'video/webm', seconds: 4 })).toBeNull()
      expect(fetch).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllGlobals()
    }
  })
  it('knows which Main-card sources are live streams', () => {
    expect(liveKindOf('tab:')).toBe('tab')
    expect(liveKindOf('cam:')).toBe('cam')
    expect(liveKindOf('url:https://fake-real.live')).toBeNull()
    expect(liveKindOf(null)).toBeNull()
  })
})
