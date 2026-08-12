import type { Building, CityMap } from '../api/types.gen'
import type { Grade } from './palette'

/**
 * One drawable box: either a whole building, or one function inside it.
 *
 * A file with several functions is drawn as a stack — each slab sized by the function's
 * length and coloured by its complexity — so a building reads as a section through its own
 * source rather than a single bar. Slabs are grouped by grade, which keeps the whole city
 * at one instanced mesh per grade however many floors it grows.
 */
export interface Slab {
  buildingId: string
  floorIndex: number | null
  grade: Grade
  x: number
  z: number
  baseY: number
  height: number
  width: number
  depth: number
}

const FLOOR_INSET = 0.86
/** Floors are drawn slightly narrower than their building, so the stack shows its seams. */

export function slabsOf(city: CityMap): Slab[] {
  const districtY = new Map(city.districts.map((d) => [d.id, d.y]))
  const slabs: Slab[] = []

  for (const building of city.buildings) {
    const ground = districtY.get(building.districtId) ?? 0
    // The schema gives floors a default, so the generated type makes them optional.
    const floors = building.floors ?? []
    if (floors.length === 0) {
      slabs.push(whole(building, ground))
      continue
    }

    // The building's own colour stays as a plinth behind the floors, so gaps between
    // functions — imports, fields, class scaffolding — are still part of the shape.
    slabs.push({ ...whole(building, ground), width: building.footprint.w * 0.7, depth: building.footprint.d * 0.7 })

    floors.forEach((floor, index) => {
      slabs.push({
        buildingId: building.id,
        floorIndex: index,
        grade: floor.grade,
        x: building.position.x,
        z: building.position.z,
        baseY: ground + floor.y,
        height: floor.height,
        width: building.footprint.w * FLOOR_INSET,
        depth: building.footprint.d * FLOOR_INSET,
      })
    })
  }

  return slabs
}

function whole(building: Building, ground: number): Slab {
  return {
    buildingId: building.id,
    floorIndex: null,
    grade: building.grade,
    x: building.position.x,
    z: building.position.z,
    baseY: ground,
    height: building.height,
    width: building.footprint.w,
    depth: building.footprint.d,
  }
}
