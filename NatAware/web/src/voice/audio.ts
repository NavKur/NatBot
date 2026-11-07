/**
 * Browsers only let pages use audio after a user gesture. Call `unlockAudio()` inside a click
 * handler (e.g. "Start talking", the mic button) so later hands-free listening and playback,
 * which happen outside a click, still work.
 */
let ctx: AudioContext | null = null

export function audioContext(): AudioContext {
  if (!ctx) ctx = new AudioContext()
  return ctx
}

export function unlockAudio(askForMic = false): void {
  try {
    void audioContext().resume()
    // A silent buffer primes playback on Safari / iOS.
    const c = audioContext()
    const src = c.createBufferSource()
    src.buffer = c.createBuffer(1, 1, 22050)
    src.connect(c.destination)
    src.start(0)
  } catch {
    /* audio unsupported */
  }
  if (askForMic && navigator.mediaDevices?.getUserMedia) {
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((s) => s.getTracks().forEach((t) => t.stop()))
      .catch(() => {
        /* the mic button will explain if access is blocked */
      })
  }
}
