import { CanvasTexture, RepeatWrapping, type Texture } from 'three'

const CELL = 16
const COLUMNS = 6
const ROWS = 8

/**
 * A facade of lit and dark windows, drawn once and shared by every building.
 *
 * This is the difference between a bar and a building. One canvas texture costs nothing
 * per instance and the grid survives being stretched across boxes of different heights,
 * because at the distance a skyline is read from the eye wants rhythm, not accuracy.
 */
function paint(litRatio: number, glow: string, dark: string): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = COLUMNS * CELL
  canvas.height = ROWS * CELL
  const ctx = canvas.getContext('2d')!

  ctx.fillStyle = dark
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // A fixed pattern rather than a random one: the same building looks the same on every
  // analysis, which is the rule the whole layout follows.
  let seed = 0x2f6e2b1
  const next = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0
    return seed / 0xffffffff
  }

  for (let row = 0; row < ROWS; row++) {
    for (let column = 0; column < COLUMNS; column++) {
      if (next() > litRatio) continue
      ctx.fillStyle = glow
      ctx.fillRect(column * CELL + 4, row * CELL + 4, CELL - 8, CELL - 7)
    }
  }

  const texture = new CanvasTexture(canvas)
  texture.wrapS = texture.wrapT = RepeatWrapping
  texture.repeat.set(1.6, 2.4)
  return texture
}

let cache: Map<string, Texture> | null = null

export function windowTexture(kind: 'lit' | 'dim' | 'dark'): Texture {
  cache ??= new Map()
  const existing = cache.get(kind)
  if (existing) return existing

  const made =
    kind === 'lit'
      ? paint(0.55, '#dff0ff', '#0d1420')
      : kind === 'dim'
        ? paint(0.3, '#ffd9a8', '#141414')
        : paint(0.12, '#6b3b2a', '#101010')
  cache.set(kind, made)
  return made
}
