/// <reference types="node" />
import { readdirSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// macOS file systems ignore case, so './director/Timeline' and './director/timeline' resolve to whichever
// file wins: the app then fails to load on the Mac Studio. Import paths must differ by more than case.
const SRC = resolve(process.cwd(), 'src')

function modulePaths(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return modulePaths(path)
    return /\.(tsx?|jsx?)$/.test(entry.name) ? [relative(SRC, path).replace(/\.(tsx?|jsx?)$/, '')] : []
  })
}

describe('source file names', () => {
  it('has no two import paths that differ only in case', () => {
    const byLower = new Map<string, Set<string>>()
    for (const path of modulePaths(SRC)) {
      const key = path.toLowerCase()
      byLower.set(key, new Set([...(byLower.get(key) ?? []), path]))
    }
    const clashes = [...byLower.values()].filter((paths) => paths.size > 1).map((paths) => [...paths].join(' vs '))
    expect(clashes).toEqual([])
  })
})
