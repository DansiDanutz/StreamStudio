import { describe, expect, it } from 'vitest'
import { autoDirect, propose, splitScript } from './autoDirect'
import { layoutForCue } from './cueLayouts'
import { PRESETS } from '../stage/presets'
import { estimateMs, newSegment } from './types'

describe('auto-direct rules', () => {
  it('opens and closes on the presenter', () => {
    expect(propose("Welcome to Dan's Lab. I'm Dan.", 0, 5).cue).toBe('avatar')
    expect(propose('If this is useful, subscribe.', 4, 5).cue).toBe('avatar')
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
  it('never mutates the saved layout', () => {
    const before = JSON.stringify(saved)
    layoutForCue('avatar', saved, 'portrait')
    expect(JSON.stringify(saved)).toBe(before)
  })
})
