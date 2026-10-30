import { useEffect, useRef } from 'react'

/** Deep-space backdrop: one dark colour with a slow, sparse starfield. Calm by design so the cards
 *  stay the focus. Honors prefers-reduced-motion (static stars), and renders at device pixel ratio. */
export function Starfield({ tint = '#07070d' }: { tint?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current!
    const ctx = canvas.getContext('2d')!
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    let raf = 0
    let stars: { x: number; y: number; z: number; r: number; tw: number }[] = []

    const resize = () => {
      const dpr = Math.min(2, devicePixelRatio || 1)
      const { width, height } = canvas.getBoundingClientRect()
      canvas.width = Math.max(1, width * dpr)
      canvas.height = Math.max(1, height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const n = Math.round((width * height) / 3800) // sparse: ~550 stars at 1920×1080
      stars = Array.from({ length: n }, () => ({
        x: Math.random() * width, y: Math.random() * height,
        z: 0.3 + Math.random() * 0.7, // depth: parallax speed + brightness
        r: 0.4 + Math.random() * 1.1, tw: Math.random() * Math.PI * 2,
      }))
    }
    const draw = (t: number) => {
      const { width, height } = canvas.getBoundingClientRect()
      ctx.fillStyle = tint
      ctx.fillRect(0, 0, width, height)
      // a faint nebula so the field isn't flat
      const g = ctx.createRadialGradient(width * 0.7, height * 0.2, 0, width * 0.7, height * 0.2, width * 0.7)
      g.addColorStop(0, 'rgba(90,70,160,.14)'); g.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = g; ctx.fillRect(0, 0, width, height)
      for (const s of stars) {
        if (!reduce) {
          s.x -= 0.012 * s.z; // drift left, deeper stars slower
          if (s.x < -2) { s.x = width + 2; s.y = Math.random() * height }
        }
        const a = reduce ? 0.6 * s.z : (0.45 + 0.35 * Math.sin(t * 0.0012 * s.z + s.tw)) * s.z
        ctx.fillStyle = `rgba(226,230,255,${a.toFixed(3)})`
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r * s.z, 0, Math.PI * 2); ctx.fill()
      }
      if (!reduce) raf = requestAnimationFrame(draw)
    }
    resize()
    const ro = new ResizeObserver(() => { resize(); if (reduce) draw(0) })
    ro.observe(canvas)
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); ro.disconnect() }
  }, [tint])

  return <canvas ref={ref} className="starfield" aria-hidden />
}
