import { useState } from 'react'
import { putScript, type Episode, type SceneIn } from './api'

type Props = { episode: Episode; scene: SceneIn; saved: (episode: Episode) => void }

export function SceneEditor({ episode, scene, saved }: Props) {
  const [original] = useState(episode.script)
  const [text, setText] = useState(scene.text ?? '')
  const [voice, setVoice] = useState(scene.voice ?? '')
  const [site, setSite] = useState(scene.site ?? '')
  const [sources, setSources] = useState(JSON.stringify(scene.sources ?? [], null, 2))
  const [direction, setDirection] = useState(JSON.stringify(scene.plan ?? null, null, 2))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true); setError('')
    try {
      const updated = { ...scene, text, voice, site: site.trim() || undefined, sources: JSON.parse(sources), plan: JSON.parse(direction) }
      const result = await putScript(episode.id, {
        ...original, scenes: original.scenes.map(s => s.id === scene.id ? updated : s),
      })
      saved(result)
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }
  return <fieldset className="scene-editor" disabled={busy}>
    <legend>Edit {scene.id}</legend>
    <label>On-screen text<textarea value={text} onChange={e => setText(e.target.value)} /></label>
    <label>Dan’s spoken line<textarea value={voice} onChange={e => setVoice(e.target.value)} /></label>
    {scene.kind === 'card' && <label>Website URL<input type="url" value={site}
      onChange={e => setSite(e.target.value)} /></label>}
    <label>Sources (JSON)<textarea value={sources} onChange={e => setSources(e.target.value)} /></label>
    <label>Scene direction (JSON)<textarea rows={6} value={direction} onChange={e => setDirection(e.target.value)} /></label>
    <p>Saving returns the episode to draft for review.</p>
    <button onClick={() => void save()}>Save scene</button>
    {error && <p role="alert">{error}</p>}
  </fieldset>
}
