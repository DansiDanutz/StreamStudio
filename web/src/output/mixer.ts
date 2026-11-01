/** S5 audio mixer: per-source gain and mute, level meters, and music ducking under the voice.
 *  The math is pure (tested); `AudioMixer` wires it to WebAudio. */

export type SourceKind = 'mic' | 'tab' | 'file' | 'music'

export interface Channel { id: string; kind: SourceKind; gainDb: number; muted: boolean }

export const dbToGain = (db: number) => (db <= -60 ? 0 : 10 ** (db / 20))
export const gainToDb = (g: number) => (g <= 0 ? -Infinity : 20 * Math.log10(g))

/** RMS level of a float sample block, in dBFS (−Infinity for silence). */
export function rmsDb(samples: ArrayLike<number>): number {
  let sum = 0
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i]
  return samples.length ? gainToDb(Math.sqrt(sum / samples.length)) : -Infinity
}

export interface Duck { thresholdDb: number; reductionDb: number; attackMs: number; releaseMs: number }
export const DEFAULT_DUCK: Duck = { thresholdDb: -45, reductionDb: -12, attackMs: 80, releaseMs: 600 }

/** Music reduction (dB, ≤ 0) after `dtMs` more time, easing toward the target the voice level asks for. */
export function duckStep(current: number, voiceDb: number, dtMs: number, d: Duck = DEFAULT_DUCK): number {
  const target = voiceDb > d.thresholdDb ? d.reductionDb : 0
  const tau = target < current ? d.attackMs : d.releaseMs
  const k = 1 - Math.exp(-dtMs / tau)
  return current + (target - current) * k
}

/** Gain (linear) a channel plays at: muted → 0; music also takes the current duck reduction. */
export function effectiveGain(c: Channel, duckDb = 0): number {
  if (c.muted) return 0
  return dbToGain(c.gainDb + (c.kind === 'music' ? duckDb : 0))
}

/** Gain correction (dB) to move a measured loudness onto the target, limited so one step stays gentle. */
export function loudnessCorrection(measuredDb: number, targetDb = -16, maxStepDb = 6): number {
  if (!Number.isFinite(measuredDb)) return 0
  return Math.max(-maxStepDb, Math.min(maxStepDb, targetDb - measuredDb))
}

interface Node { gain: GainNode; analyser: AnalyserNode; src: AudioNode }

export class AudioMixer {
  readonly ctx: AudioContext
  private dest: MediaStreamAudioDestinationNode
  private nodes = new Map<string, Node>()
  private channels = new Map<string, Channel>()
  private duckDb = 0
  private timer: ReturnType<typeof setInterval> | null = null
  duck: Duck = DEFAULT_DUCK

  constructor(ctx: AudioContext = new AudioContext()) {
    this.ctx = ctx
    this.dest = ctx.createMediaStreamDestination()
  }

  /** The mixed audio, ready to join the recorder's stream in place of the raw tab audio. */
  get output(): MediaStream { return this.dest.stream }

  add(ch: Channel, source: MediaStream | HTMLMediaElement): void {
    const src = source instanceof MediaStream ? this.ctx.createMediaStreamSource(source) : this.ctx.createMediaElementSource(source)
    const gain = this.ctx.createGain()
    const analyser = this.ctx.createAnalyser()
    analyser.fftSize = 1024
    src.connect(gain)
    gain.connect(analyser)
    gain.connect(this.dest)
    this.nodes.set(ch.id, { gain, analyser, src })
    this.channels.set(ch.id, ch)
    this.apply(ch.id)
    if (!this.timer) this.timer = setInterval(() => this.tick(50), 50)
  }

  set(id: string, patch: Partial<Pick<Channel, 'gainDb' | 'muted'>>): void {
    const c = this.channels.get(id)
    if (!c) return
    this.channels.set(id, { ...c, ...patch })
    this.apply(id)
  }

  level(id: string): number {
    const n = this.nodes.get(id)
    if (!n) return -Infinity
    const buf = new Float32Array(n.analyser.fftSize)
    n.analyser.getFloatTimeDomainData(buf)
    return rmsDb(buf)
  }

  private apply(id: string) {
    const c = this.channels.get(id)
    const n = this.nodes.get(id)
    if (c && n) n.gain.gain.setTargetAtTime(effectiveGain(c, this.duckDb), this.ctx.currentTime, 0.02)
  }

  private tick(dtMs: number) {
    const voice = Math.max(-Infinity, ...[...this.channels.values()].filter((c) => c.kind === 'mic' && !c.muted).map((c) => this.level(c.id)))
    this.duckDb = duckStep(this.duckDb, voice, dtMs, this.duck)
    for (const [id, c] of this.channels) if (c.kind === 'music') this.apply(id)
  }

  close(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    void this.ctx.close()
  }
}
