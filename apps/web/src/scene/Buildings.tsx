import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import { Color, InstancedMesh, type MeshStandardMaterial, Object3D } from 'three'
import { TRANSITION_MS, type Transition } from '../city/delta'
import { useCityStore } from '../store'
import { materialFor, pulse } from './materials'
import { GRADE_COLOR, GRADES, HOVER_COLOR, SELECTED_COLOR, type Grade } from './palette'
import { slabsOf, type Slab } from './slabs'

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

/** How far through its transition a slab's building is, as a scale on its height. */
function scaleOf(transition: Transition | undefined, now: number): number {
  if (!transition) return 1
  const t = Math.min((now - transition.startedAt) / TRANSITION_MS, 1)
  if (transition.kind === 'remove') return collapse(t)
  if (transition.toHeight <= 0) return 1
  const eased = spring(t)
  const from = transition.fromHeight / transition.toHeight
  return from + (1 - from) * eased
}

interface GroupProps {
  grade: Grade
  slabs: Slab[]
  transitions: Map<string, Transition>
  ghost?: boolean
}

/**
 * One InstancedMesh per grade. Floors join the same four meshes as whole buildings, so a
 * city drawn as stacks costs the same handful of draw calls as one drawn as bars.
 */
function GradeGroup({ grade, slabs, transitions, ghost = false }: GroupProps) {
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

    slabs.forEach((slab, index) => {
      const scale = scaleOf(transitions.get(slab.buildingId), now)
      const height = Math.max(slab.height * scale, 0.001)
      dummy.position.set(slab.x, slab.baseY * scale + height / 2, slab.z)
      dummy.scale.set(slab.width, height, slab.depth)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      instanced.setMatrixAt(index, dummy.matrix)
    })

    instanced.count = slabs.length
    instanced.instanceMatrix.needsUpdate = true
  }

  useEffect(() => {
    const instanced = mesh.current
    if (!instanced) return

    writeMatrices(performance.now())
    slabs.forEach((_, index) => instanced.setColorAt(index, base))
    if (instanced.instanceColor) instanced.instanceColor.needsUpdate = true

    // Raycasting rejects against the bounding volume first, and the one computed at mount
    // was built from identity matrices. Without this, nothing is ever clickable.
    instanced.computeBoundingSphere()
    instanced.computeBoundingBox()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slabs, base])

  useFrame((state) => {
    const instanced = mesh.current
    if (!instanced || !instanced.instanceColor) return

    if (transitions.size > 0) {
      writeMatrices(performance.now())
      instanced.computeBoundingSphere()
    }

    const glow = pulse(grade, state.clock.elapsedTime)
    if (glow !== null) {
      ;(instanced.material as MeshStandardMaterial).emissiveIntensity = glow
    }

    let dirty = false
    slabs.forEach((slab, index) => {
      const target =
        slab.buildingId === selectedId
          ? SELECTED_COLOR
          : slab.buildingId === hoveredId
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

  if (slabs.length === 0) return null

  const pick = (instanceId: number | undefined) =>
    instanceId === undefined ? null : (slabs[instanceId] ?? null)

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, slabs.length]}
      castShadow
      receiveShadow
      material={material}
      onPointerMove={
        ghost
          ? undefined
          : (event) => {
              event.stopPropagation()
              hover(pick(event.instanceId)?.buildingId ?? null)
            }
      }
      onPointerOut={ghost ? undefined : () => hover(null)}
      onClick={
        ghost
          ? undefined
          : (event) => {
              event.stopPropagation()
              const slab = pick(event.instanceId)
              if (slab) void select(slab.buildingId, slab.floorIndex)
            }
      }
      onDoubleClick={
        ghost
          ? undefined
          : (event) => {
              event.stopPropagation()
              const slab = pick(event.instanceId)
              if (!slab) return
              void select(slab.buildingId, slab.floorIndex)
              window.dispatchEvent(new CustomEvent('repocity:focus'))
            }
      }
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

  const byGrade = useMemo(() => {
    const groups = new Map<Grade, Slab[]>(GRADES.map((g) => [g, []]))
    if (city) for (const slab of slabsOf(city)) groups.get(slab.grade)?.push(slab)
    return groups
  }, [city])

  const ghostsByGrade = useMemo(() => {
    const groups = new Map<Grade, Slab[]>(GRADES.map((g) => [g, []]))
    if (!showBaseline && city && ghosts.length > 0) {
      const removing = new Set(ghosts.map((b) => b.id))
      const stale = { ...city, buildings: ghosts }
      for (const slab of slabsOf(stale)) {
        if (removing.has(slab.buildingId)) groups.get(slab.grade)?.push(slab)
      }
    }
    return groups
  }, [ghosts, showBaseline, city])

  if (!city) return null

  return (
    <>
      {GRADES.map((grade) => (
        <GradeGroup
          key={grade}
          grade={grade}
          slabs={byGrade.get(grade) ?? []}
          transitions={transitions}
        />
      ))}
      {GRADES.map((grade) => (
        <GradeGroup
          key={`ghost-${grade}`}
          grade={grade}
          slabs={ghostsByGrade.get(grade) ?? []}
          transitions={transitions}
          ghost
        />
      ))}
    </>
  )
}
