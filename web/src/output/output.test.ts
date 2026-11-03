import { describe, expect, it, vi } from 'vitest'
import { pickMime, Recorder } from './recorder'
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
  it('knows which Main-card sources are live streams', () => {
    expect(liveKindOf('tab:')).toBe('tab')
    expect(liveKindOf('cam:')).toBe('cam')
    expect(liveKindOf('url:https://fake-real.live')).toBeNull()
    expect(liveKindOf(null)).toBeNull()
  })
})
