import { create } from 'zustand'
import {
  agentHealth,
  analysisStatus,
  analyze,
  applyTask,
  fetchCityMap,
  fetchDetail,
  prewarm,
  requestRefactor,
  revertSnapshot,
  ApiError,
  type AgentHealth,
  type FileDetail,
  type JobStatus,
} from './api/rest'
import { connect, type ServerEvent, type Verdict } from './api/ws'
import { useLocaleStore } from './i18n'
import type { Building, CityMap } from './api/types.gen'
import { applyDelta, ghostsOf, TRANSITION_MS, type Transition } from './city/delta'

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

  progress: { done: number; total: number } | null
  cloning: string | null
  origin: { ref: string | null; subpath: string | null } | null
  transitions: Transition[]
  ghosts: Building[]
  baseline: CityMap | null
  showBaseline: boolean

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
  toggleBaseline: () => void
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
  progress: null,
  cloning: null,
  origin: null,
  transitions: [],
  ghosts: [],
  baseline: null,
  showBaseline: false,

  llm: null,
  agentStatus: 'idle',
  agentError: null,
  steps: [],
  streamed: '',
  proposal: null,
  snapshotId: null,
  disconnect: null,

  load: async (path) => {
    set({
      status: 'loading',
      error: null,
      proposal: null,
      progress: null,
      cloning: null,
      origin: null,
      transitions: [],
      ghosts: [],
    })
    try {
      const { jobId, projectId, willClone } = await analyze(path)
      if (willClone) set({ cloning: path })
      const revisiting = get().projectId === projectId && get().city !== null

      if (!revisiting) {
        // Subscribe before waiting: analysis reports progress on this channel, and a large
        // repository would otherwise look frozen.
        get().disconnect?.()
        set({
          projectId,
          city: null,
          selected: null,
          detail: null,
          baseline: null,
          showBaseline: false,
          disconnect: connect(projectId, (event) => handleEvent(event, set, get)),
        })
      }

      const finished = await waitForAnalysis(jobId)
      set({ origin: { ref: finished.ref, subpath: finished.subpath } })

      // Re-analyzing a project already on screen arrives as a delta, which is what makes
      // the buildings animate. Refetch only if that delta did not land.
      const fetched = await fetchCityMap(projectId)
      const current = get().city
      if (!revisiting || !current || !sameStats(current.stats, fetched.stats)) {
        set({ city: fetched })
      }
      set({ status: 'ready', progress: null, cloning: null, agentStatus: 'idle' })

      // The badge tells you whether refactoring is available before you try to use it.
      agentHealth()
        .then((llm) => set({ llm }))
        .catch(() => set({ llm: { ok: false, model: null, detail: 'unreachable' } }))
    } catch (error) {
      set({ status: 'error', error: describe(error), progress: null, cloning: null })
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
    const { proposal, projectId, city } = get()
    if (!proposal || !projectId) return
    try {
      // Keep the pre-change city so the before/after comparison has something to show.
      set({ baseline: city })
      const { snapshotId } = await applyTask(proposal.taskId)
      set({ snapshotId, agentStatus: 'applied', proposal: null })
      await refreshSelection(set, get, projectId)
    } catch (error) {
      set({ agentStatus: 'error', agentError: message(error), baseline: null })
    }
  },

  discardProposal: () => set({ proposal: null, agentStatus: 'idle', streamed: '', steps: [] }),

  revert: async () => {
    const { snapshotId, projectId } = get()
    if (!snapshotId || !projectId) return
    try {
      await revertSnapshot(snapshotId)
      set({ snapshotId: null, agentStatus: 'idle', baseline: null, showBaseline: false })
      await refreshSelection(set, get, projectId)
    } catch (error) {
      set({ agentStatus: 'error', agentError: message(error) })
    }
  },

  toggleBaseline: () => set({ showBaseline: !get().showBaseline }),
}))

const POLL_MS = 150

/** Carries the server's error code so the message can be shown in the reader's language. */
class SourceFailure extends Error {
  constructor(
    message: string | null,
    readonly code: string | null,
  ) {
    super(message ?? 'analysis failed')
  }
}

function describe(error: unknown): string {
  const messages = useLocaleStore.getState().t.errors
  const code =
    error instanceof SourceFailure || error instanceof ApiError ? (error.code ?? null) : null
  if (code && messages[code]) return messages[code]
  return error instanceof Error ? error.message : String(error)
}

function sameStats(a: CityMap['stats'], b: CityMap['stats']): boolean {
  return a.files === b.files && a.loc === b.loc && a.links === b.links
}

/** The socket reports completion; polling is the fallback if a frame is missed. */
async function waitForAnalysis(jobId: string): Promise<JobStatus> {
  for (;;) {
    const status = await analysisStatus(jobId)
    if (status.status === 'done') return status
    if (status.status === 'error') throw new SourceFailure(status.error, status.errorCode)
    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
  }
}

async function refreshSelection(set: Setter, get: Getter, projectId: string): Promise<void> {
  const selected = get().selected
  if (!selected) return
  const current = get().city?.buildings.find((b) => b.id === selected.id) ?? null
  set({ selected: current })
  if (current) set({ detail: await fetchDetail(projectId, current.id) })
}

function retryLabel(reason: string): string {
  return useLocaleStore.getState().t.agent.retrying(reason)
}

type Setter = (partial: Partial<CityState>) => void
type Getter = () => CityState

function handleEvent(event: ServerEvent, set: Setter, get: Getter): void {
  switch (event.type) {
    case 'agent.plan':
      set({ steps: event.steps, agentStatus: 'generating' })
      break
    case 'agent.token':
      set({ streamed: get().streamed + event.delta })
      break
    case 'agent.retry':
      set({ streamed: '', steps: [...get().steps, retryLabel(event.reason)] })
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
    case 'analysis.cloning':
      set({ cloning: event.url })
      break

    case 'analysis.progress':
      set({ progress: { done: event.done, total: event.total }, cloning: null })
      break

    case 'analysis.done':
      set({ progress: null, cloning: null })
      break

    case 'analysis.error': {
      const messages = useLocaleStore.getState().t.errors
      const text = (event.code && messages[event.code]) || event.message
      set({ status: 'error', error: text, progress: null, cloning: null })
      break
    }

    case 'citymap.delta': {
      const current = get().city
      if (!current) break
      const now = performance.now()
      const { city, transitions } = applyDelta(current, event.ops, event.links, event.stats, now)
      set({
        city,
        transitions,
        ghosts: ghostsOf(current, transitions),
      })
      // Ghosts are only drawn while they collapse.
      setTimeout(() => set({ ghosts: [], transitions: [] }), TRANSITION_MS + 100)
      break
    }
  }
}
