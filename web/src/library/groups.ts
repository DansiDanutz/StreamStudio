/** Library tabs, filters and search. Pure functions: the panel and its tests share them.
 *  The grouping matches the server's (api/routes/agent.py GROUPS) so agents and the editor
 *  see the same tabs. */

import type { Artifact } from '../agent/catalog'

export const GROUPS: Record<string, string> = {
  scene: 'Scenes', template: 'Scenes',
  gesture: 'Avatar', clip: 'Avatar',
  object: 'Media', media: 'Media', 'stage-media': 'Media',
  recording: 'Recordings',
  workflow: 'Workflows',
  cue: 'Layouts', hotspot: 'Layouts', target: 'Layouts',
}
export const TABS = ['All', 'Scenes', 'Avatar', 'Media', 'Recordings', 'Workflows', 'Layouts'] as const

export const KIND_LABEL: Record<string, string> = {
  scene: 'Scenes', template: 'Templates', gesture: 'Gestures', clip: 'Clips', object: 'Objects', media: 'Media',
  'stage-media': 'On stage now', recording: 'Takes', workflow: 'Workflows', cue: 'Layouts', hotspot: 'Studio places', target: 'Cards',
}

export interface Storage { key: string; local: boolean; vault: boolean }
export interface LibItem extends Artifact {
  group: string
  tags: string[]
  storage?: Storage
  created?: number | null
  default_name?: string
  clip_ready?: boolean
  url?: string
  bytes?: number | null
}

export type StatusFilter = 'any' | 'ready' | 'needs-clip'
export type StoreFilter = 'any' | 'local' | 'vault' | 'vault-only' | 'not-backed-up'
export type Sort = 'group' | 'name' | 'newest'

export interface Filters {
  tab: string
  q: string
  kind: string
  status: StatusFilter
  store: StoreFilter
  tag: string
  sort: Sort
}

export const NO_FILTERS: Filters = { tab: 'All', q: '', kind: 'all', status: 'any', store: 'any', tag: '', sort: 'group' }

export const asItem = (a: Artifact & Partial<LibItem>): LibItem => ({ ...a, group: a.group ?? GROUPS[a.kind] ?? 'Other', tags: a.tags ?? [] })

const haystack = (a: LibItem) => `${a.name} ${a.default_name ?? ''} ${a.id} ${a.description} ${a.tags.join(' ')} ${KIND_LABEL[a.kind] ?? a.kind}`.toLowerCase()

/** Every search word must appear (name, id, description, tags or kind). */
export const matches = (a: LibItem, q: string) => q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => haystack(a).includes(w))

/** A gesture with no rendered clip yet (a pointer cue stands in). */
export const needsClip = (a: LibItem) => a.kind === 'gesture' && !a.clip_ready

export function storeOf(a: LibItem): StoreFilter[] {
  const s = a.storage
  if (!s) return []
  const out: StoreFilter[] = []
  if (s.local) out.push('local')
  if (s.vault) out.push('vault')
  if (s.vault && !s.local) out.push('vault-only')
  if (s.local && !s.vault) out.push('not-backed-up')
  return out
}

export function filterItems(items: LibItem[], f: Filters): LibItem[] {
  const out = items.filter((a) =>
    (f.tab === 'All' || a.group === f.tab) &&
    (f.kind === 'all' || a.kind === f.kind) &&
    (f.status === 'any' || (f.status === 'needs-clip') === needsClip(a)) &&
    (f.store === 'any' || storeOf(a).includes(f.store)) &&
    (!f.tag || a.tags.includes(f.tag)) &&
    (!f.q || matches(a, f.q)))
  const order = TABS as readonly string[]
  if (f.sort === 'name') out.sort((x, y) => x.name.localeCompare(y.name))
  else if (f.sort === 'newest') out.sort((x, y) => (y.created ?? 0) - (x.created ?? 0))
  else {
    const kinds = Object.keys(KIND_LABEL)
    out.sort((x, y) => order.indexOf(x.group) - order.indexOf(y.group) || kinds.indexOf(x.kind) - kinds.indexOf(y.kind))
  }
  return out
}

export const countBy = (items: LibItem[], key: (a: LibItem) => string) =>
  items.reduce<Record<string, number>>((m, a) => { const k = key(a); m[k] = (m[k] ?? 0) + 1; return m }, {})

export const fmtBytes = (n?: number | null) =>
  n == null ? '' : n > 1e9 ? `${(n / 1e9).toFixed(1)} GB` : n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1e3))} KB`
