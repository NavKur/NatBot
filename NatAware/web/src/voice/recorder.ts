import { audioContext } from './audio'

/**
 * Microphone capture with simple voice-activity detection, the browser twin of
 * nataware/voice/capture.py: wait for speech, then stop after `silenceMs` of quiet.
 *
 * The noise floor is measured for the first moments of the recording so it adapts to
 * quiet bedrooms and noisy kitchens alike.
 */

export interface RecordOptions {
  silenceMs?: number
  startTimeoutMs?: number
  maxMs?: number
  onLevel?: (level: number) => void // 0..1, for the on-screen level meter
  onSpeechStart?: () => void
}

const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

export function micSupported(): boolean {
  return typeof window !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
}

export class Recording {
  /** Resolves with the recorded audio, or null if no speech was heard / it was cancelled. */
  readonly result: Promise<Blob | null>
  private stopRequested = false
  private cancelled = false
  private finish: () => void = () => {}

  constructor(opts: RecordOptions = {}) {
    this.result = this.run(opts)
  }

  /** Stop now and keep what was said (the "I'm done" button). */
  stop() {
    this.stopRequested = true
    this.finish()
  }

  /** Stop and throw the audio away. */
  cancel() {
    this.cancelled = true
    this.finish()
  }

  private async run({
    silenceMs = 1500,
    startTimeoutMs = 20000,
    maxMs = 90000,
    onLevel,
    onSpeechStart,
  }: RecordOptions): Promise<Blob | null> {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    const mimeType = MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t))
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks: Blob[] = []
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)

    const ctx = audioContext()
    await ctx.resume().catch(() => {})
    const source = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 1024
    source.connect(analyser)
    const buf = new Float32Array(analyser.fftSize)

    let heardSpeech = false
    let floor = 0.01
    let calibrating = 0
    let lastVoice = performance.now()
    const started = performance.now()

    const done = new Promise<void>((resolve) => {
      this.finish = resolve
      const tick = () => {
        if (this.stopRequested || this.cancelled) return resolve()
        analyser.getFloatTimeDomainData(buf)
        let sum = 0
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
        const rms = Math.sqrt(sum / buf.length)
        const now = performance.now()

        if (calibrating < 8) {
          floor = calibrating === 0 ? rms : floor * 0.7 + rms * 0.3
          calibrating++
        }
        const threshold = Math.max(0.015, floor * 2.5)
        const voiced = rms > threshold
        onLevel?.(Math.min(1, rms / (threshold * 3)))

        if (voiced) {
          lastVoice = now
          if (!heardSpeech) {
            heardSpeech = true
            onSpeechStart?.()
          }
        } else if (!heardSpeech) {
          floor = floor * 0.95 + rms * 0.05 // keep tracking the room until they speak
        }

        if (heardSpeech && now - lastVoice > silenceMs) return resolve()
        if (!heardSpeech && now - started > startTimeoutMs) return resolve()
        if (now - started > maxMs) return resolve()
        requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    })

    recorder.start(250)
    await done
    const stopped = new Promise<void>((resolve) => (recorder.onstop = () => resolve()))
    if (recorder.state !== 'inactive') recorder.stop()
    await stopped
    stream.getTracks().forEach((t) => t.stop())
    source.disconnect()
    onLevel?.(0)

    if (this.cancelled || (!heardSpeech && !this.stopRequested)) return null
    return new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
  }
}
