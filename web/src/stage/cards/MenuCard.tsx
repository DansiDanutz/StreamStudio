import { PRESETS } from '../presets'
import { useStage } from '../store'
import { useDirector } from '../../director/store'
import type { Cue } from '../../director/types'

/** Menu card: controls the stage. Transparent in the output by default (ghost outline in the editor);
 *  when `menuShown` is on it is drawn into the output with the glass skin. */
export function MenuCard() {
  const scene = useStage((s) => s.active())
  const orientation = useStage((s) => s.orientation)
  const { setOrientation, loadPreset, toggleMenu, toggleVisible } = useStage.getState()
  const avatarVisible = useStage((s) => s.active().layouts[s.orientation].avatar.visible)
  const stop = (e: React.SyntheticEvent) => e.stopPropagation()
  const cue = useDirector((s) => s.cue)
  const applyCue = useDirector((s) => s.applyCue)

  return (
    <div className={`menu ${scene.menuShown ? 'menu-on' : 'menu-ghost'}`} onPointerDown={stop}>
      <div className="lbl">Cue</div>
      <div className="segs">
        {(['avatar', 'duo', 'split', 'content', 'full'] as Cue[]).map((c) => (
          <button key={c} className={cue === c ? 'on' : ''} onClick={() => applyCue(c)}>{c}</button>
        ))}
      </div>
      <div className="lbl">Scene</div>
      <div className="segs">
        {PRESETS.map((p) => (
          <button key={p.id} className={p.layouts === scene.layouts || p.name === scene.name ? 'on' : ''} onClick={() => loadPreset(p.id)}>{p.name.split(' ')[0]}</button>
        ))}
      </div>
      <div className="lbl">Orientation</div>
      <div className="segs two">
        <button className={orientation === 'landscape' ? 'on' : ''} onClick={() => setOrientation('landscape')}>16:9</button>
        <button className={orientation === 'portrait' ? 'on' : ''} onClick={() => setOrientation('portrait')}>9:16</button>
      </div>
      <div className="lbl">Avatar</div>
      <div className="segs two">
        <button className={avatarVisible ? 'on' : ''} onClick={() => toggleVisible('avatar')}>{avatarVisible ? 'Shown' : 'Hidden'}</button>
        <button onClick={toggleMenu}>{scene.menuShown ? 'Hide menu' : 'Show menu'}</button>
      </div>
      <div className="rec" title="Recording and live arrive in S6">REC 00:00<span>LIVE</span></div>
    </div>
  )
}
