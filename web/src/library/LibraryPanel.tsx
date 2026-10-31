import { useCallback, useEffect, useMemo, useState } from 'react'
import { buildCatalog, type Artifact } from '../agent/catalog'
import { EXECUTORS } from '../agent/bridge'
import { useStage, orderedScenes } from '../stage/store'
import { DRAG_MIME, DRAG_SRC_MIME, LIBRARY } from '../stage/Library'
import { VaultPanel } from './VaultPanel'
import {
  KIND_LABEL, NO_FILTERS, TABS, asItem, countBy, filterItems, fmtBytes, needsClip,
  type Filters, type LibItem, type Sort, type StatusFilter, type StoreFilter,
} from './groups'

const STORE_LABEL: Record<StoreFilter, string> = {
  any: 'Anywhere', local: 'On this Mac', vault: 'In the vault', 'vault-only': 'Vault only', 'not-backed-up': 'Not backed up',
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { 'content-type': 'application/json', ...init?.headers } })
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`)
  return r.json() as Promise<T>
}

/** The Library: every artifact in tabs (Scenes, Avatar, Media, Recordings, Workflows, Layouts),
 *  each with its own name, tags and where it is stored; search and filters to find it; ▶ runs its
 *  action here, ⧉ copies the call an agent makes; media drag onto the stage. ☁ Vault sets up the
 *  copy kept off this machine. Names, tags and storage need the Mac Studio server. */
export function LibraryPanel({ onAddFile }: { onAddFile: (f: File) => void }) {
  const scenes = useStage((s) => s.scenes)
  const media = useStage((s) => s.active().media?.[s.orientation])
  const [server, setServer] = useState<LibItem[] | null>(null)
  const [f, setF] = useState<Filters>(() => {
    try { return { ...NO_FILTERS, ...JSON.parse(localStorage.getItem('streamstudio.library.filters') ?? '{}'), q: '' } } catch { return NO_FILTERS }
  })
  const [vault, setVault] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)

  const load = useCallback(() => {
    api<{ artifacts: LibItem[] }>('/api/library').then((r) => setServer(r.artifacts.map(asItem)), () => setServer(null))
  }, [])
  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    window.addEventListener('streamstudio:library', load) // the editor just published its catalog
    return () => { clearInterval(t); window.removeEventListener('streamstudio:library', load) }
  }, [load])
  useEffect(() => {
    try { localStorage.setItem('streamstudio.library.filters', JSON.stringify({ ...f, q: '' })) } catch { /* private window */ }
  }, [f])

  const all = useMemo<LibItem[]>(() => {
    const live: Artifact[] = (media ?? []).map((m) => ({
      id: `media:${m.id}`, kind: 'stage-media', name: m.label, description: 'A media card on the current scene.', preview: m.poster,
      actions: [{ action: 'point.at', args: { target: `media:${m.id}` } }, { action: 'media.remove', args: { id: m.id } }],
    }))
    const sc: Artifact[] = orderedScenes(scenes).map((s) => ({
      id: `scene:${s.id}`, kind: 'scene', name: s.name, description: `Scene in ${s.collection ?? 'Talk'}.`,
      actions: [{ action: 'scene.activate', args: { id: s.id } }],
    }))
    const local = [...sc, ...live, ...buildCatalog().artifacts].map(asItem)
    if (!server) return local
    // the server's copy carries names, tags and storage; the editor's fills anything it lacks
    const have = new Set(server.map((a) => a.id))
    return [...live.map(asItem), ...server, ...local.filter((a) => a.kind !== 'stage-media' && !have.has(a.id))]
  }, [server, scenes, media])

  const set = (p: Partial<Filters>) => setF((x) => ({ ...x, ...p }))
  const inTab = all.filter((a) => f.tab === 'All' || a.group === f.tab)
  const kinds = countBy(inTab, (a) => a.kind)
  const tabs = countBy(all, (a) => a.group)
  const tags = Array.from(new Set(all.flatMap((a) => a.tags))).sort()
  const shown = filterItems(all, f)
  const filtered = f.kind !== 'all' || f.status !== 'any' || f.store !== 'any' || !!f.tag || !!f.q

  const run = (action: string, args: Record<string, unknown>) => {
    const ex = EXECUTORS[action]
    if (!ex) { setNote(`${action}: use it from the Script tab`); return }
    try {
      const r = ex(args)
      setNote(`${action} ✓ ${r && Object.keys(r as object).length ? JSON.stringify(r) : ''}`)
    } catch (e) { setNote(`${action}: ${(e as Error).message}`) }
  }
  const copy = (action: string, args: Record<string, unknown>) => {
    const call = JSON.stringify({ tool: 'studio_do', arguments: { action, args } })
    void navigator.clipboard?.writeText(call).then(() => setNote('Agent call copied'), () => setNote(call))
  }
  const patch = (a: LibItem, body: { title?: string; tags?: string[] }) =>
    api<LibItem>(`/api/library/${encodeURIComponent(a.id)}`, { method: 'PATCH', body: JSON.stringify(body) })
      .then(() => { setNote(`Saved ${body.title ? `“${body.title}”` : 'tags'}`); load() }, (e: Error) => setNote(e.message))
  const store = (a: LibItem, what: 'fetch' | 'evict') =>
    api<{ freed_bytes?: number }>(`/api/vault/${what}`, { method: 'POST', body: JSON.stringify({ key: a.storage!.key }) })
      .then((r) => { setNote(what === 'fetch' ? `${a.name} is back on this Mac` : `Freed ${fmtBytes(r.freed_bytes)}; it comes back when used`); load() },
        (e: Error) => setNote(e.message))

  const dragFor = (a: LibItem): ((e: React.DragEvent) => void) | undefined => {
    const libId = a.kind === 'object' || a.kind === 'media' ? a.id.split(':')[1] : null
    if (libId && LIBRARY.some((x) => x.id === libId)) return (e) => { e.dataTransfer.setData(DRAG_MIME, libId); e.dataTransfer.effectAllowed = 'copy' }
    if ((a.kind === 'clip' || a.kind === 'recording') && a.url) return (e) => { e.dataTransfer.setData(DRAG_SRC_MIME, JSON.stringify({ label: a.name, src: a.url })); e.dataTransfer.effectAllowed = 'copy' }
    return undefined
  }

  if (vault) return <VaultPanel onClose={() => { setVault(false); load() }} />

  return (
    <div className="lib2">
      <div className="lib-head">
        <div className="lib-top">
          <div className="lbl">Library · {all.length}</div>
          <button className="lib-vault" onClick={() => setVault(true)} disabled={!server}
            title={server ? 'Where copies are kept off this Mac' : 'Needs the Mac Studio server'}>☁ Vault</button>
        </div>
        <input className="art-search" type="search" placeholder="Search names, ids, tags…" value={f.q} onChange={(e) => set({ q: e.target.value })} />
        <div className="lib-tabs" role="tablist">
          {TABS.map((t) => (tabs[t] || t === 'All') && (
            <button key={t} role="tab" aria-selected={f.tab === t} className={f.tab === t ? 'on' : ''} onClick={() => set({ tab: t, kind: 'all' })}>
              {t} <span>{t === 'All' ? all.length : tabs[t]}</span>
            </button>
          ))}
        </div>
        <div className="lib-filters">
          <select value={f.kind} onChange={(e) => set({ kind: e.target.value })} aria-label="Kind">
            <option value="all">All kinds</option>
            {Object.entries(kinds).map(([k, n]) => <option key={k} value={k}>{KIND_LABEL[k] ?? k} ({n})</option>)}
          </select>
          <select value={f.status} onChange={(e) => set({ status: e.target.value as StatusFilter })} aria-label="Status">
            <option value="any">Any status</option><option value="ready">Ready</option><option value="needs-clip">Needs a clip</option>
          </select>
          <select value={f.store} onChange={(e) => set({ store: e.target.value as StoreFilter })} aria-label="Stored" disabled={!server}>
            {(Object.keys(STORE_LABEL) as StoreFilter[]).map((k) => <option key={k} value={k}>{STORE_LABEL[k]}</option>)}
          </select>
          {tags.length > 0 && (
            <select value={f.tag} onChange={(e) => set({ tag: e.target.value })} aria-label="Tag">
              <option value="">Any tag</option>{tags.map((t) => <option key={t} value={t}>#{t}</option>)}
            </select>
          )}
          <select value={f.sort} onChange={(e) => set({ sort: e.target.value as Sort })} aria-label="Sort">
            <option value="group">By tab</option><option value="name">A–Z</option><option value="newest">Newest</option>
          </select>
          {filtered && <button onClick={() => setF({ ...NO_FILTERS, tab: f.tab })}>Clear</button>}
        </div>
        {note && <div className="art-note">{note}</div>}
      </div>
      <ul className="art-list">
        {f.tab === 'Media' && (
          <li className="lib-upload-row">
            <label title="Add your own video or image as a card">
              <span className="plus">+</span> Video or image from this computer
              <input type="file" accept="video/*,image/*" hidden onChange={(e) => { const x = e.target.files?.[0]; if (x) onAddFile(x) }} />
            </label>
          </li>
        )}
        {shown.map((a) => {
          const drag = dragFor(a)
          return (
            <li key={a.id} draggable={!!drag} onDragStart={drag} className={drag ? 'can-drag' : ''} title={drag ? 'Drag onto the stage' : undefined}>
              {a.preview ? <img src={a.preview} alt="" draggable={false} /> : <i className={`art-ico k-${a.kind}`} />}
              <div className="art-body">
                {editing === a.id ? (
                  <form className="art-rename" onSubmit={(e) => {
                    e.preventDefault()
                    const fd = new FormData(e.currentTarget)
                    const tagsIn = String(fd.get('tags') ?? '').split(/[,\s]+/).map((t) => t.replace(/^#/, '')).filter(Boolean)
                    void patch(a, { title: String(fd.get('title') ?? ''), tags: tagsIn })
                    setEditing(null)
                  }}>
                    <input name="title" defaultValue={a.name} placeholder={a.default_name ?? a.name} autoFocus maxLength={120} />
                    <input name="tags" defaultValue={a.tags.map((t) => `#${t}`).join(' ')} placeholder="#tags" />
                    <button type="submit">Save</button><button type="button" onClick={() => setEditing(null)}>Cancel</button>
                  </form>
                ) : (
                  <div className="art-name">
                    {a.name}
                    {server && <button className="art-edit" title="Rename and tag" onClick={() => setEditing(a.id)}>✎</button>}
                    <code>{a.id}</code>
                  </div>
                )}
                <div className="art-meta">
                  <span className="art-kind">{KIND_LABEL[a.kind] ?? a.kind}</span>
                  {needsClip(a) && <span className="art-warn">needs a clip</span>}
                  {a.storage && <span className={`art-store ${a.storage.local ? 'on' : ''}`} title={a.storage.local ? 'On this Mac' : 'Not on this Mac'}>💻</span>}
                  {a.storage && <span className={`art-store ${a.storage.vault ? 'on' : ''}`} title={a.storage.vault ? 'Copy in the vault' : 'Not backed up yet'}>☁</span>}
                  {a.bytes ? <span>{fmtBytes(a.bytes)}</span> : null}
                  {a.tags.map((t) => <button key={t} className="art-tag" onClick={() => set({ tag: t })}>#{t}</button>)}
                </div>
                <div className="art-desc">{a.description}</div>
                <div className="art-actions">
                  {a.actions.map((x, i) => (
                    <span key={i} className="art-act">
                      <button title={`Run ${x.action} here`} onClick={() => run(x.action, x.args)}>▶ {x.action}{x.action === 'table.event' ? ` ${String(x.args.event)}` : ''}</button>
                      <button title="Copy the agent call" onClick={() => copy(x.action, x.args)}>⧉</button>
                    </span>
                  ))}
                  {a.kind === 'recording' && a.url && <a className="art-btn" href={a.url} download>⬇ MP4</a>}
                  {a.storage?.vault && !a.storage.local && <button onClick={() => store(a, 'fetch')} title="Download it to this Mac now">⤓ Bring back</button>}
                  {a.storage?.vault && a.storage.local && (a.kind === 'recording' || a.kind === 'clip') &&
                    <button onClick={() => store(a, 'evict')} title="Remove the local copy; the vault keeps it and it comes back when used">Free space</button>}
                </div>
              </div>
            </li>
          )
        })}
        {!shown.length && <li className="art-empty">Nothing matches.{filtered && <> <button onClick={() => setF({ ...NO_FILTERS, tab: f.tab })}>Clear filters</button></>}</li>}
      </ul>
    </div>
  )
}
