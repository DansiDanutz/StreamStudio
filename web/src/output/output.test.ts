import { describe, expect, it } from 'vitest'
import { pickMime } from './recorder'
import { liveKindOf } from '../stage/media'

describe('recording output', () => {
  it('prefers MP4 (H.264 + AAC), falls back to WebM', () => {
    expect(pickMime(() => true)).toMatch(/^video\/mp4/)
    expect(pickMime((t) => t.startsWith('video/webm'))).toBe('video/webm;codecs=vp9,opus')
    expect(pickMime(() => false)).toBe('')
  })
  it('knows which Main-card sources are live streams', () => {
    expect(liveKindOf('tab:')).toBe('tab')
    expect(liveKindOf('cam:')).toBe('cam')
    expect(liveKindOf('url:https://fake-real.live')).toBeNull()
    expect(liveKindOf(null)).toBeNull()
  })
})
