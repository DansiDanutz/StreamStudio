import { describe, expect, it } from 'vitest'
import { primaryAction, progressLabel } from './api'

const base = { outputs: {}, progress: { clips: 0, qa: 0, composed: 0, total: 3 } }

describe('progressLabel', () => {
  it('counts what the factory is doing from the record, never a stored label', () => {
    expect(progressLabel({ ...base, status: 'in_progress', progress: { clips: 1, qa: 0, composed: 0, total: 3 } })).toBe('Rendering 1/3')
    expect(progressLabel({ ...base, status: 'in_progress', progress: { clips: 3, qa: 0, composed: 2, total: 3 } })).toBe('Composing 2/3')
    expect(progressLabel({ ...base, status: 'in_progress', progress: { clips: 3, qa: 0, composed: 3, total: 3 } })).toBe('Assembling')
    expect(progressLabel({ ...base, status: 'in_progress', outputs: { recording_id: 'rec_1-ep' }, progress: { clips: 3, qa: 0, composed: 3, total: 3 } })).toBe('Uploading')
    expect(progressLabel({ ...base, status: 'needs_dan' })).toBe('Needs you')
  })
})

describe('primaryAction', () => {
  it('offers exactly the click each gate needs', () => {
    expect(primaryAction('draft')).toBe('approve-script')
    expect(primaryAction('script_approved')).toBe('approve-budget')
    expect(primaryAction('in_progress')).toBeNull()
    expect(primaryAction('needs_dan')).toBe('advance')
    expect(primaryAction('uploaded_private')).toBe('publish')
    expect(primaryAction('published')).toBe('purge')
    expect(primaryAction('purged')).toBeNull()
  })
})
