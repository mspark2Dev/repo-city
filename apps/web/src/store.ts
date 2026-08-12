import { create } from 'zustand'
import {
  agentHealth,
  analyze,
  applyTask,
  fetchCityMap,
  fetchDetail,
  prewarm,
  requestRefactor,
  revertSnapshot,
  type AgentHealth,
  type FileDetail,
} from './api/rest'
import { connect, type AgentEvent, type Verdict } from './api/ws'
import type { Building, CityMap } from './api/types.gen'

type Status = 'idle' | 'loading' | 'ready' | 'error'
type AgentStatus = 'idle' | 'planning' | 'generating' | 'ready' | 'applied' | 'error'

interface Proposal {
  taskId: string
  path: string
  diff: string
  content: string
  verdict: Verdict | null
}

interface CityState {
  status: Status
  error: string | null
  projectId: string | null
  city: CityMap | null
  selected: Building | null
  detail: FileDetail | null
  hovered: string | null

  llm: AgentHealth | null
  agentStatus: AgentStatus
  agentError: string | null
  steps: string[]
  streamed: string
  proposal: Proposal | null
  snapshotId: string | null
  disconnect: (() => void) | null

  load: (path: string) => Promise<void>
  select: (building: Building | null) => Promise<void>
  hover: (id: string | null) => void
  refactor: (instruction: string) => Promise<void>
  applyProposal: () => Promise<void>
  discardProposal: () => void
  revert: () => Promise<void>
}

const message = (error: unknown) => (error instanceof Error ? error.message : String(error))

export const useCityStore = create<CityState>((set, get) => ({
  status: 'idle',
  error: null,
  projectId: null,
  city: null,
  selected: null,
  detail: null,
  hovered: null,

  llm: null,
  agentStatus: 'idle',
  agentError: null,
  steps: [],
  streamed: '',
  proposal: null,
  snapshotId: null,
  disconnect: null,

  load: async (path) => {
    get().disconnect?.()
    set({ status: 'loading', error: null, selected: null, detail: null, proposal: null })
    try {
      const { projectId } = await analyze(path)
      const city = await fetchCityMap(projectId)

      const disconnect = connect(projectId, (event) => handleEvent(event, set, get))
      set({ status: 'ready', projectId, city, disconnect, agentStatus: 'idle' })

      // The badge tells you whether refactoring is available before you try to use it.
      agentHealth()
        .then((llm) => set({ llm }))
        .catch(() => set({ llm: { ok: false, model: null, detail: 'unreachable' } }))
    } catch (error) {
      set({ status: 'error', error: message(error) })
    }
  },

  select: async (building) => {
    set({ selected: building, detail: null })
    const { projectId } = get()
    if (!building || !projectId) return
    try {
      set({ detail: await fetchDetail(projectId, building.id) })
      // Warm the prompt prefix while the user reads the file and types a command.
      if (get().llm?.ok) void prewarm(projectId, building.id)
    } catch (error) {
      set({ error: message(error) })
    }
  },

  hover: (id) => set({ hovered: id }),

  refactor: async (instruction) => {
    const { projectId, selected } = get()
    if (!projectId || !selected) return
    set({ agentStatus: 'planning', agentError: null, steps: [], streamed: '', proposal: null })
    try {
      await requestRefactor(projectId, selected.id, instruction)
    } catch (error) {
      set({ agentStatus: 'error', agentError: message(error) })
    }
  },

  applyProposal: async () => {
    const { proposal, projectId } = get()
    if (!proposal || !projectId) return
    try {
      const { snapshotId } = await applyTask(proposal.taskId)
      const city = await fetchCityMap(projectId)
      const selected = get().selected
      set({
        city,
        snapshotId,
        agentStatus: 'applied',
        proposal: null,
        selected: selected ? (city.buildings.find((b) => b.id === selected.id) ?? null) : null,
      })
      const refreshed = get().selected
      if (refreshed) set({ detail: await fetchDetail(projectId, refreshed.id) })
    } catch (error) {
      set({ agentStatus: 'error', agentError: message(error) })
    }
  },

  discardProposal: () => set({ proposal: null, agentStatus: 'idle', streamed: '', steps: [] }),

  revert: async () => {
    const { snapshotId, projectId } = get()
    if (!snapshotId || !projectId) return
    try {
      await revertSnapshot(snapshotId)
      const city = await fetchCityMap(projectId)
      const selected = get().selected
      set({
        city,
        snapshotId: null,
        agentStatus: 'idle',
        selected: selected ? (city.buildings.find((b) => b.id === selected.id) ?? null) : null,
      })
      const refreshed = get().selected
      if (refreshed) set({ detail: await fetchDetail(projectId, refreshed.id) })
    } catch (error) {
      set({ agentStatus: 'error', agentError: message(error) })
    }
  },
}))

type Setter = (partial: Partial<CityState>) => void
type Getter = () => CityState

function handleEvent(event: AgentEvent, set: Setter, get: Getter): void {
  switch (event.type) {
    case 'agent.plan':
      set({ steps: event.steps, agentStatus: 'generating' })
      break
    case 'agent.token':
      set({ streamed: get().streamed + event.delta })
      break
    case 'agent.retry':
      set({ streamed: '', steps: [...get().steps, `retrying: ${event.reason}`] })
      break
    case 'agent.diff':
      set({
        agentStatus: 'ready',
        proposal: {
          taskId: event.taskId,
          path: event.path,
          diff: event.diff,
          content: event.proposal,
          verdict: event.verdict,
        },
      })
      break
    case 'agent.error':
      set({ agentStatus: 'error', agentError: `${event.stage}: ${event.message}` })
      break
    case 'citymap.applied':
      break
  }
}
