/**
 * Fallback speech-to-text using the browser's own recogniser (Chrome, Edge, Safari),
 * used when the server has no Whisper key. Ends automatically when the speaker pauses.
 */

type Recognition = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: any) => void) | null
  onerror: ((e: any) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

function ctor(): (new () => Recognition) | null {
  const w = window as any
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}

export function browserSttSupported(): boolean {
  return typeof window !== 'undefined' && !!ctor()
}

export class BrowserRecognition {
  readonly result: Promise<string | null>
  private rec: Recognition | null = null

  constructor(onInterim?: (text: string) => void) {
    this.result = new Promise((resolve) => {
      const Ctor = ctor()
      if (!Ctor) return resolve(null)
      const rec = new Ctor()
      this.rec = rec
      rec.lang = 'en-GB'
      rec.interimResults = true
      rec.continuous = false
      let finalText = ''
      rec.onresult = (e: any) => {
        let interim = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i]
          if (r.isFinal) finalText += r[0].transcript
          else interim += r[0].transcript
        }
        onInterim?.((finalText + interim).trim())
      }
      rec.onerror = () => resolve(finalText.trim() || null)
      rec.onend = () => resolve(finalText.trim() || null)
      rec.start()
    })
  }

  stop() {
    this.rec?.stop()
  }

  cancel() {
    this.rec?.abort()
  }
}
