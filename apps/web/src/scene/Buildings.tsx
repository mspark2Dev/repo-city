import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import { Color, InstancedMesh, type MeshStandardMaterial, Matrix4, Object3D, Vector3 } from 'three'
import type { Building } from '../api/types.gen'
import { useCityStore } from '../store'
import { GRADE_COLOR, GRADES, HOVER_COLOR, SELECTED_COLOR, type Grade } from './palette'
import { materialFor, pulse } from './materials'

const dummy = new Object3D()
const scratchColor = new Color()

interface GroupProps {
  grade: Grade
  buildings: Building[]
  districtY: Map<string, number>
}

/**
 * One InstancedMesh per grade keeps the whole city at four draw calls. Instances are
 * ordered by building id so an index maps back to a building without a lookup table.
 */
function GradeGroup({ grade, buildings, districtY }: GroupProps) {
  const mesh = useRef<InstancedMesh>(null)
  const select = useCityStore((s) => s.select)
  const hover = useCityStore((s) => s.hover)
  const selectedId = useCityStore((s) => s.selected?.id ?? null)
  const hoveredId = useCityStore((s) => s.hovered)

  const base = useMemo(() => new Color(GRADE_COLOR[grade]), [grade])
  const material = useMemo(() => materialFor(grade), [grade])

  useEffect(() => {
    const instanced = mesh.current
    if (!instanced) return

    buildings.forEach((building, index) => {
      const y = districtY.get(building.districtId) ?? 0
      dummy.position.set(
        building.position.x,
        y + building.height / 2,
        building.position.z,
      )
      dummy.scale.set(building.footprint.w, building.height, building.footprint.d)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      instanced.setMatrixAt(index, dummy.matrix)
      instanced.setColorAt(index, base)
    })

    instanced.count = buildings.length
    instanced.instanceMatrix.needsUpdate = true
    if (instanced.instanceColor) instanced.instanceColor.needsUpdate = true

    // Raycasting rejects against the bounding volume first, and the one computed at mount
    // was built from identity matrices. Without this, no building is ever clickable.
    instanced.computeBoundingSphere()
    instanced.computeBoundingBox()
  }, [buildings, districtY, base])

  useFrame((state) => {
    const instanced = mesh.current
    if (!instanced || !instanced.instanceColor) return

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
        instanced.setColorAt(index, target)
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
      onPointerMove={(event) => {
        event.stopPropagation()
        const index = event.instanceId
        if (index !== undefined) hover(buildings[index].id)
      }}
      onPointerOut={() => hover(null)}
      onClick={(event) => {
        event.stopPropagation()
        const index = event.instanceId
        if (index !== undefined) void select(buildings[index])
      }}
      onDoubleClick={(event) => {
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
  const city = useCityStore((s) => s.city)

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

  if (!city) return null

  return (
    <>
      {GRADES.map((grade) => (
        <GradeGroup
          key={grade}
          grade={grade}
          buildings={byGrade.get(grade) ?? []}
          districtY={districtY}
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
