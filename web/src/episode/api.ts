/** The episode factory's API client: one function per route of `/api/episodes`, and the pure
 *  helpers the Episode page renders from. The server's `EpisodeOut` shape is the one source of
 *  truth; the page, the MCP tools and the tests all read it. */

export type EpisodeStatus =
  | 'draft' | 'script_approved' | 'budget_approved' | 'in_progress' | 'needs_dan'
  | 'ready' | 'uploaded_private' | 'scheduled' | 'published' | 'purged' | 'cancelled'

export interface SceneIn {
  id: string
  text?: string
  voice?: string
  kind?: 'avatar' | 'card'
  site?: string
  question?: number
  reveal?: boolean
  plan?: Record<string, unknown>
}

export interface Episode {
  id: string
  title: string
  status: EpisodeStatus
  script: { title: string; scenes: SceneIn[]; hash?: string; [k: string]: unknown }
  budget: { approved_at: string | null; clips: number; seconds: number; usd: number; allowance: { attempts: number; usd: number }; spent: { renders: number; seconds: number; usd: number } }
  scenes_state: Record<string, { take?: number; clip?: boolean; composed_hash?: string | null; qa?: string | null; qa_issues?: string[] }>
  outputs: { channel?: string; recording_id?: string; youtube_video_id?: string; publish_at?: string | null }
  log: { at: string; stage: string; message: string; scene?: string }[]
  progress: { clips: number; qa: number; composed: number; total: number }
  validation: { errors: Record<string, string[]>; warnings: Record<string, string[]> }
  next_action: string | null
  last_log: string | null
}

export interface Estimate {
  seconds: number
  usd: number
  clips: number
  with_motion: number
  ready: number
  allowance: { attempts: number; usd: number }
  ceiling_usd: number
  month_total_before_usd: number
  month_total_after_usd: number
  over_ceiling: boolean
  wallet_remaining_usd: number | null
  confirm_token: string
  expires_in_s: number
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api/episodes${path}`, {
    method,
    headers: body === undefined ? {} : { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) {
    let detail: unknown = r.statusText
    try { detail = (await r.json()).detail } catch { /* not JSON */ }
    throw new ApiError(r.status, typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return (await r.json()) as T
}

export const getEpisode = (id: string) => call<Episode>('GET', `/${id}`)
export const listEpisodes = () => call<{ id: string; title: string; status: EpisodeStatus; scenes: number }[]>('GET', '')
export const createEpisode = (script: Episode['script']) => call<Episode>('POST', '', script)
export const putScript = (id: string, script: Episode['script']) => call<Episode>('PUT', `/${id}/script`, script)
export const approveScript = (id: string) => call<Episode>('POST', `/${id}/approve-script`)
export const estimate = (id: string) => call<Estimate>('GET', `/${id}/estimate`)
export const approveBudget = (id: string, token: string) => call<Episode & { job_id: string }>('POST', `/${id}/approve-budget`, { confirm_token: token })
export const uploadPrivate = (id: string) => call<Episode>('POST', `/${id}/upload`, {})
export const refresh = (id: string) => call<Episode>('POST', `/${id}/refresh`)
export const publish = (id: string, publishAt?: string) => call<Episode>('POST', `/${id}/publish`, publishAt ? { publish_at: publishAt } : {})
export const advance = (id: string) => call<Episode & { job_id: string }>('POST', `/${id}/advance`)
export const purge = (id: string) => call<Episode & { job_id: string }>('POST', `/${id}/purge`)

/** The one line under the title: what the factory is doing, from counts, never stored. */
export function progressLabel(ep: Pick<Episode, 'status' | 'progress' | 'outputs'>): string {
  const p = ep.progress
  switch (ep.status) {
    case 'draft': return 'Draft: approve the script to start'
    case 'script_approved': return 'Script approved: approve the budget to render'
    case 'budget_approved': return 'Budget approved: starting'
    case 'in_progress':
      if (p.clips < p.total) return `Rendering ${p.clips}/${p.total}`
      if (p.composed < p.total) return `Composing ${p.composed}/${p.total}`
      return ep.outputs.recording_id ? 'Uploading' : 'Assembling'
    case 'needs_dan': return 'Needs you'
    case 'ready': return 'Ready in the Library'
    case 'uploaded_private': return 'Uploaded privately: publish when ready'
    case 'scheduled': return `Scheduled for ${ep.outputs.publish_at ?? '…'}`
    case 'published': return 'Published'
    case 'purged': return 'Published and purged'
    case 'cancelled': return 'Cancelled'
  }
}

/** Which of the three buttons is live for a status (the fourth is Advance for `needs_dan`). */
export function primaryAction(status: EpisodeStatus): 'approve-script' | 'approve-budget' | 'upload' | 'publish' | 'advance' | 'purge' | null {
  switch (status) {
    case 'draft': return 'approve-script'
    case 'script_approved': return 'approve-budget'
    case 'needs_dan': return 'advance'
    case 'ready': return 'upload'
    case 'uploaded_private': return 'publish'
    case 'published': case 'cancelled': return 'purge'
    default: return null
  }
}

export const usd = (n: number) => `${n.toFixed(2)} USD`
