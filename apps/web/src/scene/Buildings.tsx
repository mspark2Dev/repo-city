import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import { Color, InstancedMesh, type MeshStandardMaterial, Matrix4, Object3D, Vector3 } from 'three'
import type { Building } from '../api/types.gen'
import { useCityStore } from '../store'
import { GRADE_COLOR, GRADES, HOVER_COLOR, SELECTED_COLOR, type Grade } from './palette'
import { materialFor, pulse } from './materials'
import { TRANSITION_MS, type Transition } from '../city/delta'

const dummy = new Object3D()
const scratchColor = new Color()

/** Overshoot-and-settle, so a new building arrives with some weight behind it. */
function spring(t: number): number {
  if (t >= 1) return 1
  return 1 - Math.pow(2, -9 * t) * Math.cos(t * 13)
}

function collapse(t: number): number {
  return Math.max(0, 1 - t * t)
}

function progressOf(transition: Transition, now: number): number {
  return Math.min((now - transition.startedAt) / TRANSITION_MS, 1)
}

/** Height mid-transition; buildings not transitioning sit at their own height. */
function animatedHeight(building: Building, transition: Transition | undefined, now: number): number {
  if (!transition) return building.height
  const t = progressOf(transition, now)
  if (transition.kind === 'remove') return transition.fromHeight * collapse(t)
  const eased = spring(t)
  return transition.fromHeight + (transition.toHeight - transition.fromHeight) * eased
}

interface GroupProps {
  grade: Grade
  buildings: Building[]
  districtY: Map<string, number>
  transitions: Map<string, Transition>
  ghost?: boolean
}

/**
 * One InstancedMesh per grade keeps the whole city at four draw calls. Instances are
 * ordered by building id so an index maps back to a building without a lookup table.
 */
function GradeGroup({ grade, buildings, districtY, transitions, ghost = false }: GroupProps) {
  const mesh = useRef<InstancedMesh>(null)
  const select = useCityStore((s) => s.select)
  const hover = useCityStore((s) => s.hover)
  const selectedId = useCityStore((s) => s.selected?.id ?? null)
  const hoveredId = useCityStore((s) => s.hovered)

  const base = useMemo(() => new Color(GRADE_COLOR[grade]), [grade])
  const material = useMemo(() => materialFor(grade), [grade])

  const writeMatrices = (now: number) => {
    const instanced = mesh.current
    if (!instanced) return

    buildings.forEach((building, index) => {
      const y = districtY.get(building.districtId) ?? 0
      const height = animatedHeight(building, transitions.get(building.id), now)
      dummy.position.set(building.position.x, y + height / 2, building.position.z)
      dummy.scale.set(building.footprint.w, Math.max(height, 0.001), building.footprint.d)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      instanced.setMatrixAt(index, dummy.matrix)
    })

    instanced.count = buildings.length
    instanced.instanceMatrix.needsUpdate = true
  }

  useEffect(() => {
    const instanced = mesh.current
    if (!instanced) return

    writeMatrices(performance.now())
    buildings.forEach((_, index) => instanced.setColorAt(index, base))
    if (instanced.instanceColor) instanced.instanceColor.needsUpdate = true

    // Raycasting rejects against the bounding volume first, and the one computed at mount
    // was built from identity matrices. Without this, no building is ever clickable.
    instanced.computeBoundingSphere()
    instanced.computeBoundingBox()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildings, districtY, base])

  useFrame((state) => {
    const instanced = mesh.current
    if (!instanced || !instanced.instanceColor) return

    if (transitions.size > 0) {
      const now = performance.now()
      writeMatrices(now)
      if (buildings.some((b) => transitions.has(b.id))) instanced.computeBoundingSphere()
    }

    const glow = pulse(grade, state.clock.elapsedTime)
    if (glow !== null) {
      ;(instanced.material as MeshStandardMaterial).emissiveIntensity = glow
    }

    let dirty = false
    buildings.forEach((building, index) => {
      const target =
        building.id === selectedId
          ? SELECTED_COLOR
          : building.id === hoveredId
            ? HOVER_COLOR
            : base
      instanced.getColorAt(index, scratchColor)
      if (!scratchColor.equals(target)) {
        // Colour eases rather than snapping: a building going from red to blue is the
        // whole point of the refactoring, and a hard cut reads as a glitch.
        scratchColor.lerp(target, 0.12)
        instanced.setColorAt(index, scratchColor)
        dirty = true
      }
    })
    if (dirty) instanced.instanceColor.needsUpdate = true
  })

  if (buildings.length === 0) return null

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, buildings.length]}
      castShadow
      receiveShadow
      onPointerMove={ghost ? undefined : (event) => {
        event.stopPropagation()
        const index = event.instanceId
        if (index !== undefined) hover(buildings[index].id)
      }}
      onPointerOut={ghost ? undefined : () => hover(null)}
      onClick={ghost ? undefined : (event) => {
        event.stopPropagation()
        const index = event.instanceId
        if (index !== undefined) void select(buildings[index])
      }}
      onDoubleClick={ghost ? undefined : (event) => {
        event.stopPropagation()
        const index = event.instanceId
        if (index === undefined) return
        void select(buildings[index])
        window.dispatchEvent(new CustomEvent('repocity:focus'))
      }}
      material={material}
    >
      <boxGeometry args={[1, 1, 1]} />
    </instancedMesh>
  )
}

export function Buildings() {
  const live = useCityStore((s) => s.city)
  const baseline = useCityStore((s) => s.baseline)
  const showBaseline = useCityStore((s) => s.showBaseline)
  const ghosts = useCityStore((s) => s.ghosts)
  const transitionList = useCityStore((s) => s.transitions)

  const city = showBaseline && baseline ? baseline : live

  const transitions = useMemo(
    () => new Map(showBaseline ? [] : transitionList.map((t) => [t.id, t])),
    [transitionList, showBaseline],
  )

  const districtY = useMemo(() => {
    const map = new Map<string, number>()
    city?.districts.forEach((d) => map.set(d.id, d.y))
    return map
  }, [city])

  const byGrade = useMemo(() => {
    const groups = new Map<Grade, Building[]>(GRADES.map((g) => [g, []]))
    city?.buildings.forEach((b) => groups.get(b.grade)?.push(b))
    return groups
  }, [city])

  const ghostsByGrade = useMemo(() => {
    const groups = new Map<Grade, Building[]>(GRADES.map((g) => [g, []]))
    if (!showBaseline) ghosts.forEach((b) => groups.get(b.grade)?.push(b))
    return groups
  }, [ghosts, showBaseline])

  if (!city) return null

  return (
    <>
      {GRADES.map((grade) => (
        <GradeGroup
          key={grade}
          grade={grade}
          buildings={byGrade.get(grade) ?? []}
          districtY={districtY}
          transitions={transitions}
        />
      ))}
      {GRADES.map((grade) => (
        <GradeGroup
          key={`ghost-${grade}`}
          grade={grade}
          buildings={ghostsByGrade.get(grade) ?? []}
          districtY={districtY}
          transitions={transitions}
          ghost
        />
      ))}
    </>
  )
}

export function cityCenter(buildings: Building[]): Vector3 {
  if (buildings.length === 0) return new Vector3()
  const sum = buildings.reduce(
    (acc, b) => {
      acc.x += b.position.x
      acc.z += b.position.z
      return acc
    },
    { x: 0, z: 0 },
  )
  return new Vector3(sum.x / buildings.length, 0, sum.z / buildings.length)
}

export const identityMatrix = new Matrix4()
