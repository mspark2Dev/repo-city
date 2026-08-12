import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useRef, useState } from 'react'
import { useCityStore } from '../store'

const SAMPLE_MS = 500

interface Sample {
  fps: number
  ms: number
  calls: number
  tris: number
}

/**
 * Frame cost, on screen.
 *
 * Counting requestAnimationFrame callbacks in a headless browser said 60fps while the real
 * thing stuttered; what matters is how long a frame takes and how many draw calls it makes,
 * measured where it is actually being looked at.
 */
export function Stats({ onSample }: { onSample: (sample: Sample) => void }) {
  const gl = useThree((s) => s.gl)
  const frames = useRef(0)
  const worst = useRef(0)
  const since = useRef(performance.now())
  const last = useRef(performance.now())
  const counts = useRef({ calls: 0, tris: 0 })

  // Draw calls accumulate during the render, and this hook runs before it. Turning off the
  // automatic reset lets the numbers be read from the frame that just finished instead of
  // the one about to start — which is why the readout said one draw call.
  useEffect(() => {
    gl.info.autoReset = false
    return () => {
      gl.info.autoReset = true
    }
  }, [gl])

  useFrame(() => {
    const now = performance.now()
    worst.current = Math.max(worst.current, now - last.current)
    last.current = now
    frames.current += 1

    counts.current = { calls: gl.info.render.calls, tris: gl.info.render.triangles }
    gl.info.reset()

    const elapsed = now - since.current
    if (elapsed < SAMPLE_MS) return

    onSample({
      fps: Math.round((frames.current * 1000) / elapsed),
      ms: Math.round(worst.current),
      calls: counts.current.calls,
      tris: counts.current.tris,
    })
    frames.current = 0
    worst.current = 0
    since.current = now
  })

  return null
}

export function StatsReadout() {
  const [sample, setSample] = useState<Sample | null>(null)
  const shadows = useCityStore((s) => s.shadowsEnabled)
  const city = useCityStore((s) => s.city)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'p' || event.metaKey || event.ctrlKey) return
      const active = document.activeElement
      if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) return
      setVisible((on) => !on)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!visible || !city) return null
  const floors = city.buildings.reduce((n, b) => n + (b.floors?.length ?? 0), 0)

  return (
    <>
      <StatsProbe onSample={setSample} />
      <div className="stats">
        <div>
          <b>{sample?.fps ?? '–'}</b> fps · worst {sample?.ms ?? '–'} ms
        </div>
        <div>
          {sample?.calls ?? '–'} draw calls · {((sample?.tris ?? 0) / 1000).toFixed(0)}k tris
        </div>
        <div>
          {city.buildings.length} buildings · {floors} floors
        </div>
        <div>shadows {shadows ? 'on' : 'off'}</div>
      </div>
    </>
  )
}

/** Rendered inside the canvas by CityCanvas; kept here so the readout owns its own probe. */
let probe: ((sample: Sample) => void) | null = null

function StatsProbe({ onSample }: { onSample: (sample: Sample) => void }) {
  useEffect(() => {
    probe = onSample
    return () => {
      probe = null
    }
  }, [onSample])
  return null
}

export function StatsInCanvas() {
  return <Stats onSample={(sample) => probe?.(sample)} />
}
