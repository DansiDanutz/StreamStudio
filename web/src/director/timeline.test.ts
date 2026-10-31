import { beforeEach, describe, expect, it } from 'vitest'
import { compileTimeline, itemAt } from './timeline'
import { newSegment, type Script } from './types'
import { setMadeGestures } from '../avatar/gestures'
import { EXECUTORS } from '../agent/bridge'
import { useDirector } from './store'
import { useStage } from '../stage/store'
import { PRESETS, clone } from '../stage/presets'

const scenes = PRESETS.map((p) => ({ id: p.id, name: p.name }))
const seg = (text: string, cue: Parameters<typeof newSegment>[1], extra = {}) => ({ ...newSegment(text, cue), ...extra })

describe('timeline', () => {
  it('lays segments end to end, gesture lead first, and shows what really plays', () => {
    setMadeGestures(['point-up-right', 'point-right', 'present-right', 'welcome', 'thumbs-up', 'wave', 'think'])
    const script: Script = { id: 's', title: 't', segments: [
      seg('Let me show you Fake-Real.', 'avatar', { scene: 'studio-solo', gesture: 'auto', target: 'hotspot:monitor' }),
      seg('Paste a link.', 'content', { via: 'monitor', visual: 'url:https://fake-real.live' }),
      seg('Back to me.', 'avatar', { clip: '/avatar/clips/x.mp4', gesture: 'point-down-right' }),
    ] }
    const tl = compileTimeline(script, scenes, 'world-of-ai')
    const [a, b, c] = tl.items
    expect(a.startMs).toBe(0)
    expect(a.leadMs).toBeGreaterThan(0)
    expect(b.startMs).toBe(a.endMs)
    expect(tl.totalMs).toBe(c.endMs)
    expect(a.plays).toBe('pip') // no lip-synced clip: guarded
    expect(a.warnings.join()).toMatch(/plays as pip/)
    expect(c.plays).toBe('avatar') // has its own clip
    expect(c.gesture?.plays).toBe('point-right') // no down-right clip: closest made one
    expect(b.sceneInEffect?.id).toBe('studio-solo') // carries over
    expect(itemAt(tl, b.startMs + 10)).toBe(1)
    setMadeGestures(null)
  })
  it('flags things that will not work', () => {
    const tl = compileTimeline({ id: 's', title: 't', segments: [seg('x', 'split', { scene: 'nope', via: 'moon', voice: 'narration' })] }, scenes)
    expect(tl.warnings).toBe(3)
  })
})

describe('agents edit the script', () => {
  beforeEach(() => {
    useStage.setState({ scenes: clone(PRESETS), activeId: 'studio-desk' })
    useDirector.getState().insertSegments([seg('One.', 'avatar'), seg('Two.', 'split')], 'replace', 'Test')
  })
  it('read, update, add, remove, set, preview', () => {
    const tl = EXECUTORS['timeline.get']({}) as { items: { plays: string }[] }
    expect(tl.items).toHaveLength(2)
    EXECUTORS['segment.update']({ index: 1, patch: { cue: 'content', visual: 'https://fake-real.live', bogus: 1 } })
    const s1 = useDirector.getState().script.segments[1]
    expect(s1.cue).toBe('content')
    expect(s1.visual).toBe('url:https://fake-real.live')
    expect('bogus' in s1).toBe(false)
    EXECUTORS['segment.add']({ after: 0, segment: { text: 'In between.', cue: 'duo' } })
    expect(useDirector.getState().script.segments.map((s) => s.text)).toEqual(['One.', 'In between.', 'Two.'])
    EXECUTORS['segment.remove']({ index: 0 })
    expect(useDirector.getState().script.segments).toHaveLength(2)
    EXECUTORS['script.set']({ title: 'New', segments: [{ text: 'Only.', cue: 'pip' }] })
    expect(useDirector.getState().script.title).toBe('New')
    EXECUTORS['segment.preview']({ index: 0 })
    expect(useDirector.getState().current).toBe(0)
    expect(() => EXECUTORS['segment.update']({ index: 9, patch: {} })).toThrow(/no segment/)
    expect(() => EXECUTORS['segment.update']({ index: 0, patch: { cue: 'fly' } })).toThrow(/cue/)
  })
})

describe('script-driven media cards', () => {
  beforeEach(() => {
    useStage.setState({ scenes: clone(PRESETS), activeId: 'studio-solo', orientation: 'landscape' })
    useDirector.getState().stop()
  })
  it('parses events and rejects bad ones clearly', async () => {
    const { parseMediaEvents } = await import('./types')
    expect(parseMediaEvents('show:Codex; move:Kimi@0.8,0.3,0.25; focus:GLM')).toEqual([
      { op: 'show', card: 'Codex' }, { op: 'move', card: 'Kimi', x: 0.8, y: 0.3, w: 0.25 }, { op: 'focus', card: 'GLM' },
    ])
    expect(() => parseMediaEvents('jump:Codex')).toThrow(/bad media event/)
    expect(() => parseMediaEvents('move:Codex')).toThrow(/needs a position/)
  })
  it('moves a card live (not saved), Dan points where it went, stop resets', () => {
    const { media } = EXECUTORS['media.add']({ item: 'codex', x: 0.5, y: 0.5, w: 0.2 }) as { media: string }
    const saved = { ...useStage.getState().media()[0].layout }
    EXECUTORS['media.event']({ event: 'move:Codex@0.85,0.2,0.2' })
    const live = useDirector.getState().mediaLive[media]
    expect(live.x! + live.w! / 2).toBeCloseTo(0.85, 5)
    expect(useStage.getState().media()[0].layout).toEqual(saved) // the scene is untouched
    expect(useDirector.getState().targetRect(`media:${media}`)!.x).toBeCloseTo(live.x!, 5)
    expect((EXECUTORS['point.at']({ target: `media:${media}` }) as { gesture: string }).gesture).toMatch(/up-right|right/)
    useDirector.getState().stop()
    expect(useDirector.getState().mediaLive).toEqual({})
  })
  it('the timeline warns about cards that are not on the stage', () => {
    const tl = compileTimeline({ id: 's', title: 't', segments: [seg('x', 'split', { media: 'show:Nope' })] }, scenes, undefined, [{ id: 'm1', label: 'Codex' }])
    expect(tl.items[0].warnings.join()).toMatch(/No media card "Nope"/)
  })
})
