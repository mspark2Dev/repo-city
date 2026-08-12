import { Color } from 'three'
import type { Building } from '../api/types.gen'

export type Grade = Building['grade']

/** Grade colours are specified in DESIGN.md; the city's whole read depends on them. */
export const GRADE_COLOR: Record<Grade, string> = {
  clean: '#4EA8FF',
  watch: '#FFC24E',
  hot: '#FF7A3D',
  critical: '#FF3B30',
}

export const GRADES: Grade[] = ['clean', 'watch', 'hot', 'critical']

export const SELECTED_COLOR = new Color('#FFFFFF')
export const HOVER_COLOR = new Color('#B9E1FF')

export const GROUND = '#0B0E14'
export const DISTRICT_COLOR = '#161C28'
export const DISTRICT_EDGE = '#28324A'
