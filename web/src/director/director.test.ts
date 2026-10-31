import { describe, expect, it } from 'vitest'
import { autoDirect, propose, splitScript } from './autoDirect'
import { guardLayout, layoutForCue, pipRect } from './cueLayouts'
import { PRESETS } from '../stage/presets'
import { MAX_UNSYNCED_AREA, estimateMs, guardCue, lipsMatch, newSegment } from './types'

describe('auto-direct rules', () => {
  it('opens and closes on the presenter, full frame', () => {
    expect(propose("Welcome to Dan's Lab. I'm Dan.", 0, 5).cue).toBe('avatar')
    expect(propose('If this is useful, subscribe.', 4, 5).cue).toBe('avatar')
  })
  it('presenter segments that mention the screen keep a small content window (duo)', () => {
    expect(propose('Welcome back. Today we look at the new dashboard.', 0, 5).cue).toBe('duo')
  })
  it('points at the screen → content', () => {
    expect(propose('Look at the dashboard on the screen: this is the merchant view.', 1, 5).cue).toBe('content')
  })
  it('fine detail → content with a zoom at the hinted corner', () => {
    const p = propose('Notice this button in the top right.', 2, 5)
    expect(p.cue).toBe('content')
    expect(p.zoom).toEqual({ x: 0.8, y: 0.2, scale: 1.7 })
  })
  it('reveal → full', () => {
    expect(propose("Here's the result: the full flow, end to end.", 3, 5).cue).toBe('full')
  })
  it('Romanian cues work too', () => {
    expect(propose('Uitați-vă pe ecran la dashboard.', 1, 4).cue).toBe('content')
    expect(propose('Bună ziua, eu sunt Dan.', 1, 4).cue).toBe('avatar')
  })
  it('keeps pinned segments', () => {
    const s = newSegment('Look at the screen.', 'avatar')
    s.pinned = true
    const out = autoDirect({ id: 'x', title: 't', segments: [s] })
    expect(out.segments[0].cue).toBe('avatar')
  })
})

describe('script splitting and timing', () => {
  it('splits paragraphs, and long paragraphs into sentence pairs', () => {
    const parts = splitScript('One. Two.\n\nA. B. C. D. E.')
    expect(parts).toEqual(['One. Two.', 'A. B.', 'C. D.', 'E.'])
  })
  it('estimates ~150 wpm with a floor', () => {
    expect(estimateMs('hi')).toBe(1500)
    expect(estimateMs(Array(150).fill('word').join(' '))).toBe(60_400)
  })
})

describe('cue layouts', () => {
  const saved = PRESETS[0].layouts.landscape
  it('split is the saved layout', () => {
    expect(layoutForCue('split', saved, 'landscape')).toEqual(saved)
  })
  it('content maximizes main and shrinks avatar; full hides avatar', () => {
    const c = layoutForCue('content', saved, 'landscape')
    expect(c.main.w).toBeGreaterThan(0.9)
    expect(c.avatar.w).toBeLessThan(0.2)
    const f = layoutForCue('full', saved, 'landscape')
    expect(f.main).toMatchObject({ x: 0, y: 0, w: 1, h: 1 })
    expect(f.avatar.visible).toBe(false)
  })
  it('avatar is full frame with no content; duo keeps a small content window', () => {
    const a = layoutForCue('avatar', saved, 'landscape')
    expect(a.avatar).toMatchObject({ x: 0, y: 0, w: 1, h: 1, radius: 0 })
    expect(a.main.visible).toBe(false)
    const d = layoutForCue('duo', saved, 'landscape')
    expect(d.main.visible).toBe(true)
    expect(d.main.w).toBeLessThan(0.5)
  })
  it('never mutates the saved layout', () => {
    const before = JSON.stringify(saved)
    layoutForCue('avatar', saved, 'portrait')
    expect(JSON.stringify(saved)).toBe(before)
  })
})

describe('lip-sync guard', () => {
  const saved = PRESETS[0].layouts.landscape
  const synced = { clip: '/avatar/x.mp4' }
  const dubbed = { clip: '/avatar/x.mp4', voice: 'narration' as const }
  it('lips match only when the voice is the clip\'s own audio', () => {
    expect(lipsMatch(synced)).toBe(true)
    expect(lipsMatch({ ...synced, voice: 'clip' })).toBe(true)
    expect(lipsMatch(dubbed)).toBe(false)
    expect(lipsMatch({})).toBe(false)
  })
  it('full-frame and large-face cues degrade when the lips do not match', () => {
    expect(guardCue('avatar', synced)).toBe('avatar')
    expect(guardCue('duo', synced)).toBe('duo')
    expect(guardCue('avatar', dubbed)).toBe('pip')
    expect(guardCue('duo', dubbed)).toBe('content')
    expect(guardCue('avatar', {})).toBe('pip')
    expect(guardCue('full', dubbed)).toBe('full')
  })
  it('pip keeps the face small, bottom-left, with no content', () => {
    for (const o of ['landscape', 'portrait'] as const) {
      const L = layoutForCue('pip', PRESETS[0].layouts[o], o)
      expect(L.main.visible).toBe(false)
      expect(L.avatar.w * L.avatar.h).toBeLessThanOrEqual(MAX_UNSYNCED_AREA)
      expect(L.avatar.x + L.avatar.w).toBeLessThan(0.5)
      expect(L.avatar.y + L.avatar.h).toBeLessThan(1)
    }
  })
  it('circle is square in pixels; portrait is 3:4', () => {
    const c = pipRect('landscape', 'circle')
    expect((c.w * 1920) / (c.h * 1080)).toBeCloseTo(1, 5)
    const p = pipRect('landscape', 'portrait')
    expect((p.w * 1920) / (p.h * 1080)).toBeCloseTo(3 / 4, 5)
  })
  it('guardLayout shrinks any large face (e.g. a big avatar in the saved split) and leaves small ones', () => {
    const big = { ...saved, avatar: { ...saved.avatar, visible: true, x: 0.1, y: 0.1, w: 0.5, h: 0.8 } }
    const g = guardLayout(big, 'landscape')
    expect(g.avatar.w * g.avatar.h).toBeLessThanOrEqual(MAX_UNSYNCED_AREA)
    expect(g.main).toEqual(big.main)
    const small = layoutForCue('content', saved, 'landscape')
    expect(guardLayout(small, 'landscape')).toEqual(small)
    for (const cue of ['avatar', 'duo', 'split', 'content', 'full', 'pip'] as const) {
      const L = guardLayout(layoutForCue(guardCue(cue, dubbed), saved, 'landscape'), 'landscape')
      if (L.avatar.visible) expect(L.avatar.w * L.avatar.h).toBeLessThanOrEqual(MAX_UNSYNCED_AREA)
    }
  })
})
