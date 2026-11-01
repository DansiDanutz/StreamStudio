import { describe, expect, it } from 'vitest'
import { staleServerWarning } from './health'

describe('staleServerWarning', () => {
  it('warns when the server runs older code than the checkout', () => {
    expect(staleServerWarning({ rev: 'a'.repeat(40), head: 'b'.repeat(40), stale: true })).toMatch(/restart/i)
  })

  it('warns when the server is too old to report its revision', () => {
    expect(staleServerWarning({ ok: true, version: '0.1.0' })).toMatch(/restart/i)
  })

  it('stays quiet when the server is current', () => {
    expect(staleServerWarning({ rev: 'a'.repeat(40), head: 'a'.repeat(40), stale: false })).toBeNull()
  })

  it('stays quiet when git is unavailable on the server', () => {
    expect(staleServerWarning({ rev: null, head: null, stale: false })).toBeNull()
  })
})
