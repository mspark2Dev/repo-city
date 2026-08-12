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

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${detail}`)
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
  source: string | null
  resolvedPath: string | null
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
