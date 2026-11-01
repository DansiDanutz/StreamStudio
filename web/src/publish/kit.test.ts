import { describe, expect, it } from 'vitest'
import type { Timeline, TimelineItem } from '../director/timeline'
import { buildPublishKit, captionChunks, srtTime, youtubeTime } from './kit'

const scene = (id: string) => ({ id, name: id })

function item(index: number, startMs: number, voiceMs: number, text: string, sceneId: string, extra: Partial<TimelineItem> = {}): TimelineItem {
  return {
    index, id: `s${index}`, startMs, leadMs: 0, voiceMs, endMs: startMs + voiceMs, text,
    scene: null, sceneInEffect: scene(sceneId), cue: 'avatar', plays: 'avatar', lips: true,
    voice: 'clip', clip: `/avatar/s${index}.mp4`, gesture: null, warnings: [], ...extra,
  }
}

function timeline(items: TimelineItem[]): Timeline {
  return { totalMs: items.at(-1)!.endMs, items, warnings: 0 }
}

const known = new Map<string, number>([['/avatar/s0.mp4', 1], ['/avatar/s1.mp4', 1], ['/avatar/s2.mp4', 1], ['/avatar/s3.mp4', 1]])

describe('time formats', () => {
  it('formats SRT times', () => {
    expect(srtTime(0)).toBe('00:00:00,000')
    expect(srtTime(3_723_045)).toBe('01:02:03,045')
  })

  it('formats YouTube chapter times', () => {
    expect(youtubeTime(0)).toBe('0:00')
    expect(youtubeTime(75_900)).toBe('1:15')
    expect(youtubeTime(3_723_000)).toBe('1:02:03')
  })
})

describe('captionChunks', () => {
  it('keeps short lines whole', () => {
    expect(captionChunks('Hello there.')).toEqual(['Hello there.'])
  })

  it('wraps long text into captions of at most two 42-character lines', () => {
    const chunks = captionChunks('This is a much longer sentence that keeps going well past what fits on a single caption line, so it has to be split.')
    expect(chunks.length).toBeGreaterThan(1)
    for (const c of chunks) {
      const lines = c.split('\n')
      expect(lines.length).toBeLessThanOrEqual(2)
      for (const l of lines) expect(l.length).toBeLessThanOrEqual(42)
    }
    expect(chunks.join(' ').replace(/\n/g, ' ')).toBe('This is a much longer sentence that keeps going well past what fits on a single caption line, so it has to be split.')
  })
})

describe('buildPublishKit', () => {
  const tl = timeline([
    item(0, 0, 20_000, 'Welcome to the world of AI. Today we meet seven agents.', 'intro'),
    item(1, 20_000, 30_000, 'First, Claude Code writes and ships software.', 'desk'),
    item(2, 50_000, 5_000, 'It is fast.', 'desk'),
    item(3, 55_000, 25_000, 'Finally, how they work together as one team.', 'outro', { leadMs: 2_000, startMs: 55_000, endMs: 82_000 }),
  ])

  it('writes SRT captions timed to each spoken line, after any gesture lead-in', () => {
    const kit = buildPublishKit({ title: 'World of AI' }, tl, known)
    expect(kit.srt.startsWith('1\n00:00:00,000 --> ')).toBe(true)
    expect(kit.srt).toContain('00:00:57,000 --> 00:01:22,000\nFinally, how they work together as one\nteam.')
    expect(kit.srt.trim().split('\n\n').length).toBeGreaterThanOrEqual(4)
  })

  it('makes a chapter at each scene change, titled from its first sentence, starting at 0:00', () => {
    const kit = buildPublishKit({ title: 'World of AI' }, tl, known)
    expect(kit.chapters).toEqual([
      '0:00 Welcome to the world of AI',
      '0:20 First, Claude Code writes and ships software',
      '0:55 Finally, how they work together as one team',
    ])
  })

  it('folds chapters shorter than 10 seconds into the previous one', () => {
    const short = timeline([
      item(0, 0, 20_000, 'Intro line.', 'a'),
      item(1, 20_000, 4_000, 'Quick aside.', 'b'),
      item(2, 24_000, 20_000, 'Main part.', 'c'),
      item(3, 44_000, 20_000, 'Wrap up.', 'd'),
    ])
    expect(buildPublishKit({ title: 'T' }, short, new Map()).chapters.map((c) => c.split(' ')[0])).toEqual(['0:00', '0:24', '0:44'])
  })

  it('leaves chapters out, with a reason, when YouTube would reject them', () => {
    const two = timeline([item(0, 0, 20_000, 'One.', 'a'), item(1, 20_000, 20_000, 'Two.', 'b')])
    const kit = buildPublishKit({ title: 'T' }, two, new Map())
    expect(kit.chapters).toEqual([])
    expect(kit.notes.join(' ')).toMatch(/at least 3 chapters/)
  })

  it('writes a description with the opening line and the chapters', () => {
    const kit = buildPublishKit({ title: 'World of AI' }, tl, known)
    expect(kit.title).toBe('World of AI')
    expect(kit.description).toContain('Welcome to the world of AI. Today we meet seven agents.')
    expect(kit.description).toContain('Chapters\n0:00 Welcome to the world of AI')
  })

  it('says when timings are estimates because clip lengths are not loaded', () => {
    const kit = buildPublishKit({ title: 'T' }, tl, new Map())
    expect(kit.notes.join(' ')).toMatch(/4 lines are timed from word count/)
  })

  it('captions only lines that are actually voiced, and says which were left out', () => {
    // A line with no clip and no narration plays silent: captioning it would show words nobody says.
    const silent = timeline([item(0, 0, 5_000, 'Not recorded yet.', 'a', { voice: 'none', lips: false, clip: undefined }), item(1, 5_000, 5_000, 'Spoken.', 'a')])
    const kit = buildPublishKit({ title: 'T' }, silent, new Map())
    expect(kit.srt).toBe('1\n00:00:05,000 --> 00:00:10,000\nSpoken.\n')
    expect(kit.notes.join(' ')).toMatch(/1 line has no voice yet/)
  })
})

describe('publish.kit agent action', () => {
  it('returns the kit for the script in the editor', async () => {
    const { EXECUTORS } = await import('../agent/bridge')
    const { useDirector } = await import('../director/store')
    const { newSegment } = await import('../director/types')
    useDirector.getState().insertSegments([{ ...newSegment('Hello and welcome.', 'avatar'), voice: 'narration', audio: '/a.mp3' }], 'replace', 'Agent test')
    const kit = EXECUTORS['publish.kit']({}) as { title: string; srt: string }
    expect(kit.title).toBe('Agent test')
    expect(kit.srt).toContain('Hello and welcome.')
  })

  it('is listed in the agent catalog', async () => {
    const { buildCatalog } = await import('../agent/catalog')
    expect(JSON.stringify(buildCatalog())).toContain('publish.kit')
  })
})
