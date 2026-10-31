import { useEffect, useState } from 'react'
import { fmtBytes } from './groups'

interface Status {
  configured: boolean
  config: Record<string, string>
  local_files: number
  in_vault: number
  not_backed_up: number
  vault_only: number
  bytes_in_vault: number
  last_push: { status: string; progress?: number; message?: string; error?: string } | null
}

const FOLDERS = [
  { label: 'iCloud Drive', path: '~/Library/Mobile Documents/com~apple~CloudDocs/StreamStudio' },
  { label: 'Google Drive', path: '~/Library/CloudStorage/GoogleDrive-<you@gmail.com>/My Drive/StreamStudio' },
  { label: 'Dropbox', path: '~/Library/CloudStorage/Dropbox/StreamStudio' },
]
const S3_HINTS = [
  { label: 'Supabase Storage', endpoint: 'https://<project-ref>.supabase.co/storage/v1/s3', region: '<project region, e.g. eu-central-1>' },
  { label: 'Cloudflare R2', endpoint: 'https://<account-id>.r2.cloudflarestorage.com', region: 'auto' },
  { label: 'Backblaze B2', endpoint: 'https://s3.<region>.backblazeb2.com', region: '<region>' },
]

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { 'content-type': 'application/json' } })
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`)
  return r.json() as Promise<T>
}

/** Where copies of the library live off this Mac: an S3-compatible bucket or a synced folder.
 *  Keys are typed here by Dan, sent once to the local server, and only ever shown masked. */
export function VaultPanel({ onClose }: { onClose: () => void }) {
  const [st, setSt] = useState<Status | null>(null)
  const [kind, setKind] = useState<'s3' | 'folder' | 'off'>('folder')
  const [form, setForm] = useState<Record<string, string>>({ prefix: 'streamstudio' })
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = () => call<Status>('/api/vault').then((s) => {
    setSt(s)
    return s
  }, (e: Error) => { setMsg(e.message); return null })
  useEffect(() => {
    void refresh().then((s) => {
      if (!s?.configured) return
      setKind(s.config.kind as 's3' | 'folder')
      setForm({ ...s.config, access_key: '', secret_key: '' })
    })
  }, [])
  useEffect(() => {
    if (st?.last_push && ['queued', 'running'].includes(st.last_push.status)) {
      const t = setTimeout(refresh, 1500)
      return () => clearTimeout(t)
    }
  }, [st])

  const field = (k: string, label: string, ph = '', type = 'text') => (
    <label className="v-field"><span>{label}</span>
      <input type={type} value={form[k] ?? ''} placeholder={ph} autoComplete="off" spellCheck={false}
        onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))} />
    </label>
  )
  const save = async () => {
    setBusy(true); setMsg(null)
    try {
      const s = await call<Status>('/api/vault', { method: 'PUT', body: JSON.stringify({ kind, ...form }) })
      setSt(s); setForm((f) => ({ ...f, access_key: '', secret_key: '' }))
      setMsg(kind === 'off' ? 'Vault turned off. Nothing was deleted.' : 'Connected. New clips and takes are backed up automatically.')
    } catch (e) { setMsg((e as Error).message) } finally { setBusy(false) }
  }
  const act = async (path: string, done: (r: Record<string, number>) => string) => {
    setBusy(true); setMsg(null)
    try { setMsg(done(await call(path, { method: 'POST' }))); await refresh() } catch (e) { setMsg((e as Error).message) } finally { setBusy(false) }
  }
  const lp = st?.last_push

  return (
    <div className="vault">
      <div className="lib-head">
        <div className="lib-top"><div className="lbl">☁ Vault</div><button onClick={onClose}>← Library</button></div>
        <p>A copy of every clip, take, scene and name, kept off this Mac. Anything removed here comes back by itself the first time it is used.</p>
      </div>
      <div className="vault-body">
        {st?.configured && (
          <div className="v-stats">
            <div><b>{st.in_vault}</b><span>in the vault · {fmtBytes(st.bytes_in_vault)}</span></div>
            <div><b>{st.not_backed_up}</b><span>not backed up</span></div>
            <div><b>{st.vault_only}</b><span>only in the vault</span></div>
            <div className="v-where">{st.config.kind === 's3' ? `${st.config.endpoint} · ${st.config.bucket}` : st.config.path}</div>
            <div className="v-row">
              <button disabled={busy} onClick={() => act('/api/vault/push', () => 'Backing up…')}>Back up now</button>
              <button disabled={busy} onClick={() => act('/api/vault/sync', (r) => `Read the vault: ${r.files_in_vault} files, ${r.scenes} scenes and ${r.names} names restored`)}
                title="On a new machine, or after another machine added things">Sync from vault</button>
            </div>
            {lp && <div className={`v-job ${lp.status}`}>Last backup: {lp.status}{lp.message && lp.status === 'running' ? ` · ${lp.message}` : ''}{lp.error ? ` · ${lp.error}` : ''}</div>}
          </div>
        )}
        <div className="v-kinds" role="radiogroup">
          {(['folder', 's3', 'off'] as const).map((k) => (
            <button key={k} role="radio" aria-checked={kind === k} className={kind === k ? 'on' : ''} onClick={() => setKind(k)}>
              {k === 'folder' ? 'Synced folder' : k === 's3' ? 'Cloud bucket (S3)' : 'Off'}
            </button>
          ))}
        </div>
        {kind === 'folder' && (
          <>
            <p className="v-help">A folder that a cloud service copies off this Mac. The server must be able to write to it.</p>
            {field('path', 'Folder', FOLDERS[0].path)}
            <div className="v-row">{FOLDERS.map((x) => <button key={x.label} onClick={() => setForm((f) => ({ ...f, path: x.path }))}>{x.label}</button>)}</div>
          </>
        )}
        {kind === 's3' && (
          <>
            <p className="v-help">Any S3-compatible bucket. Make the bucket private; create an access key that can read and write it.</p>
            <div className="v-row">{S3_HINTS.map((x) => <button key={x.label} onClick={() => setForm((f) => ({ ...f, endpoint: x.endpoint, region: x.region }))}>{x.label}</button>)}</div>
            {field('endpoint', 'Endpoint', 'https://…')}
            {field('region', 'Region', 'auto')}
            {field('bucket', 'Bucket', 'streamstudio')}
            {field('access_key', 'Access key id', st?.config.access_key || '', 'password')}
            {field('secret_key', 'Secret access key', st?.config.secret_key ? `${st.config.secret_key} (blank keeps it)` : '', 'password')}
          </>
        )}
        {kind !== 'off' && field('prefix', 'Folder inside the vault', 'streamstudio')}
        <div className="v-row"><button className="primary" disabled={busy} onClick={save}>{kind === 'off' ? 'Turn off' : 'Save and test'}</button></div>
        {msg && <div className="art-note">{msg}</div>}
      </div>
    </div>
  )
}
