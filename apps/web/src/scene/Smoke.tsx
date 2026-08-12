import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import { AdditiveBlending, BufferAttribute, CanvasTexture, type Points } from 'three'
import type { Building, CityMap } from '../api/types.gen'
import { useCityStore } from '../store'

/** A radial falloff sprite; the default square point renders as a hard red pixel block. */
function puffTexture(): CanvasTexture {
  const size = 64
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')!
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, 'rgba(255,255,255,0.85)')
  gradient.addColorStop(0.4, 'rgba(255,255,255,0.28)')
  gradient.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  return new CanvasTexture(canvas)
}

const WORST_COUNT = 12
const PER_BUILDING = 14
const RISE_SPEED = 0.55
const PLUME_HEIGHT = 4.5

/**
 * Smoke marks the worst buildings only. Attaching a plume to every critical file would
 * cost more than the whole city costs to draw, and the point is to single out where to
 * look first.
 */
function worstBuildings(city: CityMap): Building[] {
  return city.buildings
    .filter((b) => b.grade === 'critical')
    .sort((a, b) => b.metrics.maxCC - a.metrics.maxCC || a.path.localeCompare(b.path))
    .slice(0, WORST_COUNT)
}

export function Smoke() {
  const city = useCityStore((s) => s.city)
  const points = useRef<Points>(null)
  const sprite = useMemo(puffTexture, [])

  const { positions, seeds, origins } = useMemo(() => {
    if (!city) {
      return { positions: new Float32Array(0), seeds: new Float32Array(0), origins: [] }
    }
    const districtY = new Map(city.districts.map((d) => [d.id, d.y]))
    const worst = worstBuildings(city)
    const count = worst.length * PER_BUILDING
    const positions = new Float32Array(count * 3)
    const seeds = new Float32Array(count)
    const origins: { x: number; y: number; z: number }[] = []

    worst.forEach((building) => {
      const baseY = (districtY.get(building.districtId) ?? 0) + building.height
      for (let i = 0; i < PER_BUILDING; i++) {
        origins.push({ x: building.position.x, y: baseY, z: building.position.z })
        seeds[origins.length - 1] = Math.random()
      }
    })

    return { positions, seeds, origins }
  }, [city])

  useFrame((state) => {
    const node = points.current
    if (!node || origins.length === 0) return

    const attribute = node.geometry.getAttribute('position') as BufferAttribute
    const time = state.clock.elapsedTime

    for (let i = 0; i < origins.length; i++) {
      const seed = seeds[i]
      const progress = (time * RISE_SPEED + seed) % 1
      const drift = Math.sin(time * 0.7 + seed * 12) * progress * 1.4
      attribute.setXYZ(
        i,
        origins[i].x + drift,
        origins[i].y + progress * PLUME_HEIGHT,
        origins[i].z + Math.cos(time * 0.6 + seed * 9) * progress * 0.9,
      )
    }
    attribute.needsUpdate = true
  })

  if (origins.length === 0) return null

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        map={sprite}
        size={1.6}
        color="#FF7A5A"
        transparent
        opacity={0.4}
        sizeAttenuation
        depthWrite={false}
        blending={AdditiveBlending}
      />
    </points>
  )
}
