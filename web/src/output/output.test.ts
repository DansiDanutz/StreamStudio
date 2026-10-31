import { describe, expect, it } from 'vitest'
import { pickMime } from './recorder'
import { liveKindOf } from '../stage/media'

describe('recording output', () => {
  it('streams WebM when a server takes the chunks; MP4 only for a download-only take', () => {
    expect(pickMime(() => true)).toBe('video/webm;codecs=vp9,opus')
    expect(pickMime(() => true, false)).toMatch(/^video\/mp4/)
    expect(pickMime((t) => t.startsWith('video/webm'), false)).toBe('video/webm;codecs=vp9,opus')
    expect(pickMime(() => false)).toBe('')
  })
  it('knows which Main-card sources are live streams', () => {
    expect(liveKindOf('tab:')).toBe('tab')
    expect(liveKindOf('cam:')).toBe('cam')
    expect(liveKindOf('url:https://fake-real.live')).toBeNull()
    expect(liveKindOf(null)).toBeNull()
  })
})
