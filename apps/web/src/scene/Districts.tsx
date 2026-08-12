import { useMemo } from 'react'
import { DISTRICT_COLOR, DISTRICT_EDGE } from './palette'
import { useCityStore } from '../store'

const TILE_THICKNESS = 0.12

/** Directory tiles, stacked by depth so nesting reads as elevation. */
export function Districts() {
  const city = useCityStore((s) => s.city)

  const tiles = useMemo(
    () =>
      city?.districts.map((district) => ({
        id: district.id,
        depth: district.depth,
        x: district.rect.x + district.rect.w / 2,
        z: district.rect.z + district.rect.d / 2,
        y: district.y,
        w: district.rect.w,
        d: district.rect.d,
      })) ?? [],
    [city],
  )

  return (
    <group>
      {tiles.map((tile) => (
        <mesh key={tile.id} position={[tile.x, tile.y - TILE_THICKNESS / 2, tile.z]} receiveShadow>
          <boxGeometry args={[tile.w, TILE_THICKNESS, tile.d]} />
          <meshStandardMaterial
            color={tile.depth === 0 ? DISTRICT_EDGE : DISTRICT_COLOR}
            roughness={0.9}
            metalness={0}
          />
        </mesh>
      ))}
    </group>
  )
}
