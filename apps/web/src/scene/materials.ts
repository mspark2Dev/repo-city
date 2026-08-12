import { MeshPhysicalMaterial, MeshStandardMaterial, type Material } from 'three'
import { GRADE_COLOR, type Grade } from './palette'

/**
 * Material per grade, so a building's condition reads before you can see its colour:
 * clean code is glass, and complexity turns it to rough, rusted concrete.
 */
function build(grade: Grade): Material {
  const color = GRADE_COLOR[grade]

  if (grade === 'clean') {
    return new MeshPhysicalMaterial({
      color,
      roughness: 0.12,
      metalness: 0.1,
      transmission: 0.35,
      thickness: 1.2,
      ior: 1.35,
      emissive: color,
      emissiveIntensity: 0.28,
      transparent: true,
      opacity: 0.92,
    })
  }

  if (grade === 'watch') {
    return new MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.12 })
  }

  if (grade === 'hot') {
    return new MeshStandardMaterial({
      color,
      roughness: 0.88,
      metalness: 0.04,
      emissive: color,
      emissiveIntensity: 0.12,
    })
  }

  return new MeshStandardMaterial({
    color,
    roughness: 0.97,
    metalness: 0.02,
    emissive: color,
    emissiveIntensity: 0.45,
  })
}

const cache = new Map<Grade, Material>()

export function materialFor(grade: Grade): Material {
  let material = cache.get(grade)
  if (!material) {
    material = build(grade)
    cache.set(grade, material)
  }
  return material
}

/** Critical buildings pulse so the eye is drawn to them without needing to hunt. */
export function pulse(grade: Grade, time: number): number | null {
  if (grade !== 'critical') return null
  return 0.35 + 0.22 * Math.sin(time * 2.2)
}
