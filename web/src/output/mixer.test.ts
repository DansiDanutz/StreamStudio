import { describe, expect, it, vi } from 'vitest'
import { AudioMixer, DEFAULT_DUCK, dbToGain, duckStep, effectiveGain, gainToDb, loudnessCorrection, rmsDb } from './mixer'

describe('mixer math', () => {
  it('converts dB and gain', () => {
    expect(dbToGain(0)).toBe(1)
    expect(dbToGain(-6)).toBeCloseTo(0.501, 3)
    expect(dbToGain(-80)).toBe(0)
    expect(gainToDb(0.1)).toBeCloseTo(-20, 5)
  })

  it('measures RMS level', () => {
    expect(rmsDb([])).toBe(-Infinity)
    expect(rmsDb([0, 0, 0])).toBe(-Infinity)
    expect(rmsDb([1, -1, 1, -1])).toBeCloseTo(0, 5)
    expect(rmsDb([0.1, -0.1])).toBeCloseTo(-20, 5)
  })

  it('ducks music while the voice is loud and releases slower than it attacks', () => {
    let d = 0
    for (let i = 0; i < 20; i++) d = duckStep(d, -20, 50)
    expect(d).toBeCloseTo(DEFAULT_DUCK.reductionDb, 1)
    const afterOneStep = duckStep(d, -80, 50)
    expect(afterOneStep).toBeLessThan(0) // still ducked: release is slow
    let r = d
    for (let i = 0; i < 100; i++) r = duckStep(r, -80, 50)
    expect(r).toBeCloseTo(0, 1)
    expect(duckStep(0, -20, 50)).toBeLessThan(-3) // attack is fast
  })

  it('applies mute, gain and ducking only to music', () => {
    const mic = { id: 'm', kind: 'mic' as const, gainDb: 0, muted: false }
    const music = { id: 'x', kind: 'music' as const, gainDb: -10, muted: false }
    expect(effectiveGain(mic, -12)).toBe(1)
    expect(effectiveGain(music, -12)).toBeCloseTo(dbToGain(-22), 6)
    expect(effectiveGain({ ...mic, muted: true })).toBe(0)
  })

  it('corrects loudness toward the target in limited steps', () => {
    expect(loudnessCorrection(-22)).toBe(6)
    expect(loudnessCorrection(-18)).toBe(2)
    expect(loudnessCorrection(-5)).toBe(-6)
    expect(loudnessCorrection(-Infinity)).toBe(0)
  })
})

describe('AudioMixer channel replacement', () => {
  const node = () => ({ connect: () => {}, disconnect: vi.fn(), gain: { setTargetAtTime: () => {} }, fftSize: 0 })
  const fakeCtx = () => ({
    currentTime: 0,
    createMediaStreamDestination: () => ({ stream: {} }),
    createMediaStreamSource: node,
    createMediaElementSource: node,
    createGain: node,
    createAnalyser: node,
    close: () => Promise.resolve(),
  }) as unknown as AudioContext

  it('disconnects the old nodes when a channel id is added again', () => {
    const made: ReturnType<typeof node>[] = []
    const ctx = fakeCtx()
    ctx.createMediaStreamSource = (() => { const n = node(); made.push(n); return n }) as never
    const m = new AudioMixer(ctx)
    vi.stubGlobal('MediaStream', class {})
    const stream = new (globalThis.MediaStream as unknown as new () => MediaStream)()
    m.add({ id: 'mic', kind: 'mic', gainDb: 0, muted: false }, stream)
    m.add({ id: 'mic', kind: 'mic', gainDb: 0, muted: false }, stream)
    expect(made[0].disconnect).toHaveBeenCalled()
    expect(made[1].disconnect).not.toHaveBeenCalled()
    m.close()
    vi.unstubAllGlobals()
  })
})
