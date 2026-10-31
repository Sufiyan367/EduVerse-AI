import { useJobs } from './store'
import type { JobEvent } from './types'
import { queryClient } from './queryClient'

/**
 * Job-progress WebSocket with reconnection.
 *
 * The connection is a singleton rather than a hook: every screen wants job progress, and one
 * socket per mounted component would open a dozen and leak them on navigation.
 */
class JobSocket {
  private socket: WebSocket | null = null
  private retries = 0
  private timer: ReturnType<typeof setTimeout> | null = null
  private closed = false

  connect() {
    this.closed = false
    const token = localStorage.getItem('eduverse_token')
    if (!token) return
    if (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) {
      return
    }
    this.closed = false
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${location.host}/api/v1/ws/jobs`, [`bearer.${token}`])
    this.socket = socket

    socket.onopen = () => {
      if (this.socket !== socket) return
      this.retries = 0
      useJobs.getState().setConnected(true)
    }
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as JobEvent
        if (payload.type === 'ping') return
        useJobs.getState().applyEvent(payload)

        // Invalidate relevant query caches when source or job status changes
        if (payload.type === 'source.updated' && payload.source_id) {
          void queryClient.invalidateQueries({ queryKey: ['source', payload.source_id] })
          void queryClient.invalidateQueries({ queryKey: ['sources'] })
          void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          void queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
        } else if (payload.type === 'job.succeeded' || payload.type === 'job.failed') {
          if (payload.source_id) {
            void queryClient.invalidateQueries({ queryKey: ['source', payload.source_id] })
          }
          void queryClient.invalidateQueries({ queryKey: ['sources'] })
          void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          void queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
        }
      } catch {
        /* malformed frame — ignore rather than tearing down the socket */
      }
    }
    socket.onclose = () => {
      if (this.socket !== socket) return
      useJobs.getState().setConnected(false)
      this.socket = null
      if (!this.closed) this.scheduleReconnect()
    }
    socket.onerror = () => socket.close()
  }

  private scheduleReconnect() {
    if (this.timer) clearTimeout(this.timer)
    // Exponential backoff capped at 15s: the server is on localhost, so it is usually
    // restarting rather than gone, and hammering it during a reload helps nobody.
    const delay = Math.min(15000, 500 * 2 ** this.retries)
    this.retries += 1
    this.timer = setTimeout(() => this.connect(), delay)
  }

  disconnect() {
    this.closed = true
    if (this.timer) clearTimeout(this.timer)
    this.socket?.close()
    this.socket = null
    useJobs.getState().setConnected(false)
  }
}

export const jobSocket = new JobSocket()

/** Streaming chat socket. One per open conversation; closed when the panel unmounts. */
export function openChatSocket(
  chatId: number,
  handlers: {
    onExcerpts?: (excerpts: unknown[]) => void
    onToken?: (text: string) => void
    onDone?: (payload: Record<string, unknown>) => void
    onError?: (message: string) => void
    onOpen?: () => void
    onClose?: () => void
  },
): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const socket = new WebSocket(`${protocol}//${location.host}/api/v1/chat/ws/${chatId}`, [`bearer.${localStorage.getItem('eduverse_token') || ''}`])

  socket.onopen = () => handlers.onOpen?.()
  socket.onclose = () => handlers.onClose?.()
  socket.onerror = () => handlers.onError?.('Lost connection to the server.')
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      switch (payload.type) {
        case 'excerpts':
          handlers.onExcerpts?.(payload.excerpts ?? [])
          break
        case 'token':
          handlers.onToken?.(payload.text ?? '')
          break
        case 'done':
          handlers.onDone?.(payload)
          break
        case 'error':
          handlers.onError?.(payload.message ?? 'Something went wrong.')
          break
      }
    } catch {
      /* ignore malformed frame */
    }
  }
  return socket
}
