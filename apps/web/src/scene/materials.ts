import { MeshStandardMaterial, type Material } from 'three'
import { GRADE_COLOR, type Grade } from './palette'
import { windowTexture } from './windows'

/**
 * Material per grade, so a building's condition reads before you can see its colour:
 * clean code is glass, and complexity turns it to rough, rusted concrete.
 */
function build(grade: Grade): Material {
  const color = GRADE_COLOR[grade]

  if (grade === 'clean') {
    // Glass without transmission. A physical material's refraction re-renders the whole
    // scene into a transmission target every frame, and clean code is most of a healthy
    // city — so the city was being drawn twice. Low roughness and a lit edge read the
    // same at the distance a skyline is seen from.
    return new MeshStandardMaterial({
      color,
      roughness: 0.15,
      metalness: 0.35,
      emissive: color,
      emissiveIntensity: 0.22,
      emissiveMap: windowTexture('lit'),
      transparent: true,
      opacity: 0.9,
    })
  }

  if (grade === 'watch') {
    return new MeshStandardMaterial({
      color,
      roughness: 0.55,
      metalness: 0.12,
      emissive: color,
      emissiveIntensity: 0.16,
      emissiveMap: windowTexture('dim'),
    })
  }

  if (grade === 'hot') {
    return new MeshStandardMaterial({
      color,
      roughness: 0.88,
      metalness: 0.04,
      emissive: color,
      emissiveIntensity: 0.12,
      emissiveMap: windowTexture('dark'),
    })
  }

  // Nothing lit is left in a critical building: the windows are out.
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
