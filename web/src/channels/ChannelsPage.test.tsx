import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ChannelsPage } from './ChannelsPage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('preserves unsaved settings after a version conflict and reloads the latest version', async () => {
  const profile = { slug: 'danslab', name: 'DansLab', language: 'en', youtube_channel: null,
    presenter: { name: 'Dan', avatar_id: 'dan', voice_id: 'original' },
    publish: { description_footer: '', default_tags: [] } }
  let version = 1
  const fetcher = vi.fn(async (path: string, opts: RequestInit) => {
    if (opts.method === 'PUT') {
      expect(JSON.parse(String(opts.body)).base_version).toBe(1)
      version = 2
      return { ok: false, json: async () => ({ detail: 'profile changed; reload' }) }
    }
    const json = path === '/api/channels' ? [{ slug: 'danslab', name: 'DansLab', default: true, version }]
      : { profile, version }
    return { ok: true, json: async () => json }
  })
  vi.stubGlobal('fetch', fetcher)
  render(<ChannelsPage />)
  const voice = await screen.findByLabelText('Voice ID') as HTMLInputElement
  fireEvent.change(voice, { target: { value: 'edited' } })
  fireEvent.click(screen.getByText('Save new version'))
  await screen.findByText('profile changed; reload')
  expect(voice.value).toBe('edited')
  fireEvent.click(screen.getByText('Discard edits and reload'))
  await waitFor(() => expect(voice.value).toBe('original'))
  expect(screen.getByText('DansLab · version 2')).toBeTruthy()
})
