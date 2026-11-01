/** /api/health reports the revision the server started with (`rev`) and the checkout on disk
 *  (`head`). After a pull they differ: the server is still running the old code, and routes the
 *  editor needs may be missing, so tell Dan to restart instead of failing in odd ways. */
export function staleServerWarning(health: Record<string, unknown>): string | null {
  if (!('rev' in health)) return 'The StreamStudio server is running an old build. Restart StreamStudio (reopen the Mac app) to load the latest.'
  if (health.stale === true) return 'The StreamStudio server is running older code than this checkout. Restart StreamStudio (reopen the Mac app) to load the latest.'
  return null
}
