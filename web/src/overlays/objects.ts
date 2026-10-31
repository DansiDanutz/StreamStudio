/** 3D objects on the table. Each object is a set of generated clips on pure black
 *  (`assets/objects/<id>/{arrive,idle,react}.mp4`) composited with a screen blend, so glow and
 *  reflections come through with no matte. Positions are fractions of the frame (desk scale). */

export type ObjectPhase = 'arrive' | 'idle' | 'react' | 'gone'

export interface ObjectDef {
  id: string
  name: string
  /** Centre of the object's footprint on the desk, fractions of the frame. */
  x: number
  y: number
  /** Object clip height as a fraction of the frame height. */
  scale: number
  /** Folder under /objects/. Falls back to the placeholder until the real clips exist. */
  dir?: string
}

// x = centre on the desk, y = the disc line (fractions of frame); `w` = rendered width of the cut-out.
export const OBJECTS: ObjectDef[] = [
  { id: 'claude-code', name: 'Claude Code', x: 0.15, y: 0.86, scale: 0.11 },
  { id: 'codex', name: 'Codex', x: 0.29, y: 0.86, scale: 0.11 },
  { id: 'cluster', name: 'Grok + GrokBot', x: 0.43, y: 0.86, scale: 0.11 },
  { id: 'hermes', name: 'Hermes', x: 0.57, y: 0.86, scale: 0.11 },
  { id: 'kimi', name: 'Kimi', x: 0.71, y: 0.86, scale: 0.11 },
  { id: 'glm', name: 'GLM', x: 0.85, y: 0.86, scale: 0.11 },
  { id: 'openclaw', name: 'OpenClaw', x: 0.5, y: 0.86, scale: 0.2 },
]
/** Hero spot: where an object arrives (big, centre) before it settles into its place. */
export const HERO = { x: 0.5, y: 0.88, scale: 0.2 }
export const objectStill = (o: ObjectDef) => `/objects/${o.dir ?? o.id}/cutout.png`

export const objectClip = (o: ObjectDef, phase: Exclude<ObjectPhase, 'gone'>) => `/objects/${o.dir ?? o.id}/${phase}.mp4`
export const PLACEHOLDER = (phase: Exclude<ObjectPhase, 'gone'>) => `/objects/_placeholder/${phase}.mp4`

/** Director events on the table, from a segment's `table` field:
 *  "arrive:claude" · "react:claude,codex" · "react:all" · "dim:all" · "clear" */
export type TableEvent = string
