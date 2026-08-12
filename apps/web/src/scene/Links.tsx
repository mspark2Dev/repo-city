import { useMemo } from 'react'
import { CubicBezierCurve3, Vector3 } from 'three'
import type { Building, CityMap } from '../api/types.gen'
import { useCityStore } from '../store'

const ARC_HEIGHT = 0.45
const AMBIENT_SHARE = 0.05

interface Arc {
  id: string
  points: Vector3[]
  color: string
  active: boolean
}

function topOf(building: Building, districtY: Map<string, number>): Vector3 {
  const y = (districtY.get(building.districtId) ?? 0) + building.height
  return new Vector3(building.position.x, y, building.position.z)
}

function curve(from: Vector3, to: Vector3): Vector3[] {
  const lift = from.distanceTo(to) * ARC_HEIGHT
  const bezier = new CubicBezierCurve3(
    from,
    from.clone().setY(from.y + lift),
    to.clone().setY(to.y + lift),
    to,
  )
  return bezier.getPoints(24)
}

/**
 * Drawing every import at once produces a hairball that says nothing. Only the heaviest
 * edges stay visible at rest; selecting a building reveals its own imports in full.
 */
function selectArcs(city: CityMap, focusId: string | null): Arc[] {
  const buildings = new Map(city.buildings.map((b) => [b.id, b]))
  const districtY = new Map(city.districts.map((d) => [d.id, d.y]))

  const threshold = (() => {
    const weights = city.links.map((l) => l.weight).sort((a, b) => b - a)
    if (weights.length === 0) return Number.POSITIVE_INFINITY
    return weights[Math.min(Math.floor(weights.length * AMBIENT_SHARE), weights.length - 1)]
  })()

  const arcs: Arc[] = []
  for (const link of city.links) {
    const touchesFocus = focusId !== null && (link.source === focusId || link.target === focusId)
    const visible = touchesFocus || link.bidirectional || link.weight >= threshold
    if (!visible) continue

    const source = buildings.get(link.source)
    const target = buildings.get(link.target)
    if (!source || !target) continue

    arcs.push({
      id: link.id,
      points: curve(topOf(source, districtY), topOf(target, districtY)),
      color: link.bidirectional ? '#FF3B30' : touchesFocus ? '#7FD4FF' : '#3A4C6B',
      active: touchesFocus || link.bidirectional,
    })
  }
  return arcs
}

export function Links() {
  const city = useCityStore((s) => s.city)
  const focus = useCityStore((s) => s.selected?.id ?? s.hovered ?? null)

  const arcs = useMemo(() => (city ? selectArcs(city, focus) : []), [city, focus])

  return (
    <group>
      {arcs.map((arc) => (
        <line key={arc.id}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[new Float32Array(arc.points.flatMap((p) => [p.x, p.y, p.z])), 3]}
            />
          </bufferGeometry>
          <lineBasicMaterial
            color={arc.color}
            transparent
            opacity={arc.active ? 0.9 : 0.25}
          />
        </line>
      ))}
    </group>
  )
}
