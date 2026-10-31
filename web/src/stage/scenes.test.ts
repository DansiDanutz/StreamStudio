import { beforeEach, describe, expect, it, vi } from 'vitest'
import { COLLECTIONS, PRESETS, clone } from './presets'
import { migrateScenes, orderedScenes, useStage } from './store'
import { initSceneSync, sceneBody } from './sceneSync'
import type { Scene } from './types'

const reset = () => useStage.setState({ scenes: clone(PRESETS), activeId: 'world-of-ai', sync: 'local' })

describe('scene library', () => {
  beforeEach(reset)

  it('templates cover the collections and open on the opener', () => {
    expect(orderedScenes(PRESETS)[0].id).toBe('world-of-ai')
    for (const p of PRESETS) expect(COLLECTIONS).toContain(p.collection)
  })
  it('orders by collection, then list order', () => {
    const s = [{ ...PRESETS[1], id: 'a', collection: 'Demo' }, { ...PRESETS[1], id: 'b', collection: 'Openers' }, { ...PRESETS[1], id: 'c', collection: 'Demo' }] as Scene[]
    expect(orderedScenes(s).map((x) => x.id)).toEqual(['b', 'a', 'c'])
  })
  it('migrates a v2 library: collections assigned, new templates added once', () => {
    const v2 = [{ ...PRESETS[1], collection: undefined }, { ...PRESETS[1], id: 'mine', name: 'Mine', collection: undefined }] as Scene[]
    const out = migrateScenes(v2, true)
    expect(out.find((s) => s.id === 'studio-desk')!.collection).toBe('Talk')
    expect(out.find((s) => s.id === 'mine')!.collection).toBe('Talk')
    expect(out.filter((s) => s.id === 'world-of-ai')).toHaveLength(1)
    expect(migrateScenes(v2, false).some((s) => s.id === 'world-of-ai')).toBe(false)
  })
  it('new, duplicate, rename, move between collections', () => {
    const st = useStage.getState()
    st.newScene('studio-circle', 'Social')
    const made = useStage.getState().active()
    expect(made.collection).toBe('Social')
    expect(made.name).toBe('Studio + Circle 2')
    st.duplicateScene(made.id)
    const dup = useStage.getState().active()
    expect(dup.name).toBe('Studio + Circle 3')
    st.renameScene(dup.id, '  Shorts intro ')
    expect(useStage.getState().active().name).toBe('Shorts intro')
    st.moveScene(dup.id, 'Openers', 'world-of-ai')
    const o = orderedScenes(useStage.getState().scenes)
    expect(o[0].id).toBe(dup.id)
    expect(o[0].collection).toBe('Openers')
  })
  it('imports scenes with fresh ids; rejects junk', () => {
    const n = useStage.getState().importScenes([PRESETS[0], { nope: 1 } as unknown as Scene])
    expect(n).toBe(1)
    expect(useStage.getState().scenes.filter((s) => s.name === 'World of AI')).toHaveLength(2)
    expect(useStage.getState().importScenes([])).toBe(0)
  })
})

describe('server sync', () => {
  beforeEach(reset)

  it('falls back to local when there is no server', async () => {
    const f = vi.fn().mockResolvedValue(new Response('<html>', { status: 200, headers: { 'content-type': 'text/html' } }))
    expect(await initSceneSync(f as unknown as typeof fetch)).toBe('local')
    expect(useStage.getState().sync).toBe('local')
  })
  it('server wins on load, then changes are written back (debounced) and deletes are sent', async () => {
    vi.useFakeTimers()
    const remote = [{ ...PRESETS.find((p) => p.id === 'studio-circle')!, position: 0 }]
    const calls: [string, string][] = []
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push([init?.method ?? 'GET', url])
      return url === '/api/scenes' && !init ? Response.json(remote) : new Response(null, { status: 200 })
    })
    expect(await initSceneSync(f as unknown as typeof fetch)).toBe('server')
    expect(useStage.getState().scenes.map((s) => s.id)).toEqual(['studio-circle'])
    useStage.getState().renameScene('studio-circle', 'Circle')
    useStage.getState().renameScene('studio-circle', 'Circle 2')
    await vi.advanceTimersByTimeAsync(600)
    expect(calls.filter(([m]) => m === 'PUT')).toEqual([['PUT', '/api/scenes/studio-circle']])
    useStage.getState().newScene('raw')
    const id = useStage.getState().activeId
    useStage.getState().deleteScene(id)
    await vi.advanceTimersByTimeAsync(600)
    expect(calls).toContainEqual(['DELETE', `/api/scenes/${id}`])
    vi.useRealTimers()
  })
  it('sends the scene body without id/name/collection inside data', () => {
    const b = sceneBody({ ...PRESETS[0] }, 3)
    expect(b).toMatchObject({ name: 'World of AI', collection: 'Openers', position: 3 })
    expect(b.data).not.toHaveProperty('id')
    expect(b.data).toHaveProperty('layouts')
  })
})
