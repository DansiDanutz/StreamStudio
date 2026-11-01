/** Publish kit: what YouTube needs next to the video, built from the compiled timeline.
 *  Captions (.srt) come straight from the script text and the voice timings, so they need no
 *  speech recognition; chapters follow the scene changes; the description opens with the hook.
 *  Pure, like the timeline: the Timeline panel, agents and tests all read the same result. */

import type { Timeline, TimelineItem } from '../director/timeline'

export interface PublishKit {
  title: string
  description: string
  /** "0:00 Title" lines, YouTube's chapter format. Empty when YouTube would reject them. */
  chapters: string[]
  srt: string
  /** Things to know before publishing (estimated timings, chapters left out, …). */
  notes: string[]
}

const LINE_CHARS = 42
const LINES_PER_CAPTION = 2
const MIN_CHAPTERS = 3
const MIN_CHAPTER_MS = 10_000
const CHAPTER_TITLE_CHARS = 60

const pad = (n: number, width = 2) => String(n).padStart(width, '0')

export function srtTime(ms: number): string {
  const t = Math.max(0, Math.round(ms))
  return `${pad(Math.floor(t / 3_600_000))}:${pad(Math.floor(t / 60_000) % 60)}:${pad(Math.floor(t / 1000) % 60)},${pad(t % 1000, 3)}`
}

export function youtubeTime(ms: number): string {
  const s = Math.floor(Math.max(0, ms) / 1000)
  const h = Math.floor(s / 3600)
  const m = Math.floor(s / 60) % 60
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
}

/** Split text into captions of at most two lines of 42 characters, breaking between words. */
export function captionChunks(text: string): string[] {
  const lines: string[] = []
  for (const word of text.trim().split(/\s+/).filter(Boolean)) {
    const last = lines.at(-1)
    if (last !== undefined && `${last} ${word}`.length <= LINE_CHARS) lines[lines.length - 1] = `${last} ${word}`
    else lines.push(word)
  }
  const chunks: string[] = []
  for (let i = 0; i < lines.length; i += LINES_PER_CAPTION) chunks.push(lines.slice(i, i + LINES_PER_CAPTION).join('\n'))
  return chunks
}

/** A line with no clip and no narration plays silent: it gets no caption. */
const voiced = (i: TimelineItem) => i.voice !== 'none' && i.text.trim().length > 0

function captionsFor(items: TimelineItem[]): string {
  const cues: string[] = []
  for (const it of items) {
    if (!voiced(it)) continue
    const chunks = captionChunks(it.text)
    const voiceStart = it.startMs + it.leadMs
    const total = chunks.reduce((n, c) => n + c.length, 0)
    let at = voiceStart
    chunks.forEach((chunk, k) => {
      const end = k === chunks.length - 1 ? voiceStart + it.voiceMs : at + Math.round((it.voiceMs * chunk.length) / total)
      cues.push(`${cues.length + 1}\n${srtTime(at)} --> ${srtTime(end)}\n${chunk}\n`)
      at = end
    })
  }
  return cues.join('\n')
}

function firstSentence(text: string): string {
  const sentence = text.trim().split(/(?<=[.!?])\s/)[0].replace(/[.!?]+$/, '')
  return sentence.length > CHAPTER_TITLE_CHARS ? `${sentence.slice(0, CHAPTER_TITLE_CHARS - 1).trimEnd()}…` : sentence
}

interface Chapter { startMs: number; title: string }

function chaptersFor(tl: Timeline, notes: string[]): string[] {
  const raw: Chapter[] = []
  let sceneId: string | undefined
  for (const it of tl.items) {
    const id = it.sceneInEffect?.id
    if (raw.length === 0 || id !== sceneId) raw.push({ startMs: it.startMs, title: firstSentence(it.text) || it.sceneInEffect?.name || 'Part' })
    sceneId = id
  }
  // Fold any chapter shorter than YouTube's 10 s minimum into the one before it.
  const merged: Chapter[] = []
  raw.forEach((c, k) => {
    const end = raw[k + 1]?.startMs ?? tl.totalMs
    if (merged.length && end - c.startMs < MIN_CHAPTER_MS) return
    merged.push(c)
  })
  const lastTooShort = merged.length > 1 && tl.totalMs - merged[merged.length - 1].startMs < MIN_CHAPTER_MS
  if (lastTooShort) merged.pop()
  if (merged.length < MIN_CHAPTERS) {
    notes.push(`No chapters: YouTube needs at least 3 chapters of 10 s or more, and this script has ${merged.length}. Switch scenes at the start of each part to make chapters.`)
    return []
  }
  return merged.map((c) => `${youtubeTime(c.startMs)} ${c.title}`)
}

export function buildPublishKit(script: { title: string }, tl: Timeline, clipMs: ReadonlyMap<string, number>): PublishKit {
  const notes: string[] = []
  const estimated = tl.items.filter((i) => i.voice === 'clip' && i.clip && !clipMs.has(i.clip)).length
  if (estimated) notes.push(`${estimated} lines are timed from word count, not their clip length: open the Timeline so the clips load, then rebuild for exact timings.`)
  const silent = tl.items.filter((i) => i.voice === 'none' && i.text.trim()).length
  if (silent) notes.push(`${silent} ${silent === 1 ? 'line has' : 'lines have'} no voice yet (no clip or narration), so ${silent === 1 ? 'it is' : 'they are'} left out of the captions.`)
  const chapters = chaptersFor(tl, notes)
  const hook = tl.items.find((i) => i.text.trim())?.text.trim() ?? ''
  const description = [hook, chapters.length ? `Chapters\n${chapters.join('\n')}` : ''].filter(Boolean).join('\n\n')
  return { title: script.title, description, chapters, srt: captionsFor(tl.items), notes }
}
