/** The script as a timeline: when each segment starts and ends, what is on screen, what is heard,
 *  and what will actually play after the rules (lip-sync guard, available gesture clips). Pure:
 *  the Timeline view, the agents (timeline.get) and the tests all read the same compiled result. */

import { gesture as findGesture, hasClip, nearestMade, type GestureId } from '../avatar/gestures'
import { hotspot } from '../stage/hotspots'
import type { Scene } from '../stage/types'
import { guardCue, lipsMatch, parseMediaEvents, type Cue, type Script, type Segment } from './types'

export interface TimelineItem {
  index: number
  id: string
  startMs: number
  /** Gesture lead-in: the voice starts this long after the segment starts. */
  leadMs: number
  voiceMs: number
  endMs: number
  text: string
  scene: { id: string; name: string } | null
  /** Scene in effect (this segment's, or carried over from an earlier one). */
  sceneInEffect: { id: string; name: string } | null
  cue: Cue
  /** What really plays after the lip-sync guard. */
  plays: Cue
  lips: boolean
  voice: 'clip' | 'narration' | 'none'
  clip?: string
  gesture: { asked: string; plays: GestureId | null; clip: boolean } | null
  target?: string
  via?: string
  visual?: string
  table?: string
  media?: string
  zoom?: Segment['zoom']
  warnings: string[]
}

export interface Timeline { totalMs: number; items: TimelineItem[]; warnings: number }

/** Clip lengths learned from the media (ms), filled in by the Timeline view. */
export const clipDurations = new Map<string, number>()

export function compileTimeline(script: Script, scenes: Pick<Scene, 'id' | 'name'>[], startScene?: string, cards?: { id: string; label: string }[]): Timeline {
  let t = 0
  let inEffect = scenes.find((s) => s.id === startScene) ?? null
  const items = script.segments.map((s, index): TimelineItem => {
    const warnings: string[] = []
    const lips = lipsMatch(s)
    const plays = guardCue(s.cue, s)
    if (plays !== s.cue) warnings.push(`${s.cue} plays as ${plays}: no lip-synced clip for this line (render it in Script → HeyGen).`)
    if (s.voice === 'narration' && !s.audio) warnings.push('Narration voice but no audio attached: the segment runs silent on its timer.')
    let scene: TimelineItem['scene'] = null
    if (s.scene) {
      const sc = scenes.find((x) => x.id === s.scene)
      if (sc) { scene = { id: sc.id, name: sc.name }; inEffect = scene } else warnings.push(`Scene "${s.scene}" is not in the library.`)
    }
    let g: TimelineItem['gesture'] = null
    let leadMs = 0
    if (s.gesture) {
      const asked = s.gesture
      const ideal = asked === 'auto' ? null : (asked as GestureId)
      const playsG = ideal ? nearestMade(ideal) ?? ideal : null
      const def = findGesture(playsG ?? 'point-right')
      leadMs = def?.ms ?? 2200
      g = { asked, plays: playsG, clip: playsG ? hasClip(playsG) : true }
      if (asked !== 'auto' && !findGesture(asked)) warnings.push(`Unknown gesture "${asked}".`)
      else if (playsG && !hasClip(playsG)) warnings.push(`No clip for ${playsG} yet: a pointer cue stands in.`)
      else if (ideal && playsG !== ideal) warnings.push(`${ideal} has no clip: plays ${playsG}.`)
    }
    if (s.via && !hotspot(s.via)) warnings.push(`Unknown hotspot "${s.via}".`)
    if (s.target?.startsWith('hotspot:') && !hotspot(s.target.slice(8))) warnings.push(`Unknown target "${s.target}".`)
    if (s.media) {
      try {
        for (const ev of parseMediaEvents(s.media)) {
          if (cards && !cards.some((c) => c.id === ev.card || c.label.toLowerCase() === ev.card.toLowerCase())) warnings.push(`No media card "${ev.card}" on the stage (add it from the Library).`)
        }
      } catch (e) { warnings.push((e as Error).message) }
    }
    const known = s.clip && lips ? clipDurations.get(s.clip) : undefined
    const voiceMs = known ?? s.durationMs
    const item: TimelineItem = {
      index, id: s.id, startMs: t, leadMs, voiceMs, endMs: t + leadMs + voiceMs, text: s.text,
      scene, sceneInEffect: inEffect, cue: s.cue, plays, lips,
      voice: lips ? 'clip' : s.voice === 'narration' ? 'narration' : 'none', clip: s.clip,
      gesture: g, target: s.target, via: s.via, visual: s.visual, table: s.table, media: s.media, zoom: s.zoom, warnings,
    }
    t = item.endMs
    return item
  })
  return { totalMs: t, items, warnings: items.reduce((n, i) => n + i.warnings.length, 0) }
}

/** Index of the segment on air at a time (ms), for scrubbing. */
export const itemAt = (tl: Timeline, ms: number) => Math.max(0, tl.items.findIndex((i) => ms < i.endMs) === -1 ? tl.items.length - 1 : tl.items.findIndex((i) => ms < i.endMs))
