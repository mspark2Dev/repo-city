import type { Building, District, Link, Stats } from './types.gen'

export interface DeltaOp {
  op: 'add' | 'remove' | 'update' | 'district.add' | 'district.remove' | 'district.update'
  id?: string
  building?: Building
  district?: District
  previous?: { height: number; grade: Building['grade']; maxCC: number; loc: number }
}

export type ServerEvent =
  | { type: 'agent.plan'; taskId: string; steps: string[] }
  | { type: 'agent.token'; taskId: string; delta: string }
  | { type: 'agent.retry'; taskId: string; reason: string }
  | {
      type: 'agent.diff'
      taskId: string
      diff: string
      path: string
      proposal: string
      verdict: Verdict | null
    }
  | { type: 'agent.error'; taskId: string; message: string; stage: string }
  | { type: 'analysis.cloning'; jobId: string; url: string }
  | { type: 'analysis.progress'; jobId: string; done: number; total: number }
  | { type: 'analysis.done'; jobId: string; projectId: string }
  | { type: 'analysis.error'; jobId: string; message: string }
  | {
      type: 'citymap.delta'
      taskId?: string
      reason?: string
      ops: DeltaOp[]
      links: Link[]
      stats: Stats
    }

export interface Verdict {
  parses: boolean
  lostSymbols: string[]
  beforeMaxCC: number
  afterMaxCC: number
  beforeLoc: number
  afterLoc: number
  improved: boolean
}

const RETRY_DELAY = 2000

/** One socket per project carries analysis, agent, and city events; callers route on type. */
export function connect(projectId: string, onEvent: (event: ServerEvent) => void): () => void {
  let socket: WebSocket | null = null
  let retry: ReturnType<typeof setTimeout> | null = null
  let closed = false

  const open = () => {
    if (closed) return
    const url = new URL('/ws/stream', window.location.href)
    url.protocol = url.protocol.replace('http', 'ws')
    url.searchParams.set('projectId', projectId)

    socket = new WebSocket(url)
    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as ServerEvent)
      } catch {
        // A malformed frame is not worth tearing the connection down for.
      }
    }
    socket.onclose = () => {
      if (!closed) retry = setTimeout(open, RETRY_DELAY)
    }
  }

  open()

  return () => {
    closed = true
    if (retry) clearTimeout(retry)
    socket?.close()
  }
}
