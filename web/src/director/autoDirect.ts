/** Rule-based auto-direct: proposes a cue (and zoom) for each segment from its text.
 *  Deterministic and explainable; an LLM pass can refine it later. Pinned segments are kept. */

import type { Cue, Script, Segment, Zoom } from './types'

interface Rule {
  name: string
  test: RegExp
  cue: Cue
  weight: number
}

// EN + RO, matched case-insensitively. Order does not matter; weights are summed per cue.
const RULES: Rule[] = [
  // Direct address and personal framing → presenter
  { name: 'greeting', test: /\b(welcome|hi|hello|hey|salut|bun[aă] (ziua|seara)|bine a[tț]i venit)\b/i, cue: 'avatar', weight: 3 },
  { name: 'outro', test: /\b(subscribe|like|comment|thanks for watching|see you|abona|mul[tț]umesc|ne vedem)\b/i, cue: 'avatar', weight: 3 },
  { name: 'personal', test: /\b(i think|i believe|my (story|opinion|take)|in my experience|eu cred|p[aă]rerea mea)\b/i, cue: 'avatar', weight: 2 },
  { name: 'question', test: /\?\s*$/, cue: 'avatar', weight: 1 },

  // Pointing at the screen → content
  { name: 'look', test: /\b(look at|take a look|as you can see|check (this|it) out|on (the )?screen|here (we|you) (have|see)|uita[tț]i-v[aă]|dup[aă] cum vede[tț]i|pe ecran|aici (avem|vede[tț]i))\b/i, cue: 'content', weight: 3 },
  { name: 'demo', test: /\b(dashboard|website|app|page|chart|graph|code|terminal|repo|settings|menu|table|result|demo|live)\b/i, cue: 'content', weight: 2 },
  { name: 'walkthrough', test: /\b(step \d|first|then|next|finally|now (we|i)|let'?s (go|open|click|run)|hai s[aă]|acum|apoi|primul pas)\b/i, cue: 'content', weight: 1 },

  // Fine detail → zoom (also counts as content)
  { name: 'detail', test: /\b(this (button|number|line|value|field|icon|tab|corner|part)|right here|in the (top|bottom) (left|right)|zoom|notice (the|this)|butonul|aici sus|aici jos|col[tț]ul)\b/i, cue: 'content', weight: 2 },

  // Big reveal → full frame
  { name: 'reveal', test: /\b(full ?screen|the whole (screen|thing|picture)|let it play|watch this|here'?s the (result|final)|rezultatul final|tot ecranul)\b/i, cue: 'full', weight: 3 },
]

const ZOOM_HINTS: { test: RegExp; zoom: Zoom }[] = [
  { test: /top[- ]left|st[aâ]nga sus/i, zoom: { x: 0.2, y: 0.2, scale: 1.7 } },
  { test: /top[- ]right|dreapta sus/i, zoom: { x: 0.8, y: 0.2, scale: 1.7 } },
  { test: /bottom[- ]left|st[aâ]nga jos/i, zoom: { x: 0.2, y: 0.8, scale: 1.7 } },
  { test: /bottom[- ]right|dreapta jos/i, zoom: { x: 0.8, y: 0.8, scale: 1.7 } },
  { test: /\b(top|header|title bar|sus)\b/i, zoom: { x: 0.5, y: 0.15, scale: 1.5 } },
  { test: /\b(bottom|footer|jos)\b/i, zoom: { x: 0.5, y: 0.85, scale: 1.5 } },
  { test: /\b(left|st[aâ]nga)\b/i, zoom: { x: 0.25, y: 0.5, scale: 1.5 } },
  { test: /\b(right|dreapta)\b/i, zoom: { x: 0.75, y: 0.5, scale: 1.5 } },
  { test: /this (button|number|line|value|field|icon)|right here|zoom|notice|butonul/i, zoom: { x: 0.5, y: 0.5, scale: 1.5 } },
]

export interface Proposal {
  cue: Cue
  zoom?: Zoom
  reasons: string[]
}

export function propose(text: string, index: number, total: number): Proposal {
  const score: Record<Cue, number> = { avatar: 0, duo: 0, split: 0.5, content: 0, full: 0, pip: 0 }
  const reasons: string[] = []
  for (const r of RULES) {
    if (r.test.test(text)) {
      score[r.cue] += r.weight
      reasons.push(r.name)
    }
  }
  // Structure: first and last segments lean to the presenter.
  if (index === 0) { score.avatar += 2; reasons.push('opening') }
  if (index === total - 1 && total > 1) { score.avatar += 2; reasons.push('closing') }

  let cue = (Object.keys(score) as Cue[]).reduce((a, b) => (score[b] > score[a] ? b : a))
  // Presenter segments: clean full-frame when nothing on screen is referenced, otherwise keep a small content window.
  if (cue === 'avatar' && reasons.some((r) => r === 'demo' || r === 'look' || r === 'walkthrough')) cue = 'duo'
  let zoom: Zoom | undefined
  if (cue === 'content' && reasons.includes('detail')) {
    zoom = ZOOM_HINTS.find((z) => z.test.test(text))?.zoom ?? { x: 0.5, y: 0.5, scale: 1.5 }
  }
  return { cue, zoom, reasons }
}

export function autoDirect(script: Script): Script {
  const n = script.segments.length
  return {
    ...script,
    segments: script.segments.map((s, i): Segment => {
      if (s.pinned) return s
      const p = propose(s.text, i, n)
      return { ...s, cue: p.cue, zoom: p.zoom }
    }),
  }
}

/** Split free text into segments: one per paragraph, or per sentence group of ~2 when paragraphs are long. */
export function splitScript(text: string): string[] {
  const paras = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)
  const out: string[] = []
  for (const p of paras) {
    const sentences = p.match(/[^.!?]+[.!?]+["')\]]*|[^.!?]+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [p]
    if (sentences.length <= 3) { out.push(p); continue }
    for (let i = 0; i < sentences.length; i += 2) out.push(sentences.slice(i, i + 2).join(' '))
  }
  return out
}
