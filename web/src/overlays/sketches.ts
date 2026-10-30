/** Desk sketches: original neon-chalk line glyphs, drawn on the desk plane. Coordinates are in a
 *  1000×400 "desk" space (x across the desk, y from the far edge (0) to the near edge (400)).
 *  Each stroke is an SVG path; `delay` staggers the draw-on. Labels use a handwritten face. */

export interface Stroke { d: string; delay?: number; color?: 'teal' | 'warm' | 'red'; width?: number }
export interface Glyph { id: string; x: number; y: number; scale?: number; strokes: Stroke[]; label?: string; labelDy?: number }
export interface Sketch { id: string; glyphs: Glyph[]; keep?: boolean; crossout?: string[] }

const heart: Glyph = {
  id: 'heart', x: 500, y: 170, scale: 1.5, label: 'in love with AI', labelDy: 120,
  strokes: [
    { d: 'M0,20 C-40,-30 -110,10 -60,70 L0,130 L60,70 C110,10 40,-30 0,20 Z' },
    { d: 'M-25,70 L-10,70 L-2,50 L8,90 L16,70 L30,70', delay: 0.8, color: 'warm', width: 2 }, // tiny trace
  ],
}

const codex: Glyph = {
  id: 'codex', x: 130, y: 110, label: 'Codex', labelDy: 110,
  strokes: [
    { d: 'M-90,-55 H90 Q100,-55 100,-45 V55 Q100,65 90,65 H-90 Q-100,65 -100,55 V-45 Q-100,-55 -90,-55 Z' },
    { d: 'M-100,-30 H100', delay: 0.5 },
    { d: 'M-70,0 L-45,15 L-70,30', delay: 0.9, color: 'warm' },
    { d: 'M-30,30 H10', delay: 1.2, color: 'warm' },
  ],
}

const claude: Glyph = {
  id: 'claude', x: 330, y: 115, label: 'Claude', labelDy: 110,
  strokes: [
    { d: 'M-80,-50 H80 Q100,-50 100,-30 V30 Q100,50 80,50 H-20 L-55,80 L-50,50 H-80 Q-100,50 -100,30 V-30 Q-100,-50 -80,-50 Z' },
    { d: 'M-40,0 a6,6 0 1,0 0.1,0', delay: 0.8, color: 'warm' },
    { d: 'M0,0 a6,6 0 1,0 0.1,0', delay: 1.0, color: 'warm' },
    { d: 'M40,0 a6,6 0 1,0 0.1,0', delay: 1.2, color: 'warm' },
  ],
}

const grokbot: Glyph = {
  id: 'grokbot', x: 670, y: 115, label: 'GrokBot', labelDy: 115,
  strokes: [
    { d: 'M-70,-40 H70 Q90,-40 90,-20 V50 Q90,70 70,70 H-70 Q-90,70 -90,50 V-20 Q-90,-40 -70,-40 Z' },
    { d: 'M0,-40 V-65 M-10,-70 a10,10 0 1,0 20,0 a10,10 0 1,0 -20,0', delay: 0.5 },
    { d: 'M-45,-5 a10,10 0 1,0 0.1,0 M45,-5 a10,10 0 1,0 0.1,0', delay: 0.8, color: 'warm' },
    // candlestick chart as the mouth
    { d: 'M-50,45 V25 M-40,20 V50 M-20,40 V15 M-10,10 V45 M10,35 V5 M20,0 V40 M40,25 V-5 M50,-10 V30', delay: 1.1, color: 'warm', width: 2 },
  ],
}

const hermes: Glyph = {
  id: 'hermes', x: 880, y: 110, label: 'Hermes', labelDy: 105,
  strokes: [
    { d: 'M-60,-35 H60 V40 H-60 Z M-60,-35 L0,10 L60,-35', delay: 0 },
    { d: 'M-60,0 C-90,-20 -120,-10 -140,10 C-120,5 -100,10 -90,25 C-110,25 -125,35 -135,50', delay: 0.7 }, // left wing
    { d: 'M60,0 C90,-20 120,-10 140,10 C120,5 100,10 90,25 C110,25 125,35 135,50', delay: 0.7 }, // right wing
  ],
}

const lobster: Glyph = {
  id: 'lobster', x: 500, y: 225, scale: 1.05, label: 'OpenClaw', labelDy: 150,
  strokes: [
    // body + tail segments
    { d: 'M0,-60 C30,-60 45,-35 45,-5 C45,25 30,45 0,45 C-30,45 -45,25 -45,-5 C-45,-35 -30,-60 0,-60 Z' },
    { d: 'M-35,40 C-30,65 -20,85 0,95 C20,85 30,65 35,40 M-25,60 H25 M-18,78 H18', delay: 0.6 },
    { d: 'M-12,95 L-28,125 L-8,120 M12,95 L28,125 L8,120', delay: 1.1 }, // tail fan
    // claws
    { d: 'M-40,-30 C-70,-45 -95,-70 -105,-100 C-125,-95 -140,-80 -150,-60 C-135,-62 -120,-58 -110,-50 C-130,-45 -145,-30 -150,-15 C-120,-20 -90,-35 -40,-15', delay: 0.9, color: 'warm' },
    { d: 'M40,-30 C70,-45 95,-70 105,-100 C125,-95 140,-80 150,-60 C135,-62 120,-58 110,-50 C130,-45 145,-30 150,-15 C120,-20 90,-35 40,-15', delay: 0.9, color: 'warm' },
    // antennae + eyes
    { d: 'M-15,-60 C-30,-100 -45,-130 -70,-150 M15,-60 C30,-100 45,-130 70,-150', delay: 1.5, width: 1.5 },
    { d: 'M-18,-52 a4,4 0 1,0 0.1,0 M18,-52 a4,4 0 1,0 0.1,0', delay: 1.7, color: 'warm' },
    // legs
    { d: 'M-40,0 L-75,20 M-40,15 L-78,40 M-38,30 L-70,58 M40,0 L75,20 M40,15 L78,40 M38,30 L70,58', delay: 1.3, width: 1.5 },
  ],
}

const crossout: Glyph = {
  id: 'crossout', x: 500, y: 225, scale: 1.05,
  strokes: [
    { d: 'M-150,-150 L150,130', color: 'red', width: 4 },
    { d: 'M150,-150 L-150,130', delay: 0.35, color: 'red', width: 4 },
    { d: 'M190,20 L260,20 M240,5 L262,20 L240,35', delay: 1.2, color: 'warm' }, // → next
  ],
  label: 'gave up · next', labelDy: 180,
}

const coin: Glyph = {
  id: 'coin', x: 500, y: 120,
  strokes: [
    { d: 'M-40,0 a40,28 0 1,0 80,0 a40,28 0 1,0 -80,0', color: 'warm' },
    { d: 'M-8,-14 V14 M-12,-10 H6 Q14,-10 14,-3 Q14,2 6,2 H-12 M-12,2 H8 Q16,2 16,9 Q16,14 8,14 H-12', delay: 0.6, color: 'warm', width: 2 },
  ],
  label: 'make money, in the open', labelDy: 70,
}

const links: Glyph = {
  id: 'links', x: 0, y: 0,
  strokes: [
    { d: 'M130,190 Q330,120 500,120 Q670,120 880,190', width: 1.5 },
    { d: 'M330,185 Q500,140 670,185', delay: 0.5, width: 1.5 },
  ],
}

export const SKETCHES: Record<string, Sketch> = {
  heart: { id: 'heart', glyphs: [heart] },
  grid: { id: 'grid', glyphs: [{ id: 'grid', x: 0, y: 0, strokes: Array.from({ length: 9 }, (_, i) => ({ d: `M${100 + i * 100},0 V400`, delay: i * 0.08, width: 1 })).concat(Array.from({ length: 4 }, (_, i) => ({ d: `M0,${80 + i * 80} H1000`, delay: 0.3 + i * 0.1, width: 1 }))) }] },
  codex: { id: 'codex', glyphs: [codex, claude], keep: true },
  grokbot: { id: 'grokbot', glyphs: [grokbot, hermes], keep: true },
  lobster: { id: 'lobster', glyphs: [lobster], keep: true },
  'lobster-crossout': { id: 'lobster-crossout', glyphs: [crossout], keep: true },
  team: { id: 'team', glyphs: [links, coin], keep: true },
}

/** Sketches that stay on the desk after their segment (the team builds up), reset on `heart`. */
export const RESET_ON = new Set(['heart', 'grid'])
