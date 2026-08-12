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

export async function analyze(path: string): Promise<{ projectId: string }> {
  const response = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  return json(response)
}

export async function fetchCityMap(projectId: string): Promise<CityMap> {
  return json(await fetch(`${BASE}/projects/${projectId}/citymap`))
}

export async function fetchDetail(projectId: string, nodeId: string): Promise<FileDetail> {
  return json(await fetch(`${BASE}/projects/${projectId}/metrics/${nodeId}`))
}
