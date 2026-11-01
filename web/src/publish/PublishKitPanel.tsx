import { useState } from 'react'
import type { PublishKit } from './kit'
import { YouTubeUpload } from './YouTubeUpload'

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.append(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

const fileStem = (title: string) => title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'video'

/** What to paste into YouTube Studio: title, description with chapters, and the captions file. */
export function PublishKitPanel({ kit, onClose }: { kit: PublishKit; onClose: () => void }) {
  const [copied, setCopied] = useState<string | null>(null)
  const copy = (what: string, text: string) => {
    navigator.clipboard.writeText(text).then(() => setCopied(what), () => setCopied(null))
  }
  const stem = fileStem(kit.title)
  return (
    <section className="kit" role="dialog" aria-label="Publish kit">
      <header className="kit-head">
        <b>Publish kit</b>
        <span>for YouTube Studio</span>
        <button onClick={onClose} aria-label="Close publish kit">✕</button>
      </header>
      {kit.notes.map((n) => <p key={n} className="kit-note">{n}</p>)}
      <label className="kit-field">
        <span>Title <button onClick={() => copy('title', kit.title)}>{copied === 'title' ? 'Copied' : 'Copy'}</button></span>
        <input readOnly value={kit.title} />
      </label>
      <label className="kit-field">
        <span>Description{kit.chapters.length ? ` · ${kit.chapters.length} chapters` : ''}
          <button onClick={() => copy('description', kit.description)}>{copied === 'description' ? 'Copied' : 'Copy'}</button>
          <button onClick={() => download(`${stem}-description.txt`, kit.description, 'text/plain')}>Download</button>
        </span>
        <textarea readOnly rows={8} value={kit.description} />
      </label>
      <label className="kit-field">
        <span>Captions (.srt)
          <button disabled={!kit.srt} onClick={() => download(`${stem}.srt`, kit.srt, 'application/x-subrip')}>Download .srt</button>
        </span>
        <textarea readOnly rows={8} value={kit.srt || 'No voiced lines yet.'} />
      </label>
      <YouTubeUpload title={kit.title} description={kit.description} />
    </section>
  )
}
