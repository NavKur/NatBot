import { api } from '../api'

/**
 * Speaks NatBot's replies sentence by sentence, as they stream in.
 * Uses ElevenLabs through the API when available (prefetching the next sentence while the
 * current one plays), and falls back to the browser's built-in voice otherwise.
 */
export class Speaker {
  private queue: { text: string; audio?: Promise<Blob | null> }[] = []
  private playing = false
  private current: HTMLAudioElement | null = null
  private abort = new AbortController()
  private idleWaiters: (() => void)[] = []
  private generation = 0
  useServerVoice: boolean
  onSpeakingChange?: (speaking: boolean) => void

  constructor(useServerVoice: boolean) {
    this.useServerVoice = useServerVoice
  }

  say(text: string) {
    if (!text.trim()) return
    const item: { text: string; audio?: Promise<Blob | null> } = { text }
    // Fetch audio for up to two queued sentences ahead of playback.
    if (this.useServerVoice && this.queue.length < 2) item.audio = this.fetchAudio(text)
    this.queue.push(item)
    if (!this.playing) void this.pump()
  }

  /** Stop talking immediately (user pressed stop, started typing, or closed the panel). */
  stop() {
    this.generation++
    this.abort.abort()
    this.abort = new AbortController()
    this.queue = []
    this.current?.pause()
    this.current = null
    if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel()
    this.setPlaying(false)
  }

  get speaking() {
    return this.playing
  }

  /** Resolves when everything queued so far has been spoken. */
  whenIdle(): Promise<void> {
    if (!this.playing && !this.queue.length) return Promise.resolve()
    return new Promise((resolve) => this.idleWaiters.push(resolve))
  }

  private fetchAudio(text: string): Promise<Blob | null> {
    return api.speak(text, this.abort.signal).catch(() => null)
  }

  private setPlaying(v: boolean) {
    if (this.playing === v) return
    this.playing = v
    this.onSpeakingChange?.(v)
    if (!v) {
      this.idleWaiters.splice(0).forEach((r) => r())
    }
  }

  private async pump() {
    const gen = this.generation
    this.setPlaying(true)
    while (this.queue.length && gen === this.generation) {
      const item = this.queue.shift()!
      // Keep the prefetch window full.
      const next = this.queue.find((q) => !q.audio)
      if (next && this.useServerVoice) next.audio = this.fetchAudio(next.text)
      const blob = item.audio ? await item.audio : null
      if (gen !== this.generation) return
      if (blob && blob.size > 0) await this.playBlob(blob)
      else await this.speakWithBrowser(item.text)
    }
    if (gen === this.generation) this.setPlaying(false)
  }

  private playBlob(blob: Blob): Promise<void> {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      this.current = audio
      const end = () => {
        URL.revokeObjectURL(url)
        resolve()
      }
      audio.onended = end
      audio.onerror = end
      audio.onpause = end
      audio.play().catch(end)
    })
  }

  private speakWithBrowser(text: string): Promise<void> {
    if (typeof speechSynthesis === 'undefined') return Promise.resolve()
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(text)
      u.lang = 'en-GB'
      const voice = speechSynthesis.getVoices().find((v) => v.lang === 'en-GB')
      if (voice) u.voice = voice
      u.onend = () => resolve()
      u.onerror = () => resolve()
      speechSynthesis.speak(u)
    })
  }
}
