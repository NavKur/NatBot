import type { AppState, Dashboard, Highlight, Profile, Recurring, ToolEvent, Transaction } from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  state: () => request<AppState>('/app/state'),
  skipOnboarding: () => request<AppState>('/onboarding/skip', { method: 'POST' }),
  reset: () => request<{ status: string }>('/demo/reset', { method: 'POST' }),
  dashboard: () => request<Dashboard>('/dashboard'),
  profile: () => request<Profile>('/profile'),
  transactions: (params: Record<string, string | number | boolean | string[] | undefined>) => {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === '' || v === false) continue
      if (Array.isArray(v)) v.forEach((x) => qs.append(k, x))
      else qs.set(k, String(v))
    }
    return request<{ count: number; total_debits: number; transactions: Transaction[] }>(`/transactions?${qs}`)
  },
  highlights: () => request<{ highlights: Highlight[] }>('/highlights'),
  recurring: () => request<{ recurring: Recurring[]; committed: { total: number; count: number } }>('/recurring'),
  spendingSummary: (params: { group_by: string; date_from?: string; date_to?: string }) =>
    request<{ group_by: string; rows: { group: string; total: number; count: number }[] }>(
      `/spending/summary?${new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][])}`,
    ),
  setAside: (event_id: string, weekly: number) => request('/setasides', json({ event_id, weekly })),
  removeSetAside: (event_id: string) => request(`/setasides/${encodeURIComponent(event_id)}`, { method: 'DELETE' }),
  uploadStatement: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ added: number; flagged: number; transactions: Transaction[] }>('/statements/upload', {
      method: 'POST',
      body: form,
    })
  },
  transcribe: (audio: Blob) => {
    const form = new FormData()
    const ext = audio.type.includes('mp4') ? 'mp4' : audio.type.includes('ogg') ? 'ogg' : 'webm'
    form.append('audio', audio, `speech.${ext}`)
    return request<{ text: string }>('/voice/transcribe', { method: 'POST', body: form })
  },
  speak: async (text: string, signal?: AbortSignal): Promise<Blob> => {
    const res = await fetch(`${BASE}/voice/speak`, { ...json({ text }), signal })
    if (!res.ok) throw new ApiError(res.status, 'Speech unavailable')
    return res.blob()
  },
}

export interface StreamHandlers {
  onSession?: (sessionId: string) => void
  onSentence?: (text: string) => void
  onTool?: (event: ToolEvent) => void
  onDone?: (data: { reply: string; profile?: Profile | null; complete?: boolean }) => void
  onError?: (message: string) => void
}

/** POST /chat/stream and dispatch its server-sent events as they arrive. */
export async function streamChat(
  body: { message: string; session_id: string | null; mode: 'coach' | 'onboarding' },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/chat/stream`, { ...json(body), signal })
  if (!res.ok || !res.body) {
    let message = `NatBot is unavailable (${res.status}).`
    try {
      const detail = (await res.json()).detail
      if (detail) message = detail
    } catch {
      /* ignore */
    }
    handlers.onError?.(message)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      let event = 'message'
      let data = ''
      for (const line of raw.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (!data) continue
      const payload = JSON.parse(data)
      if (event === 'session') handlers.onSession?.(payload.session_id)
      else if (event === 'sentence') handlers.onSentence?.(payload.text)
      else if (event === 'tool') handlers.onTool?.(payload)
      else if (event === 'done') handlers.onDone?.(payload)
      else if (event === 'error') handlers.onError?.(payload.message)
    }
  }
}
