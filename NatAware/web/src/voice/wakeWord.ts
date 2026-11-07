/**
 * "Hey NatBot" wake word, using the browser's speech recogniser in continuous mode
 * (Chrome, Edge, Safari). Opt-in only: the recogniser runs while NatAware is open and the
 * user has switched it on. It pauses whenever NatBot is already listening or talking.
 *
 * Recognisers often mishear a made-up name, so the matcher accepts the usual near misses
 * ("hey nat bot", "hey matt bot", "hey not bot", "hey natbots"...).
 */

export type WakeState = 'off' | 'listening' | 'paused' | 'error' | 'unsupported'

const WAKE = /\b(?:hey|hi|hay|ok|okay)[\s,.-]*(?:nat|nate|natt|matt|mat|nap|not|gnat|knat)[\s-]?(?:bot|bots|bought|pot|box|butt)\b[\s,.!?-]*/i

export function wakeWordSupported(): boolean {
  const w = window as any
  return typeof window !== 'undefined' && !!(w.SpeechRecognition || w.webkitSpeechRecognition)
}

/** Returns what was said after the wake phrase ('' if nothing), or null if no wake phrase. */
export function matchWake(transcript: string): string | null {
  const m = WAKE.exec(transcript)
  return m ? transcript.slice(m.index + m[0].length).trim() : null
}

export class WakeWordListener {
  private rec: any = null
  private wanted = false // switched on by the user
  private paused = false
  private restartTimer: number | undefined
  private failures = 0
  onWake: (rest: string) => void
  onState: (s: WakeState) => void

  constructor(onWake: (rest: string) => void, onState: (s: WakeState) => void) {
    this.onWake = onWake
    this.onState = onState
  }

  start() {
    if (!wakeWordSupported()) return this.onState('unsupported')
    this.wanted = true
    this.failures = 0
    if (!this.paused) this.spawn()
  }

  stop() {
    this.wanted = false
    this.kill()
    this.onState('off')
  }

  /** Temporarily stop (NatBot is busy with the mic or speaking). */
  pause() {
    if (this.paused) return
    this.paused = true
    this.kill()
    if (this.wanted) this.onState('paused')
  }

  resume() {
    if (!this.paused) return
    this.paused = false
    if (this.wanted) this.spawn()
  }

  private kill() {
    window.clearTimeout(this.restartTimer)
    const rec = this.rec
    this.rec = null
    if (rec) {
      rec.onend = null
      rec.onresult = null
      rec.onerror = null
      try {
        rec.abort()
      } catch {
        /* already stopped */
      }
    }
  }

  private spawn() {
    this.kill()
    const w = window as any
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
    const rec = new Ctor()
    rec.lang = 'en-GB'
    rec.continuous = true
    rec.interimResults = false
    rec.maxAlternatives = 3
    rec.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i]
        for (let a = 0; a < result.length; a++) {
          const rest = matchWake(result[a].transcript)
          if (rest !== null) {
            this.failures = 0
            this.pause()
            this.onWake(rest)
            return
          }
        }
      }
    }
    rec.onerror = (e: any) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        this.wanted = false
        this.kill()
        this.onState('error')
      } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
        this.failures++
      }
    }
    // Browsers end continuous recognition every so often; quietly start again.
    rec.onend = () => {
      if (!this.wanted || this.paused || this.rec !== rec) return
      const delay = Math.min(10_000, 300 * 2 ** Math.min(this.failures, 5))
      this.restartTimer = window.setTimeout(() => this.wanted && !this.paused && this.spawn(), delay)
    }
    try {
      rec.start()
      this.rec = rec
      this.onState('listening')
    } catch {
      this.onState('error')
    }
  }
}

/** A soft two-note chime so people know NatBot heard them (helpful when not looking at the screen). */
export function chime(ctx: AudioContext | null) {
  if (!ctx || ctx.state !== 'running') return
  const now = ctx.currentTime
  ;[660, 880].forEach((freq, i) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = freq
    gain.gain.setValueAtTime(0.0001, now + i * 0.12)
    gain.gain.exponentialRampToValueAtTime(0.12, now + i * 0.12 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.12 + 0.25)
    osc.connect(gain).connect(ctx.destination)
    osc.start(now + i * 0.12)
    osc.stop(now + i * 0.12 + 0.3)
  })
}
