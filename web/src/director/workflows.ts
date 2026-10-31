/** Workflows: ready-made script shapes. Pick one, fill a few fields, and the Director gets segments
 *  with scenes, cues, gestures, targets and transitions already set. Everything stays editable. */

import { OBJECTS } from '../overlays/objects'
import { newSegment, type Cue, type Segment } from './types'

export interface WorkflowField {
  key: string
  label: string
  placeholder?: string
  default?: string
  /** One item per line. */
  lines?: boolean
  options?: { value: string; label: string }[]
}

export interface Workflow {
  id: string
  name: string
  /** One line: what the viewer sees. */
  summary: string
  fields: WorkflowField[]
  /** Template scenes the workflow uses (created in the library if missing). */
  scenes: string[]
  build: (f: Record<string, string>) => Segment[]
}

const seg = (text: string, cue: Cue, extra: Partial<Segment> = {}): Segment => ({ ...newSegment(text, cue), pinned: true, ...extra })
const lines = (v = '') => v.split('\n').map((x) => x.trim()).filter(Boolean)
const HOTSPOT_OPTIONS = [
  { value: 'monitor', label: 'Fake-Real monitor' },
  { value: 'trading', label: 'Trading screen' },
]

export const WORKFLOWS: Workflow[] = [
  {
    id: 'opener',
    name: 'Opener: the world of AI',
    summary: 'You at the desk; the AI tools arrive on the table one by one.',
    scenes: ['world-of-ai'],
    fields: [
      { key: 'hello', label: 'First line', default: 'Let me introduce you to the world of AI. The technology of the future, on this table, today.' },
      { key: 'tools', label: 'Tools (one per line: id · line)', lines: true,
        default: OBJECTS.filter((o) => o.id !== 'openclaw').map((o) => `${o.id} · ${o.name}.`).join('\n') },
      { key: 'close', label: 'Closing line', default: "Six minds, one table. I'm the conductor. Let's make something." },
    ],
    build: (f) => [
      seg(f.hello, 'avatar', { scene: 'world-of-ai', table: 'clear', gesture: 'welcome' }),
      ...lines(f.tools).map((l) => {
        const [id, ...rest] = l.split('·')
        const tool = id.trim()
        return seg(rest.join('·').trim() || tool, 'avatar', { table: `arrive:${tool}`, gesture: 'present-right', target: 'hotspot:table' })
      }),
      seg(f.close, 'avatar', { table: 'react:all', gesture: 'thumbs-up' }),
    ],
  },
  {
    id: 'browser',
    name: 'Browser demo: open the monitor',
    summary: 'You point at the studio monitor; it opens into a live browser, you explain, it closes back.',
    scenes: ['studio-solo'],
    fields: [
      { key: 'url', label: 'Site', default: 'https://fake-real.live' },
      { key: 'via', label: 'Opens out of', default: 'monitor', options: HOTSPOT_OPTIONS },
      { key: 'intro', label: 'Intro (you, full frame)', default: 'Let me show you Fake-Real, live.' },
      { key: 'points', label: 'What you explain in the browser (one per line)', lines: true,
        default: 'Paste any link and it checks the story against trusted sources.\nGreen means real, red means fake, with the reasons.\nEvery verdict links to its sources.' },
      { key: 'outro', label: 'Back at the desk', default: "That's Fake-Real. Try it with the next link you're not sure about." },
    ],
    build: (f) => {
      const url = /^https?:\/\//.test(f.url) ? f.url : `https://${f.url}`
      const pts = lines(f.points)
      return [
        seg(f.intro, 'avatar', { scene: 'studio-solo', gesture: 'auto', target: `hotspot:${f.via}` }),
        ...pts.map((p, i) => seg(p, 'content', i === 0 ? { visual: `url:${url}`, via: f.via, transitionMs: 1400 } : {})),
        seg(f.outro, 'avatar', { via: f.via, transitionMs: 1200, gesture: 'thumbs-up' }),
      ]
    },
  },
  {
    id: 'explain-card',
    name: 'Explain the Main card',
    summary: 'You point at the content, it maximizes while you talk, then the scene comes back.',
    scenes: ['studio-desk'],
    fields: [
      { key: 'intro', label: 'Intro', default: 'Look at this.' },
      { key: 'points', label: 'Points (one per line; add "zoom" to zoom in)', lines: true, default: 'This is the overview.\nNotice the numbers top right, zoom.' },
      { key: 'outro', label: 'Wrap-up', default: "That's the idea." },
    ],
    build: (f) => [
      seg(f.intro, 'duo', { scene: 'studio-desk', gesture: 'auto', target: 'main' }),
      ...lines(f.points).map((p) => {
        const z = /\bzoom\b/i.test(p)
        const text = p.replace(/,?\s*\bzoom\b\.?/i, '').trim()
        return seg(text, 'content', z ? { zoom: { x: 0.75, y: 0.25, scale: 1.7 } } : {})
      }),
      seg(f.outro, 'split'),
    ],
  },
  {
    id: 'compare',
    name: 'Compare two things (left vs right)',
    summary: 'Two cards come in left and right; you point at each, then the winner comes forward. Add both from the Library first.',
    scenes: ['studio-solo'],
    fields: [
      { key: 'left', label: 'Left card (media card name)', default: 'Claude Code' },
      { key: 'leftLine', label: 'About the left one', default: 'On my left: the thinker. Plans, reviews, writes.' },
      { key: 'right', label: 'Right card (media card name)', default: 'Codex' },
      { key: 'rightLine', label: 'About the right one', default: 'On my right: the builder. From idea to running code.' },
      { key: 'verdict', label: 'Verdict', default: 'Together they ship twice as fast.' },
    ],
    build: (f) => [
      seg(f.leftLine, 'avatar', { scene: 'studio-solo', media: `move:${f.left}@0.17,0.32,0.22; hide:${f.right}`, gesture: 'auto', target: `media:${f.left}` }),
      seg(f.rightLine, 'avatar', { media: `move:${f.right}@0.83,0.32,0.22`, gesture: 'auto', target: `media:${f.right}` }),
      seg(f.verdict, 'avatar', { media: `reset:${f.left}; reset:${f.right}`, gesture: 'welcome' }),
    ],
  },
  {
    id: 'news',
    name: 'Talking head: news or opinion',
    summary: 'You in the studio with natural beats: welcome, think, thumbs-up. Small circle if the voice is not lip-synced.',
    scenes: ['studio-solo', 'studio-circle'],
    fields: [
      { key: 'headline', label: 'Headline', default: 'Big news in AI this week.' },
      { key: 'points', label: 'Points (one per line)', lines: true, default: 'Here is what happened.\nHere is why it matters.\nHere is what I would do.' },
    ],
    build: (f) => {
      const pts = lines(f.points)
      return [
        seg(f.headline, 'avatar', { scene: 'studio-solo', gesture: 'welcome' }),
        ...pts.map((p, i) => seg(p, 'avatar', i === Math.floor(pts.length / 2) ? { gesture: 'think' } : {})),
      ]
    },
  },
  {
    id: 'outro',
    name: 'Outro: call to action',
    summary: 'Back at the desk, the tools react, you wave goodbye.',
    scenes: ['world-of-ai'],
    fields: [
      { key: 'line', label: 'Call to action', default: "If this helped, subscribe. Next week we build one live. See you there." },
    ],
    build: (f) => [seg(f.line, 'avatar', { scene: 'world-of-ai', table: 'react:all', gesture: 'wave' })],
  },
]

export const workflowDefaults = (w: Workflow) => Object.fromEntries(w.fields.map((x) => [x.key, x.default ?? '']))
