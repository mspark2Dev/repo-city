import type { CityMap } from './types.gen'

const BASE = '/api/v1'

export interface FileDetail {
  id: string
  path: string
  lang: string
  metrics: Record<string, number>
  source: string
  imports: string[]
  importedBy: string[]
}

/** Errors carry a code so the interface can phrase them in the reader's language. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string | null,
  ) {
    super(message)
  }
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text()
    let code: string | null = null
    let message = body
    try {
      const detail = (JSON.parse(body) as { detail?: unknown }).detail
      if (detail && typeof detail === 'object') {
        code = (detail as { code?: string }).code ?? null
        message = (detail as { message?: string }).message ?? body
      } else if (typeof detail === 'string') {
        message = detail
      }
    } catch {
      // A non-JSON body is shown as-is.
    }
    throw new ApiError(`${response.status} ${response.statusText}: ${message}`, code)
  }
  return response.json() as Promise<T>
}

export async function analyze(
  path: string,
): Promise<{ jobId: string; projectId: string; willClone: boolean }> {
  const response = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  return json(response)
}

export interface JobStatus {
  jobId: string
  projectId: string
  status: 'cloning' | 'running' | 'done' | 'error'
  done: number
  total: number
  error: string | null
  errorCode: string | null
  source: string | null
  resolvedPath: string | null
  ref: string | null
  subpath: string | null
}

export async function analysisStatus(jobId: string): Promise<JobStatus> {
  return json(await fetch(`${BASE}/analyze/${jobId}`))
}

export async function fetchCityMap(projectId: string): Promise<CityMap> {
  return json(await fetch(`${BASE}/projects/${projectId}/citymap`))
}

export async function fetchDetail(projectId: string, nodeId: string): Promise<FileDetail> {
  return json(await fetch(`${BASE}/projects/${projectId}/metrics/${nodeId}`))
}

export interface AgentHealth {
  ok: boolean
  model: string | null
  detail: string | null
}

export async function agentHealth(): Promise<AgentHealth> {
  return json(await fetch(`${BASE}/agent/health`))
}

export async function prewarm(projectId: string, nodeId: string): Promise<void> {
  await fetch(`${BASE}/agent/prewarm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectId, nodeId }),
  })
}

export async function requestRefactor(
  projectId: string,
  nodeId: string,
  instruction: string,
): Promise<{ taskId: string }> {
  const response = await fetch(`${BASE}/agent/refactor`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectId, nodeId, instruction }),
  })
  return json(response)
}

export async function applyTask(taskId: string): Promise<{ applied: string[]; snapshotId: string }> {
  const response = await fetch(`${BASE}/agent/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskId }),
  })
  return json(response)
}

export async function revertSnapshot(snapshotId: string): Promise<{ reverted: string[] }> {
  const response = await fetch(`${BASE}/agent/revert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snapshotId }),
  })
  return json(response)
}
