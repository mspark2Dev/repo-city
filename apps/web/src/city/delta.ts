import type { CityMap } from '../api/types.gen'
import type { DeltaOp } from '../api/ws'

export interface Transition {
  id: string
  kind: 'add' | 'remove' | 'update'
  startedAt: number
  fromHeight: number
  toHeight: number
}

export const TRANSITION_MS = 900

/**
 * Applies a server delta to the city and records what moved.
 *
 * Ids are repo-relative paths, so an operation names the same building across analyses and
 * the canvas can animate exactly the ones that changed.
 */
export function applyDelta(
  city: CityMap,
  ops: DeltaOp[],
  links: CityMap['links'],
  stats: CityMap['stats'],
  now: number,
): { city: CityMap; transitions: Transition[] } {
  const buildings = new Map(city.buildings.map((b) => [b.id, b]))
  const districts = new Map(city.districts.map((d) => [d.id, d]))
  const transitions: Transition[] = []

  for (const op of ops) {
    switch (op.op) {
      case 'add':
        if (op.building) {
          buildings.set(op.building.id, op.building)
          transitions.push({
            id: op.building.id,
            kind: 'add',
            startedAt: now,
            fromHeight: 0,
            toHeight: op.building.height,
          })
        }
        break

      case 'remove':
        if (op.id) {
          const going = buildings.get(op.id)
          transitions.push({
            id: op.id,
            kind: 'remove',
            startedAt: now,
            fromHeight: going?.height ?? 0,
            toHeight: 0,
          })
          buildings.delete(op.id)
        }
        break

      case 'update':
        if (op.building) {
          buildings.set(op.building.id, op.building)
          transitions.push({
            id: op.building.id,
            kind: 'update',
            startedAt: now,
            fromHeight: op.previous?.height ?? op.building.height,
            toHeight: op.building.height,
          })
        }
        break

      case 'district.add':
      case 'district.update':
        if (op.district) districts.set(op.district.id, op.district)
        break

      case 'district.remove':
        if (op.id) districts.delete(op.id)
        break
    }
  }

  return {
    city: {
      ...city,
      buildings: [...buildings.values()].sort((a, b) => a.id.localeCompare(b.id)),
      districts: [...districts.values()].sort((a, b) => a.id.localeCompare(b.id)),
      links,
      stats,
    },
    transitions,
  }
}

/** Buildings that were removed still need to be drawn while they collapse. */
export function ghostsOf(
  previous: CityMap | null,
  transitions: Transition[],
): CityMap['buildings'] {
  if (!previous) return []
  const removing = new Set(transitions.filter((t) => t.kind === 'remove').map((t) => t.id))
  return previous.buildings.filter((b) => removing.has(b.id))
}
