import { create } from 'zustand'
import { analyze, fetchCityMap, fetchDetail, type FileDetail } from './api/rest'
import type { Building, CityMap } from './api/types.gen'

type Status = 'idle' | 'loading' | 'ready' | 'error'

interface CityState {
  status: Status
  error: string | null
  projectId: string | null
  city: CityMap | null
  selected: Building | null
  detail: FileDetail | null
  hovered: string | null
  load: (path: string) => Promise<void>
  select: (building: Building | null) => Promise<void>
  hover: (id: string | null) => void
}

export const useCityStore = create<CityState>((set, get) => ({
  status: 'idle',
  error: null,
  projectId: null,
  city: null,
  selected: null,
  detail: null,
  hovered: null,

  load: async (path) => {
    set({ status: 'loading', error: null, selected: null, detail: null })
    try {
      const { projectId } = await analyze(path)
      const city = await fetchCityMap(projectId)
      set({ status: 'ready', projectId, city })
    } catch (error) {
      set({ status: 'error', error: error instanceof Error ? error.message : String(error) })
    }
  },

  select: async (building) => {
    set({ selected: building, detail: null })
    const projectId = get().projectId
    if (!building || !projectId) return
    try {
      set({ detail: await fetchDetail(projectId, building.id) })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error) })
    }
  },

  hover: (id) => set({ hovered: id }),
}))
