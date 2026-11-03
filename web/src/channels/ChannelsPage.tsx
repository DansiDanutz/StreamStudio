import { useEffect, useState } from 'react'
import './channels.css'

type Summary = { slug: string; name: string; version: number; default: boolean }
type Profile = {
  slug: string; name: string; language: string; youtube_channel: string | null
  presenter: { name: string; avatar_id: string; voice_id: string; motion?: string | null }
  publish: { description_footer: string; default_tags: string[] }
  intro?: { kicker?: string; title?: string; title_em?: string; tagline?: string; logo_letter?: string; fonts?: Record<string, string>; colours?: Record<string, string> }
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
  const [captureSite, setCaptureSite] = useState('')
  const [captureFile, setCaptureFile] = useState<File | null>(null)
  const [capturePlan, setCapturePlan] = useState('')
  const [role, setRole] = useState('image')
  const [preview, setPreview] = useState<{url: string; cached: boolean} | null>(null)
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url) }, [preview])
  const [uploaded, setUploaded] = useState('')

  function display(v: Version) {
    setPreview(null); setVersion(v); setDraft(v.profile); setDirty(false); setUploaded('')
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
    if (draft) { setPreview(null); setDraft({ ...draft, ...change }); setDirty(true) }
  }
  function draftProfile() {
    if (!draft) throw new Error('Select a channel first.')
    const assets = JSON.parse(media)
    if (!assets || typeof assets !== 'object' || Array.isArray(assets) ||
        Object.keys(assets).some(k => k !== 'look' && k !== 'sound')) {
      throw new Error('Media settings must contain only look and sound.')
    }
    return { ...draft, look: assets.look ?? null, sound: assets.sound ?? null }
  }
  async function previewDraft() {
    const r = await fetch('/api/channels/preview', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draftProfile()) })
    if (!r.ok) {
      const { detail } = await r.json()
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
    setPreview({ url: URL.createObjectURL(await r.blob()), cached: r.headers.get('X-Presenter-Preview') === 'cached' })
  }
  async function save() {
    if (!draft || !version) return
    const v = await request<Version>('/' + draft.slug, 'PUT',
      { base_version: version.version, profile: draftProfile() })
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
      <details><summary>Animated intro</summary>
        {(['kicker', 'title', 'title_em', 'tagline', 'logo_letter'] as const).map((key, i) =>
          <Field key={key} label={['Intro kicker', 'Intro title', 'Emphasized title', 'Intro tagline', 'Logo letter'][i]}
            value={draft.intro?.[key] ?? ''} change={v => edit({ intro: { ...draft.intro, [key]: v } })} />)}
        {(['serif', 'serif_bold', 'serif_italic', 'mono'] as const).map(slot =>
          <label key={slot}>Intro font · {slot}
            <input type="file" accept=".ttf,.otf,.woff2" onChange={e => {
              const file = e.target.files?.[0]; if (!file) return
              void run(async () => {
                const query = new URLSearchParams({name: file.name, role: 'intro_font'})
                const response = await fetch('/api/channels/files?' + query, {method: 'PUT', body: file})
                const result = await response.json()
                if (!response.ok) throw new Error(result.detail)
                edit({ intro: { ...draft.intro, fonts: { ...draft.intro?.fonts, [slot]: result.sha256 } } })
              })
            }} />
            {draft.intro?.fonts?.[slot] && <button onClick={() => {
              const fonts = { ...draft.intro?.fonts }; delete fonts[slot]
              edit({ intro: { ...draft.intro, fonts } })
            }}>Use default for {slot}</button>}
          </label>)}
        {Object.entries(draft.intro?.colours ?? {}).map(([key, colour]) =>
          <Field key={key} label={`Intro color · ${key}`} value={colour}
            change={v => edit({ intro: { ...draft.intro, colours: { ...draft.intro?.colours, [key]: v } } })} />)}
        <button disabled={dirty} onClick={() => void run(async () => {
          const job = await request<{job_id: string}>('/' + draft.slug + '/intro', 'POST')
          setMessage('Rendering intro locally…')
          for (;;) {
            await new Promise(resolve => setTimeout(resolve, 1500))
            const response = await fetch('/api/jobs/' + job.job_id)
            if (!response.ok) throw new Error('Could not read intro job status.')
            const state = await response.json()
            if (state.status === 'error' || state.status === 'cancelled') throw new Error(state.error || state.status)
            if (state.status === 'done') {
              display(await request<Version>('/' + draft.slug)); setRows(await request<Summary[]>())
              setMessage(state.result?.discarded ? 'Channel changed during rendering. Render again with the latest version.' : 'Generated intro saved to the channel.')
              break
            }
          }
        })}>Generate intro from saved version</button>
        {typeof draft.sound?.intro === 'string' && <video controls preload="none" style={{width: '100%'}}
          aria-label="Channel intro" src={'/api/channels/files/' + draft.sound.intro} />}
      </details>
      <details><summary>Visual and sound settings</summary>
        <p>Upload a file, then use its SHA-256 in the appropriate look or sound field.</p>
        <label>File type<select value={role} onChange={e => setRole(e.target.value)}>
          {['image', 'font', 'audio', 'intro'].map(r => <option key={r}>{r}</option>)}</select></label>
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
        <label>Media settings (JSON)<textarea rows={12} value={media} onChange={e => { setPreview(null); setMedia(e.target.value); setDirty(true) }} /></label>
      </details>
      <button onClick={() => void run(previewDraft)}>Preview draft look</button>
      {preview && <figure><img width="1920" height="540" style={{width: '100%', height: 'auto'}}
        src={preview.url} alt="Draft presenter layout and sample card side by side" />
        <figcaption>{preview.cached ? 'Cached presenter frame' : 'Silhouette · no matching presenter frame available'}</figcaption></figure>}
      <button disabled={!dirty} onClick={() => void run(save)}>Save new version</button>
      <button onClick={() => void run(async () => display(await request<Version>('/' + draft.slug)))}>Discard edits and reload</button>
      {!rows.find(r => r.slug === draft.slug)?.default && <button disabled={dirty}
        onClick={() => {
          if (!window.confirm(`Remove all versions of ${draft.name}? Uploaded files will be kept.`)) return
          void run(async () => {
            await request('/' + draft.slug + '?base_version=' + version.version, 'DELETE')
            const list = await request<Summary[]>()
            setRows(list)
            const selected = list.find(r => r.default)!
            display(await request<Version>('/' + selected.slug))
            setMessage('Channel removed.')
          })
        }}>Remove channel</button>}
    </fieldset>}
    <fieldset disabled={busy}><legend>Manual website capture</legend>
      <p>For an allowed manual site, take a screenshot in your signed-in browser. The worker uses the image locally.</p>
      <Field label="Exact page URL" value={captureSite} change={v => { setCaptureSite(v); setCapturePlan('') }} />
      <label>Screenshot<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => {
        setCaptureFile(e.target.files?.[0] ?? null); setCapturePlan('')
      }} /></label>
      <button disabled={!captureFile || !captureSite} onClick={() => void run(async () => {
        const query = new URLSearchParams({url: captureSite})
        const response = await fetch('/api/episodes/captures/manual?' + query, { method: 'PUT', body: captureFile })
        const data = await response.json()
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
        setCapturePlan(JSON.stringify({site: data.site, plan: {website_demo: {
          focus_label: 'Screenshot detail', manual: data.manual }}}, null, 2))
      })}>Prepare capture for a scene</button>
      {capturePlan && <label>Scene fields · focal coordinates range from 0 to 1
        <textarea rows={10} value={capturePlan} readOnly onFocus={e => e.target.select()} />
      </label>}
    </fieldset>
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
