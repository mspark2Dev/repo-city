import { useThree } from '@react-three/fiber'
import { useEffect } from 'react'
import { Fog, Vector3 } from 'three'
import type { CityMap } from '../api/types.gen'
import { useCityStore } from '../store'
import { GROUND } from './palette'

const FRAME_MARGIN = 1.9

function bounds(city: CityMap) {
  const root = city.districts.find((d) => d.depth === 0) ?? city.districts[0]
  if (!root) return { center: new Vector3(), extent: 20 }
  return {
    center: new Vector3(root.rect.x + root.rect.w / 2, 0, root.rect.z + root.rect.d / 2),
    extent: Math.max(root.rect.w, root.rect.d),
  }
}

/** Frames whatever city was just loaded; a fixed camera only ever suits one repository size. */
export function CameraRig() {
  const camera = useThree((s) => s.camera)
  const scene = useThree((s) => s.scene)
  // drei's OrbitControls registers itself here via makeDefault.
  const controls = useThree((s) => s.controls) as { target: Vector3; update: () => void } | null
  const city = useCityStore((s) => s.city)
  const projectId = useCityStore((s) => s.projectId)

  useEffect(() => {
    if (!city) return
    const { center, extent } = bounds(city)
    const distance = extent * FRAME_MARGIN

    camera.position.set(center.x + distance * 0.75, distance * 0.65, center.z + distance * 0.75)
    camera.far = Math.max(500, distance * 6)
    camera.updateProjectionMatrix()
    camera.lookAt(center)

    // Fog has to follow the city's scale; fixed distances swallow a large repository whole.
    scene.fog = new Fog(GROUND, distance * 0.9, distance * 3.2)

    if (controls) {
      controls.target.copy(center)
      controls.update()
    }
  }, [city, projectId, camera, controls, scene])

  return null
}
