import { api } from './api'
import { useServerHealth } from './store'

let checkInterval: ReturnType<typeof setInterval> | null = null

export async function checkServerHealth(): Promise<boolean> {
  try {
    const res = await api.health()
    const ok = Boolean(res && res.status === 'ok')
    useServerHealth.getState().setServerConnected(ok)
    return ok
  } catch {
    useServerHealth.getState().setServerConnected(false)
    return false
  }
}

export async function checkLlmHealth(): Promise<void> {
  try {
    const status = await api.healthLlm()
    useServerHealth.getState().setLlmStatus(status)
  } catch {
    const current = useServerHealth.getState().llmStatus
    useServerHealth.getState().setLlmStatus({
      status: 'unavailable',
      provider: current?.provider || 'ollama',
      model: current?.model || 'qwen3.5:4b',
      is_local: true,
      thinking: 'off',
      context_window: current?.context_window || 4096,
      allow_cloud_fallback: false,
      gpu: current?.gpu || 'Unknown',
      models: current?.models || [],
      message: 'Could not contact local LLM provider endpoint.',
    })
  }
}

export function startHealthMonitoring(): () => void {
  void checkServerHealth()
  void checkLlmHealth()

  if (checkInterval) clearInterval(checkInterval)
  // Regular 15-second heartbeat ensures real status without flooding server
  checkInterval = setInterval(() => {
    void checkServerHealth()
    void checkLlmHealth()
  }, 15000)

  return () => {
    if (checkInterval) {
      clearInterval(checkInterval)
      checkInterval = null
    }
  }
}
