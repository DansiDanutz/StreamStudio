/** The artifact library as agents see it: every gesture, object, workflow, hotspot, cue and
 *  template the editor owns, each with the actions that use it. Scenes, rendered clips and
 *  recordings are added by the server. Published to /api/library/web on load. */

import { GESTURES, hasClip, motionFor } from '../avatar/gestures'
import { WORKFLOWS, workflowDefaults } from '../director/workflows'
import { OBJECTS, objectStill } from '../overlays/objects'
import { HOTSPOTS } from '../stage/hotspots'
import { PRESETS } from '../stage/presets'
import { LIBRARY } from '../stage/Library'
import type { Cue } from '../director/types'

export interface Artifact {
  id: string
  kind: string
  name: string
  description: string
  preview?: string
  actions: { action: string; args: Record<string, unknown> }[]
  [k: string]: unknown
}

export interface ActionSpec { action: string; description: string; args: Record<string, string> }

/** Every action the editor runs for an agent (see bridge.ts), with its arguments. */
export const ACTIONS: ActionSpec[] = [
  { action: 'scene.activate', description: 'Switch the stage to a scene.', args: { id: 'scene id' } },
  { action: 'scene.new', description: 'Make a new scene from a template.', args: { template: 'template id', collection: 'Openers|Talk|Demo|Data|Social (optional)' } },
  { action: 'cue.apply', description: 'Move the cards to a layout. The lip-sync guard always applies.', args: { cue: 'avatar|duo|split|content|full|pip', zoom: '{x,y,scale} (optional)' } },
  { action: 'point.at', description: 'Dan points at a card or place; the movement is chosen from where he sits.', args: { target: "'main' | 'menu' | 'media:<id>' | 'hotspot:<id>'" } },
  { action: 'gesture.play', description: 'Play one gesture.', args: { id: 'gesture id' } },
  { action: 'table.event', description: 'Objects on the studio table.', args: { event: "'arrive:<id>' | 'leave:<id>' | 'react:all' | 'clear' (chain with ;)" } },
  { action: 'media.add', description: 'Add a media card (from the library or any URL). Returns its id.', args: { item: 'library item id (or src)', src: 'video/image URL (optional)', x: '0..1', y: '0..1', w: '0..1 width' } },
  { action: 'media.remove', description: 'Remove a media card.', args: { id: 'media card id' } },
  { action: 'main.source', description: 'What the Main card shows.', args: { src: "web page URL, '/path/file.mp4', or null to clear" } },
  { action: 'workflow.insert', description: 'Fill a workflow and put its segments in the script.', args: { id: 'workflow id', fields: '{key: value} (optional)', mode: "'replace' | 'append'" } },
  { action: 'timeline.get', description: 'The script as a timeline: start/end of every segment, what really plays (after the lip-sync guard and available gesture clips) and warnings.', args: {} },
  { action: 'segment.preview', description: 'Show one segment on stage without playing (scene, layout, table, Main card).', args: { index: 'segment index' } },
  { action: 'segment.update', description: 'Change one segment. Only the fields you pass change.', args: { index: 'segment index (or id)', patch: '{text, cue, scene, gesture, target, via, visual, table, zoom, voice, clip}' } },
  { action: 'segment.add', description: 'Add a segment (at the end, or after an index).', args: { after: 'index (optional)', segment: '{text, cue, ...same fields as patch}' } },
  { action: 'segment.remove', description: 'Remove a segment.', args: { index: 'segment index (or id)' } },
  { action: 'script.set', description: 'Replace the whole script.', args: { title: 'optional', segments: '[{text, cue, ...}]' } },
  { action: 'script.play', description: 'Play the script (from a segment index).', args: { from: 'index (optional)' } },
  { action: 'script.stop', description: 'Stop playback and reset the stage.', args: {} },
  { action: 'avatar.shape', description: "Dan's small card shape.", args: { shape: "'circle' | 'portrait'" } },
  { action: 'orientation.set', description: 'Output orientation.', args: { orientation: "'landscape' | 'portrait'" } },
]

const CUES: Record<Cue, string> = {
  avatar: 'Dan fills the frame, no cards (only with his own lip-synced voice; else the small card).',
  duo: 'Dan large, content small.',
  split: 'The scene as laid out.',
  content: 'Content maximized, Dan small.',
  full: 'Content fills the frame, Dan hidden.',
  pip: 'Dan in the small circle/portrait card over the studio.',
}

export function buildCatalog(): { artifacts: Artifact[]; actions: ActionSpec[] } {
  const a: Artifact[] = []
  for (const g of GESTURES) {
    a.push({
      id: `gesture:${g.id}`, kind: 'gesture', name: g.label,
      description: `${g.label}${g.mirrorOf ? ` (mirror of ${g.mirrorOf})` : ''}. ${g.aim ? 'Pointing.' : 'Beat.'} ${hasClip(g.id) ? 'Clip ready.' : 'No clip yet: a pointer cue stands in.'}`,
      motion_prompt: motionFor(g.id), clip_ready: hasClip(g.id),
      actions: [{ action: 'gesture.play', args: { id: g.id } }],
    })
  }
  a.push({ id: 'target:main', kind: 'target', name: 'Main card', description: 'The content card.', actions: [{ action: 'point.at', args: { target: 'main' } }] })
  a.push({ id: 'target:menu', kind: 'target', name: 'Menu card', description: 'The menu card (transparent in the output unless shown).', actions: [{ action: 'point.at', args: { target: 'menu' } }] })
  for (const h of HOTSPOTS) {
    a.push({
      id: `hotspot:${h.id}`, kind: 'hotspot', name: h.label, description: `A place in the studio plate at ${JSON.stringify(h.rect)}. The Main card can open out of it (segment.via).`,
      actions: [{ action: 'point.at', args: { target: `hotspot:${h.id}` } }],
    })
  }
  for (const o of OBJECTS) {
    a.push({
      id: `object:${o.id}`, kind: 'object', name: o.name, preview: objectStill(o),
      description: `3D ${o.name} that arrives on the studio table (or as a media card).`,
      actions: [
        { action: 'table.event', args: { event: `arrive:${o.id}` } },
        { action: 'table.event', args: { event: `leave:${o.id}` } },
        { action: 'media.add', args: { item: o.id } },
      ],
    })
  }
  for (const it of LIBRARY) if (!OBJECTS.some((o) => o.id === it.id)) a.push({ id: `media:${it.id}`, kind: 'media', name: it.label, description: 'A media card source.', preview: it.poster, actions: [{ action: 'media.add', args: { item: it.id } }] })
  for (const w of WORKFLOWS) {
    a.push({
      id: `workflow:${w.id}`, kind: 'workflow', name: w.name, description: w.summary,
      fields: w.fields.map((f) => ({ key: f.key, label: f.label, lines: !!f.lines, options: f.options?.map((o) => o.value) })),
      defaults: workflowDefaults(w),
      actions: [{ action: 'workflow.insert', args: { id: w.id, mode: 'replace' } }],
    })
  }
  for (const [cue, d] of Object.entries(CUES)) a.push({ id: `cue:${cue}`, kind: 'cue', name: cue, description: d, actions: [{ action: 'cue.apply', args: { cue } }] })
  for (const p of PRESETS) a.push({ id: `template:${p.id}`, kind: 'template', name: p.name, description: `Scene template (${p.collection}).`, actions: [{ action: 'scene.new', args: { template: p.id } }] })
  return { artifacts: a, actions: ACTIONS }
}
