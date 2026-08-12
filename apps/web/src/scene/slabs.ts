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
  tilt: number
  spin: number
}

const FLOOR_INSET = 0.86
/** Floors are drawn slightly narrower than their building, so the stack shows its seams. */

const TAPER = 0.28
/** How much a tower narrows from its base to its roof. */

const DAMAGE: Record<Grade, number> = { clean: 0, watch: 0, hot: 0.03, critical: 0.08 }
/**
 * How far a storey slips out of true.
 *
 * Kept small on purpose. Shaking every floor of every bad building reads as noise from a
 * distance, not as damage — a city looks broken when a few structures fail visibly, not
 * when everything vibrates.
 */

/** Deterministic per slab, so a building looks the same on every analysis. */
function jitter(seed: string, salt: number): number {
  let hash = 0x811c9dc5
  for (let i = 0; i < seed.length; i++) {
    hash ^= seed.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193)
  }
  hash ^= salt * 0x9e3779b9
  return ((hash >>> 8) % 2000) / 1000 - 1
}

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
      const rise = building.height > 0 ? floor.y / building.height : 0
      const taper = 1 - TAPER * rise
      const slip = DAMAGE[floor.grade]
      slabs.push({
        buildingId: building.id,
        floorIndex: index,
        grade: floor.grade,
        x: building.position.x + jitter(building.id, index) * slip * building.footprint.w,
        z: building.position.z + jitter(building.id, index + 977) * slip * building.footprint.d,
        baseY: ground + floor.y,
        height: floor.height,
        width: building.footprint.w * FLOOR_INSET * taper,
        depth: building.footprint.d * FLOOR_INSET * taper,
        tilt: jitter(building.id, index + 313) * slip * 0.6,
        spin: jitter(building.id, index + 51) * slip * 1.4,
      })
    })
  }

  return slabs
}

function whole(building: Building, ground: number): Slab {
  const slip = DAMAGE[building.grade]
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
    // A building with no floors of its own still leans if it is in bad shape.
    tilt: jitter(building.id, 7) * slip * 0.25,
    spin: jitter(building.id, 19) * slip * 0.9,
  }
}
