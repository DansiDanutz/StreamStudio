import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TakeTranscript } from './TakeTranscript'

const reply = (body: unknown, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response)

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('TakeTranscript', () => {
  it('links the captions when the take already has a transcript', () => {
    render(<TakeTranscript id="rec_1" ready />)
    expect(screen.getByText('captions (.srt)').getAttribute('href')).toBe('/api/recordings/rec_1.srt')
  })

  it('queues the job, polls it and then links the captions', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn((url: string) =>
      url.endsWith('/transcribe') ? reply({ id: 'rec_1', job_id: 'job_9' }) : reply({ status: 'done' }))
    vi.stubGlobal('fetch', fetchMock)
    render(<TakeTranscript id="rec_1" />)
    await act(async () => { fireEvent.click(screen.getByText('Transcribe')) })
    expect(fetchMock).toHaveBeenCalledWith('/api/recordings/rec_1/transcribe', { method: 'POST' })
    expect(screen.getByText(/transcribing/)).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(fetchMock).toHaveBeenCalledWith('/api/jobs/job_9')
    expect(screen.getByText('captions (.srt)')).toBeTruthy()
  })

  it('says why when the server cannot transcribe', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply({ detail: 'whisper-cli not found' }, false)))
    render(<TakeTranscript id="rec_1" />)
    await act(async () => { fireEvent.click(screen.getByText('Transcribe')) })
    expect(screen.getByText(/whisper-cli not found/)).toBeTruthy()
    expect(screen.getByText('Transcribe')).toBeTruthy()
  })
})
