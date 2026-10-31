import { useState } from 'react'
import { WORKFLOWS, workflowDefaults, type Workflow } from './workflows'
import { useDirector } from './store'
import { useStage } from '../stage/store'

/** Pick a workflow, fill its blanks, and drop the segments into the script. */
export function WorkflowPicker({ onDone }: { onDone: () => void }) {
  const [w, setW] = useState<Workflow | null>(null)
  const [vals, setVals] = useState<Record<string, string>>({})
  const insert = (mode: 'replace' | 'append') => {
    if (!w) return
    w.scenes.forEach((id) => useStage.getState().ensureTemplate(id))
    useDirector.getState().insertSegments(w.build({ ...workflowDefaults(w), ...vals }), mode, w.name)
    onDone()
  }
  if (!w) {
    return (
      <div className="wf">
        <div className="lbl">Workflows</div>
        <p className="wf-hint">Ready-made shapes for a script. Pick one, fill the blanks, edit anything after.</p>
        <ul className="wf-list">
          {WORKFLOWS.map((x) => (
            <li key={x.id}><button onClick={() => { setW(x); setVals(workflowDefaults(x)) }}><b>{x.name}</b><span>{x.summary}</span></button></li>
          ))}
        </ul>
        <button onClick={onDone}>Back to the script</button>
      </div>
    )
  }
  return (
    <div className="wf">
      <div className="lbl">Workflow</div>
      <div className="wf-title">{w.name}</div>
      <p className="wf-hint">{w.summary}</p>
      {w.fields.map((f) => (
        <label key={f.key} className="wf-field">
          <span>{f.label}</span>
          {f.options
            ? <select value={vals[f.key]} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}>{f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
            : f.lines
              ? <textarea rows={4} value={vals[f.key]} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} spellCheck={false} />
              : <input value={vals[f.key]} placeholder={f.placeholder} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} />}
        </label>
      ))}
      <div className="wf-actions">
        <button onClick={() => setW(null)}>← All workflows</button>
        <button onClick={() => insert('append')}>Add to the end</button>
        <button className="primary" onClick={() => insert('replace')}>Replace the script</button>
      </div>
    </div>
  )
}
