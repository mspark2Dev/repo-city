import { useEffect, useMemo, useRef } from 'react'
import { Color, InstancedMesh, Object3D } from 'three'
import { useCityStore } from '../store'
import { DISTRICT_COLOR, DISTRICT_EDGE } from './palette'

const dummy = new Object3D()
const tint = new Color()
const TILE_THICKNESS = 0.12

/** Directory tiles, stacked by depth so nesting reads as elevation. One draw call. */
export function Districts() {
  const city = useCityStore((s) => s.city)
  const mesh = useRef<InstancedMesh>(null)

  const tiles = useMemo(
    () =>
      city?.districts.map((district) => ({
        depth: district.depth,
        x: district.rect.x + district.rect.w / 2,
        z: district.rect.z + district.rect.d / 2,
        y: district.y,
        w: district.rect.w,
        d: district.rect.d,
      })) ?? [],
    [city],
  )

  useEffect(() => {
    const instanced = mesh.current
    if (!instanced || tiles.length === 0) return

    tiles.forEach((tile, index) => {
      dummy.position.set(tile.x, tile.y - TILE_THICKNESS / 2, tile.z)
      dummy.scale.set(tile.w, TILE_THICKNESS, tile.d)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      instanced.setMatrixAt(index, dummy.matrix)
      instanced.setColorAt(index, tint.set(tile.depth === 0 ? DISTRICT_EDGE : DISTRICT_COLOR))
    })

    instanced.count = tiles.length
    instanced.instanceMatrix.needsUpdate = true
    if (instanced.instanceColor) instanced.instanceColor.needsUpdate = true
    instanced.computeBoundingSphere()
  }, [tiles])

  if (tiles.length === 0) return null

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, tiles.length]} receiveShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial roughness={0.9} metalness={0} />
    </instancedMesh>
  )
}
