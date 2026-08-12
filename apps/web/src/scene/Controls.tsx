import { useThree } from '@react-three/fiber'
import { useEffect } from 'react'
import { Vector3 } from 'three'
import type { Building } from '../api/types.gen'
import { useCityStore } from '../store'

const APPROACH = 5.5

interface OrbitLike {
  target: Vector3
  update: () => void
}

/** Keyboard and double-click framing. Dragging to find the building you just picked
 *  defeats the point of picking it. */
export function Controls() {
  const camera = useThree((s) => s.camera)
  const controls = useThree((s) => s.controls) as OrbitLike | null

  useEffect(() => {
    const focus = (building: Building) => {
      const { city } = useCityStore.getState()
      const districtY = city?.districts.find((d) => d.id === building.districtId)?.y ?? 0
      const target = new Vector3(
        building.position.x,
        districtY + building.height / 2,
        building.position.z,
      )
      const distance = Math.max(building.height, 4) * APPROACH
      camera.position.set(
        target.x + distance * 0.6,
        target.y + distance * 0.55,
        target.z + distance * 0.6,
      )
      camera.lookAt(target)
      if (controls) {
        controls.target.copy(target)
        controls.update()
      }
    }

    // Read the selection at event time: a double-click dispatches this in the same tick as
    // the selection it just made, before React has re-rendered with the new value.
    const focusSelected = () => {
      const { selected } = useCityStore.getState()
      if (selected) focus(selected)
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'f' || event.metaKey || event.ctrlKey) return
      const active = document.activeElement
      if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) return
      focusSelected()
    }

    window.addEventListener('keydown', onKey)
    window.addEventListener('repocity:focus', focusSelected)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('repocity:focus', focusSelected)
    }
  }, [camera, controls])

  return null
}
