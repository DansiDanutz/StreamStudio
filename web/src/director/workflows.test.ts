import { describe, expect, it } from 'vitest'
import { GESTURES, SEATED, gesture, gestureClip, pickGesture } from '../avatar/gestures'
import { HOTSPOTS, hotspot } from '../stage/hotspots'
import { PRESETS } from '../stage/presets'
import { WORKFLOWS, workflowDefaults } from './workflows'
import { guardCue } from './types'

const seat = SEATED.landscape

describe('gestures', () => {
  it('has at least 10, including the four diagonal points, mirrored on the left', () => {
    expect(GESTURES.length).toBeGreaterThanOrEqual(10)
    for (const id of ['point-up-right', 'point-down-right', 'point-up-left', 'point-down-left']) expect(gesture(id)).toBeTruthy()
    expect(gestureClip(gesture('point-up-left')!)).toBe('/avatar/gestures/point-up-right.cutout.webm')
    for (const g of GESTURES) if (g.mirrorOf) expect(gesture(g.mirrorOf)?.mirrorOf).toBeUndefined()
  })
  it('aims at targets around the seated presenter', () => {
    expect(pickGesture(seat, hotspot('monitor')!.rect)).toBe('point-up-right')
    expect(pickGesture(seat, { x: 0.02, y: 0.05, w: 0.2, h: 0.2 })).toBe('point-up-left')
    expect(pickGesture(seat, { x: 0.8, y: 0.8, w: 0.15, h: 0.15 })).toBe('point-down-right')
    expect(pickGesture(seat, { x: 0.02, y: 0.82, w: 0.15, h: 0.15 })).toBe('point-down-left')
    expect(pickGesture(seat, { x: 0.85, y: 0.45, w: 0.1, h: 0.1 })).toBe('point-right')
    expect(pickGesture(seat, { x: 0.85, y: 0.45, w: 0.1, h: 0.1 }, true)).toBe('present-right')
  })
  it('hotspots sit inside the frame', () => {
    for (const h of HOTSPOTS) {
      expect(h.rect.x).toBeGreaterThanOrEqual(0)
      expect(h.rect.x + h.rect.w).toBeLessThanOrEqual(1.0001)
      expect(h.rect.y + h.rect.h).toBeLessThanOrEqual(1)
    }
  })
})

describe('workflows', () => {
  const sceneIds = new Set(PRESETS.map((p) => p.id))
  for (const w of WORKFLOWS) {
    it(`${w.id} builds a playable script from its defaults`, () => {
      const segs = w.build(workflowDefaults(w))
      expect(segs.length).toBeGreaterThan(0)
      for (const id of w.scenes) expect(sceneIds.has(id)).toBe(true)
      for (const s of segs) {
        expect(s.text.length).toBeGreaterThan(0)
        if (s.scene) expect(w.scenes).toContain(s.scene)
        if (s.gesture && s.gesture !== 'auto') expect(gesture(s.gesture)).toBeTruthy()
        if (s.via) expect(hotspot(s.via)).toBeTruthy()
        if (s.target?.startsWith('hotspot:')) expect(hotspot(s.target.slice(8))).toBeTruthy()
      }
    })
  }
  it('browser demo opens out of the monitor and closes back into it', () => {
    const w = WORKFLOWS.find((x) => x.id === 'browser')!
    const segs = w.build(workflowDefaults(w))
    expect(segs[0]).toMatchObject({ cue: 'avatar', gesture: 'auto', target: 'hotspot:monitor' })
    expect(segs[1]).toMatchObject({ cue: 'content', via: 'monitor', visual: 'url:https://fake-real.live' })
    expect(segs.at(-1)).toMatchObject({ cue: 'avatar', via: 'monitor' })
    // no lip-synced clips yet: the face stays small while the browser is up
    expect(guardCue(segs[1].cue, segs[1])).toBe('content')
    expect(guardCue(segs[0].cue, segs[0])).toBe('pip')
  })
})
