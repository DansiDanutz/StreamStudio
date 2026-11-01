/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { Stage } from './Stage'
import { useStage } from './store'

// Every piece of editor UI inside the Base card must carry `editor-only`, so one rule hides it from
// the Program window and offline renders (both set `render-mode` on <html>).

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(new Proxy({}, { get: () => () => {} }) as never)
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
})

afterEach(cleanup)

function renderStage() {
  const s = useStage.getState()
  for (const kind of ['main', 'avatar', 'menu'] as const) {
    if (!s.active().layouts[s.orientation][kind].visible) s.toggleVisible(kind)
  }
  if (s.active().menuShown) s.toggleMenu()
  useStage.setState({ guides: true, mainSrc: null })
  const mediaId = s.addMedia({ label: 'clip', src: '/objects/clip.png', playback: 'once', framed: true, at: { x: 0.5, y: 0.5 } })
  return { ...render(<Stage />), mediaId }
}

function expectEditorOnly(container: HTMLElement, selectors: string[]) {
  for (const selector of selectors) {
    const found = [...container.querySelectorAll(selector)]
    expect(found.length, `${selector} should be on the stage in this setup`).toBeGreaterThan(0)
    for (const el of found) expect(el.closest('.editor-only'), `${selector} is not editor-only`).not.toBeNull()
  }
}

describe('clean output', () => {
  it('marks the stage guides, labels, ghost menu, avatar controls and empty Main card as editor-only', () => {
    const { container } = renderStage()
    expectEditorOnly(container, ['.base-label', '.safe', '.card-ghost', '.avatar-pick', '.lipsync', '.drop'])
  })

  it('marks a selected card’s handles, tag and point button as editor-only', () => {
    const { container } = renderStage()
    act(() => useStage.getState().select('main'))
    expectEditorOnly(container, ['.card-main .handle', '.card-tag', '.card-point'])
  })

  it('keeps the live source prompt in the output, so the Program window can reconnect a tab', () => {
    const { container } = renderStage()
    act(() => useStage.setState({ mainSrc: 'tab:' }))
    const ask = container.querySelector('.live-ask')
    expect(ask).not.toBeNull()
    expect(ask!.closest('.editor-only')).toBeNull()
  })

  it('marks a selected media card’s handles and toolbar as editor-only', () => {
    const { container, mediaId } = renderStage()
    act(() => useStage.getState().selectMedia(mediaId))
    expectEditorOnly(container, ['.mcard .handle', '.mcard-bar'])
  })

  it('marks the Main card source switcher as editor-only once a source is set', () => {
    const { container } = renderStage()
    act(() => useStage.setState({ mainSrc: '/studio/plate-landscape-final.png' }))
    expectEditorOnly(container, ['.source-x'])
  })

  it('hides editor-only UI and selection outlines in render mode', () => {
    const rules = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8').replace(/\s+/g, ' ')
    expect(rules).toMatch(/\.render-mode \.editor-only \{ display: none !important \}/)
    for (const outline of ['.render-mode .card.is-selected', '.render-mode .mcard.is-selected', '.render-mode .mcard.is-over', '.render-mode .base.is-drop']) {
      expect(rules).toContain(outline)
    }
  })
})
