import { beforeEach, describe, expect, it } from 'vitest'
import { ACTIONS, buildCatalog } from './catalog'
import { EXECUTORS, snapshot } from './bridge'
import { useStage } from '../stage/store'
import { useDirector } from '../director/store'
import { PRESETS, clone } from '../stage/presets'

describe('artifact library', () => {
  const { artifacts } = buildCatalog()
  it('covers every kind the studio has', () => {
    const kinds = new Set(artifacts.map((a) => a.kind))
    for (const k of ['gesture', 'target', 'hotspot', 'object', 'workflow', 'cue', 'template']) expect(kinds).toContain(k)
    expect(artifacts.filter((a) => a.kind === 'gesture').length).toBeGreaterThanOrEqual(12)
  })
  it('ids are unique and every action an artifact names can actually run', () => {
    expect(new Set(artifacts.map((a) => a.id)).size).toBe(artifacts.length)
    for (const a of artifacts) for (const x of a.actions) expect(EXECUTORS[x.action], `${a.id} → ${x.action}`).toBeTypeOf('function')
    for (const s of ACTIONS) expect(EXECUTORS[s.action]).toBeTypeOf('function')
  })
})

describe('agent actions run on the stage', () => {
  beforeEach(() => {
    useStage.setState({ scenes: clone(PRESETS), activeId: 'studio-desk', orientation: 'landscape' })
    useDirector.getState().stop()
  })
  it('scene, cue (guarded), table, media, main source, workflow', () => {
    EXECUTORS['scene.activate']({ id: 'scene:studio-solo' })
    expect(useStage.getState().activeId).toBe('studio-solo')
    EXECUTORS['cue.apply']({ cue: 'avatar' })
    expect(useDirector.getState().cue).toBe('avatar')
    EXECUTORS['table.event']({ event: 'arrive:codex' })
    expect(Object.keys(useDirector.getState().table)).toContain('codex')
    const { media } = EXECUTORS['media.add']({ item: 'object:claude-code', x: 0.8, y: 0.3 }) as { media: string }
    expect(useStage.getState().media().some((m) => m.id === media)).toBe(true)
    EXECUTORS['main.source']({ src: 'fake-real.live' })
    expect(useStage.getState().mainSrc).toBe('url:https://fake-real.live')
    const r = EXECUTORS['workflow.insert']({ id: 'workflow:browser', fields: { url: 'https://example.com' } }) as { segments: number }
    expect(r.segments).toBeGreaterThan(2)
    expect(useDirector.getState().script.segments[1].visual).toBe('url:https://example.com')
    expect(snapshot().scene.id).toBe('studio-solo')
  })
  it('points at a media card from where Dan sits', () => {
    const { media } = EXECUTORS['media.add']({ item: 'codex', x: 0.85, y: 0.2 }) as { media: string }
    const out = EXECUTORS['point.at']({ target: `media:${media}` }) as { gesture: string }
    expect(out.gesture).toMatch(/right/)
  })
  it('rejects bad input with a clear message', () => {
    expect(() => EXECUTORS['scene.activate']({ id: 'nope' })).toThrow(/no scene/)
    expect(() => EXECUTORS['cue.apply']({ cue: 'fly' })).toThrow(/one of/)
    expect(() => EXECUTORS['media.add']({})).toThrow(/item/)
  })
})
