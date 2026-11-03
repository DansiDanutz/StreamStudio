import { useEffect, useState } from 'react'
import './channels.css'

type Summary = { slug: string; name: string; version: number; default: boolean }
type Profile = {
  slug: string; name: string; language: string; youtube_channel: string | null
  presenter: { name: string; avatar_id: string; voice_id: string; motion?: string | null }
  publish: { description_footer: string; default_tags: string[] }
  look?: Record<string, unknown> | null
  sound?: Record<string, unknown> | null
}
type Version = { version: number; profile: Profile }

async function request<T>(path = '', method = 'GET', body?: unknown): Promise<T> {
  const r = await fetch('/api/channels' + path, { method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) })
  const data = await r.json()
  if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  return data
}

function Field({ label, value, change }: { label: string; value: string; change: (s: string) => void }) {
  return <label>{label}<input value={value} onChange={e => change(e.target.value)} /></label>
}

export function ChannelsPage() {
  const [rows, setRows] = useState<Summary[]>([])
  const [version, setVersion] = useState<Version | null>(null)
  const [draft, setDraft] = useState<Profile | null>(null)
  const [media, setMedia] = useState('')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [role, setRole] = useState('image')
  const [uploaded, setUploaded] = useState('')

  function display(v: Version) {
    setVersion(v); setDraft(v.profile); setDirty(false); setUploaded('')
    setMedia(JSON.stringify({ look: v.profile.look ?? null, sound: v.profile.sound ?? null }, null, 2))
  }
  useEffect(() => {
    let active = true
    async function load() {
      const list = await request<Summary[]>()
      const selected = list.find(r => r.default) ?? list[0]
      const v = selected && await request<Version>('/' + selected.slug)
      if (active) { setRows(list); if (v) display(v) }
    }
    load().catch(e => { if (active) setMessage(e.message) })
    return () => { active = false }
  }, [])

  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage('')
    try { await action() } catch (e) { setMessage(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }
  function edit(change: Partial<Profile>) {
    if (draft) { setDraft({ ...draft, ...change }); setDirty(true) }
  }
  async function save() {
    if (!draft || !version) return
    const assets = JSON.parse(media)
    if (!assets || typeof assets !== 'object' || Array.isArray(assets) ||
        Object.keys(assets).some(k => k !== 'look' && k !== 'sound')) {
      throw new Error('Media settings must contain only look and sound.')
    }
    const v = await request<Version>('/' + draft.slug, 'PUT',
      { base_version: version.version, profile: { ...draft, look: assets.look ?? null, sound: assets.sound ?? null } })
    display(v); setRows(await request<Summary[]>()); setMessage('Saved version ' + v.version)
  }
  return <main className="channels-page">
    <header><a href="./">← Studio</a><h1>Channels</h1>
      <p>Choose the presenter, media, and publishing settings for new episodes. Approved episodes keep their saved version.</p></header>
    <p role="status" aria-live="polite">{message}</p>
    <fieldset disabled={busy}>
      <legend>Channel selection</legend>
      <label>Channel<select value={draft?.slug ?? ''} disabled={dirty || !draft}
        onChange={e => { const id = e.target.value; void run(async () => display(await request<Version>('/' + id))) }}>
        {rows.map(r => <option key={r.slug} value={r.slug}>{r.name}{r.default ? ' (default)' : ''}</option>)}
      </select></label>
      {draft && !rows.find(r => r.slug === draft.slug)?.default &&
        <button disabled={dirty} onClick={() => void run(async () => {
          await request('/default', 'PUT', { slug: draft.slug }); setRows(await request<Summary[]>())
        })}>Make default</button>}
    </fieldset>
    {draft && version && <fieldset disabled={busy}>
      <legend>{version.profile.name} · version {version.version}{dirty ? ' · unsaved' : ''}</legend>
      <Field label="Channel name" value={draft.name} change={name => edit({ name })} />
      <Field label="Caption language" value={draft.language} change={language => edit({ language })} />
      <Field label="YouTube channel ID" value={draft.youtube_channel ?? ''} change={v => edit({ youtube_channel: v || null })} />
      {(['name', 'avatar_id', 'voice_id', 'motion'] as const).map((key, i) =>
        <Field key={key} label={['Presenter name', 'Avatar ID', 'Voice ID', 'Presenter motion'][i]}
          value={draft.presenter[key] ?? ''} change={v => edit({ presenter: { ...draft.presenter, [key]: v } })} />)}
      <Field label="Description footer" value={draft.publish.description_footer}
        change={v => edit({ publish: { ...draft.publish, description_footer: v } })} />
      <label>Default tags (one per line)<textarea value={draft.publish.default_tags.join('\n')}
        onChange={e => edit({ publish: { ...draft.publish, default_tags: e.target.value.split('\n') } })} /></label>
      <details><summary>Visual and sound settings</summary>
        <p>Upload a file, then use its SHA-256 in the appropriate look or sound field.</p>
        <label>File type<select value={role} onChange={e => setRole(e.target.value)}>
          {['image', 'font', 'audio'].map(r => <option key={r}>{r}</option>)}</select></label>
        <label>Upload file<input type="file" onChange={e => {
          const f = e.target.files?.[0]; if (!f) return
          void run(async () => {
            const params = new URLSearchParams({ name: f.name, role })
            const r = await fetch('/api/channels/files?' + params, { method: 'PUT', body: f })
            const result = await r.json(); if (!r.ok) throw new Error(result.detail)
            setUploaded(result.sha256)
          })
        }} /></label>
        {uploaded && <label>Uploaded file SHA-256<input readOnly value={uploaded} onFocus={e => e.target.select()} /></label>}
        <label>Media settings (JSON)<textarea rows={12} value={media} onChange={e => { setMedia(e.target.value); setDirty(true) }} /></label>
      </details>
      <button disabled={!dirty} onClick={() => void run(save)}>Save new version</button>
      <button onClick={() => void run(async () => display(await request<Version>('/' + draft.slug)))}>Discard edits and reload</button>
    </fieldset>}
    <fieldset disabled={busy || dirty || !draft}>
      <legend>Create from selected channel</legend>
      <Field label="New channel name" value={name} change={setName} />
      <Field label="New channel slug" value={slug} change={setSlug} />
      <button disabled={!name.trim() || !slug.trim()} onClick={() => void run(async () => {
        const v = await request<Version>('', 'POST', { slug, name, from: draft?.slug })
        display(v); setName(''); setSlug(''); setRows(await request<Summary[]>())
      })}>Create channel</button>
    </fieldset>
  </main>
}
