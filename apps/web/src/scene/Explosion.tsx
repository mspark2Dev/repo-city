import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import { AdditiveBlending, BufferAttribute, type Points } from 'three'
import { TRANSITION_MS } from '../city/delta'
import { useCityStore } from '../store'

const SHARDS = 26
const GRAVITY = 26
const SPREAD = 7

interface Burst {
  x: number
  y: number
  z: number
  vx: number
  vy: number
  vz: number
  startedAt: number
}

/** Debris where a building came down, so a file disappearing registers as an event. */
export function Explosion() {
  const ghosts = useCityStore((s) => s.ghosts)
  const city = useCityStore((s) => s.city)
  const points = useRef<Points>(null)

  const bursts = useMemo<Burst[]>(() => {
    if (ghosts.length === 0) return []
    const districtY = new Map(city?.districts.map((d) => [d.id, d.y]) ?? [])
    const now = performance.now()

    return ghosts.flatMap((building) => {
      const baseY = (districtY.get(building.districtId) ?? 0) + building.height / 2
      return Array.from({ length: SHARDS }, () => {
        const angle = Math.random() * Math.PI * 2
        const speed = SPREAD * (0.4 + Math.random() * 0.8)
        return {
          x: building.position.x,
          y: baseY,
          z: building.position.z,
          vx: Math.cos(angle) * speed,
          vy: 4 + Math.random() * 7,
          vz: Math.sin(angle) * speed,
          startedAt: now,
        }
      })
    })
  }, [ghosts, city])

  const positions = useMemo(() => new Float32Array(bursts.length * 3), [bursts])

  useFrame(() => {
    const node = points.current
    if (!node || bursts.length === 0) return
    const attribute = node.geometry.getAttribute('position') as BufferAttribute
    const now = performance.now()

    bursts.forEach((burst, index) => {
      const t = Math.min((now - burst.startedAt) / TRANSITION_MS, 1)
      attribute.setXYZ(
        index,
        burst.x + burst.vx * t,
        Math.max(burst.y + burst.vy * t - 0.5 * GRAVITY * t * t, 0),
        burst.z + burst.vz * t,
      )
    })
    attribute.needsUpdate = true
    const material = node.material as { opacity: number }
    material.opacity = Math.max(0, 1 - (now - bursts[0].startedAt) / TRANSITION_MS)
  })

  if (bursts.length === 0) return null

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.5}
        color="#FFB08A"
        transparent
        opacity={1}
        sizeAttenuation
        depthWrite={false}
        blending={AdditiveBlending}
      />
    </points>
  )
}
