import { describe, expect, it } from 'vitest'
import { buildCatalog } from '../agent/catalog'
import { NO_FILTERS, TABS, asItem, filterItems, matches, type LibItem } from './groups'

const items: LibItem[] = buildCatalog().artifacts.map(asItem)
const take: LibItem = asItem({
  id: 'recording:rec_20261031-234012', kind: 'recording', name: 'Take · 31 Oct 2026 · 23:40:12', description: 'A take.', actions: [],
  tags: ['ep12'], storage: { key: 'recordings/rec_20261031-234012.mp4', local: false, vault: true }, created: 2,
})
const clip: LibItem = asItem({
  id: 'clip:intro', kind: 'clip', name: 'Hello opener', description: 'Clip.', actions: [],
  tags: [], storage: { key: 'assets/avatar/clips/intro.mp4', local: true, vault: false }, created: 3,
})
const all = [...items, take, clip]

describe('library tabs and filters', () => {
  it('puts every artifact in a tab, with a specific name', () => {
    for (const a of all) expect(TABS, a.id).toContain(a.group)
    const names = items.map((a) => a.name)
    expect(new Set(names).size).toBe(names.length)
    expect(items.find((a) => a.id === 'cue:avatar')?.name).toBe('Dan full frame')
  })
  it('filters by tab, kind, status, storage and tag, and searches every word', () => {
    expect(filterItems(all, { ...NO_FILTERS, tab: 'Recordings' }).map((a) => a.id)).toEqual([take.id])
    expect(filterItems(all, { ...NO_FILTERS, tab: 'Avatar', kind: 'gesture' }).every((a) => a.kind === 'gesture')).toBe(true)
    expect(filterItems(all, { ...NO_FILTERS, status: 'needs-clip' }).every((a) => a.kind === 'gesture' && !a.clip_ready)).toBe(true)
    expect(filterItems(all, { ...NO_FILTERS, store: 'vault-only' })).toEqual([take])
    expect(filterItems(all, { ...NO_FILTERS, store: 'not-backed-up' })).toEqual([clip])
    expect(filterItems(all, { ...NO_FILTERS, tag: 'ep12' })).toEqual([take])
    expect(matches(clip, 'hello  OPENER')).toBe(true)
    expect(matches(clip, 'hello goodbye')).toBe(false)
    expect(filterItems(all, { ...NO_FILTERS, q: 'point right' }).some((a) => a.id === 'gesture:point-right')).toBe(true)
  })
  it('sorts newest first or A–Z', () => {
    expect(filterItems([take, clip], { ...NO_FILTERS, sort: 'newest' })[0]).toBe(clip)
    expect(filterItems([clip, take], { ...NO_FILTERS, sort: 'name' })[0]).toBe(clip)
  })
})
