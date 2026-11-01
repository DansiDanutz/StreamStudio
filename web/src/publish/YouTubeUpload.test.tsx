import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { YouTubeUpload } from './YouTubeUpload'

const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
const takes = [{ id: 'rec_20261101-020000', mp4: true, transcript: true }, { id: 'rec_20261101-010000', mp4: false, transcript: false }]

function server(status: object, extra: Record<string, unknown> = {}) {
  const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
    if (url === '/api/youtube') return ok(status)
    if (url === '/api/recordings') return ok(takes)
    if (url in extra) return ok(extra[url])
    throw new Error(`unexpected ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('YouTubeUpload', () => {
  it('offers to import the client JSON when it is in Downloads', async () => {
    const f = server({ client: false, connected: false, channels: [], download_ready: true }, { '/api/youtube/client': {} })
    await act(async () => { render(<YouTubeUpload title="T" description="D" />) })
    await act(async () => { fireEvent.click(screen.getByText('Import it')) })
    expect(f).toHaveBeenCalledWith('/api/youtube/client', { method: 'POST' })
  })

  it('links to Connect when the client is there but the channel is not', async () => {
    server({ client: true, connected: false, channels: [], download_ready: false })
    await act(async () => { render(<YouTubeUpload title="T" description="D" />) })
    expect(screen.getByText('Connect YouTube').getAttribute('href')).toBe('/api/youtube/connect')
  })

  it('uploads the newest finished take, private, to the chosen channel', async () => {
    vi.useFakeTimers()
    const job = { status: 'done', progress: 1, message: '', result: { url: 'https://youtu.be/v', studio: 'https://studio.youtube.com/video/v/edit', channel: 'UC2' } }
    const channels = [{ id: 'UC1', title: 'DansLab' }, { id: 'UC2', title: 'Did You Know That?' }]
    const f = server(
      { client: true, connected: true, channels, download_ready: false },
      { '/api/recordings/rec_20261101-020000/youtube': { job_id: 'job_1' }, '/api/jobs/job_1': job },
    )
    await act(async () => { render(<YouTubeUpload title="My video" description="About it" />) })
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toContain('20261101-020000 · captions')
    expect(screen.getByText('Connect another channel').getAttribute('href')).toBe('/api/youtube/connect')
    fireEvent.change(screen.getByLabelText('Channel'), { target: { value: 'UC2' } })
    await act(async () => { fireEvent.click(screen.getByText('Upload to Did You Know That?')) })
    const [, init] = f.mock.calls.find(([u]) => u.endsWith('/youtube') && u.startsWith('/api/recordings'))!
    expect(JSON.parse(String(init?.body))).toEqual({ title: 'My video', description: 'About it', privacy: 'private', channel: 'UC2' })
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(screen.getByText('open in YouTube Studio').getAttribute('href')).toBe(job.result.studio)
    expect(screen.getByText(/Uploaded \(private\) to Did You Know That\?/)).toBeTruthy()
  })
})
