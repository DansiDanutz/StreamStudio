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

export const OBJECTS: ObjectDef[] = [
  { id: 'claude', name: 'Claude', x: 0.18, y: 0.8, scale: 0.26 },
  { id: 'codex', name: 'Codex', x: 0.31, y: 0.78, scale: 0.25 },
  { id: 'grok', name: 'Grok + GrokBot', x: 0.44, y: 0.77, scale: 0.25 },
  { id: 'hermes', name: 'Hermes', x: 0.56, y: 0.77, scale: 0.25 },
  { id: 'kimi', name: 'Kimi', x: 0.69, y: 0.78, scale: 0.25 },
  { id: 'glm', name: 'GLM', x: 0.82, y: 0.8, scale: 0.26 },
]

export const objectClip = (o: ObjectDef, phase: Exclude<ObjectPhase, 'gone'>) => `/objects/${o.dir ?? o.id}/${phase}.mp4`
export const PLACEHOLDER = (phase: Exclude<ObjectPhase, 'gone'>) => `/objects/_placeholder/${phase}.mp4`

/** Director events on the table, from a segment's `table` field:
 *  "arrive:claude" · "react:claude,codex" · "react:all" · "dim:all" · "clear" */
export type TableEvent = string
