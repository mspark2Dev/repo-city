export type AgentEvent =
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
  | { type: 'citymap.applied'; taskId?: string; paths: string[] }

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
export function connect(projectId: string, onEvent: (event: AgentEvent) => void): () => void {
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
        onEvent(JSON.parse(message.data) as AgentEvent)
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
