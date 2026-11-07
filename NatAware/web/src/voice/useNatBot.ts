import { useCallback, useEffect, useRef, useState } from 'react'
import { api, streamChat } from '../api'
import { uid } from '../format'
import { usePrefs } from '../prefs'
import type { Capabilities, ChatMessage, Profile, ToolEvent } from '../types'
import { audioContext } from './audio'
import { BrowserRecognition, browserSttSupported } from './browserStt'
import { Recording, micSupported } from './recorder'
import { Speaker } from './speaker'

export type BotStatus = 'idle' | 'listening' | 'hearing' | 'transcribing' | 'thinking' | 'speaking'

interface Options {
  mode: 'coach' | 'onboarding'
  capabilities: Capabilities
  onTool?: (event: ToolEvent) => void
  onComplete?: (profile: Profile) => void
  /** Called just before the mic opens (e.g. to pause the wake-word listener). */
  onMicStart?: () => void
}

/**
 * One conversation with NatBot: text or voice in, streamed text (and speech) out.
 * Voice loop: listen -> transcribe -> stream reply (speaking sentence by sentence) -> listen again.
 */
export function useNatBot({ mode, capabilities, onTool, onComplete, onMicStart }: Options) {
  const { prefs } = usePrefs()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<BotStatus>('idle')
  const [level, setLevel] = useState(0)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [voiceMode, setVoiceMode] = useState(false) // true once the user has used the mic

  const sessionId = useRef<string | null>(null)
  const speaker = useRef<Speaker | null>(null)
  const recording = useRef<Recording | BrowserRecognition | null>(null)
  const busy = useRef(false)
  const abort = useRef<AbortController | null>(null)
  const prefsRef = useRef(prefs)
  prefsRef.current = prefs
  const voiceModeRef = useRef(voiceMode)
  voiceModeRef.current = voiceMode
  const handlers = useRef({ onTool, onComplete, onMicStart })
  handlers.current = { onTool, onComplete, onMicStart }

  const canListen = capabilities.speech_to_text ? micSupported() : browserSttSupported()

  if (!speaker.current) {
    speaker.current = new Speaker(capabilities.text_to_speech)
  }

  useEffect(() => {
    const s = speaker.current!
    s.useServerVoice = capabilities.text_to_speech
    s.onSpeakingChange = (speaking) => {
      if (speaking) setStatus('speaking')
      else setStatus((st) => (st === 'speaking' ? 'idle' : st))
    }
    return () => {
      s.stop()
      recording.current?.cancel()
      abort.current?.abort()
    }
  }, [capabilities.text_to_speech])

  const listenRef = useRef<() => void>(() => {})

  const send = useCallback(
    async (text: string, opts: { hidden?: boolean } = {}) => {
      if (busy.current) return
      busy.current = true
      setError(null)
      speaker.current?.stop()
      const botId = uid()
      setMessages((m) => [
        ...m,
        ...(opts.hidden || !text ? [] : [{ id: uid(), role: 'user' as const, text, tools: [] }]),
        { id: botId, role: 'bot', text: '', tools: [], pending: true },
      ])
      setStatus('thinking')
      const update = (fn: (m: ChatMessage) => ChatMessage) =>
        setMessages((all) => all.map((m) => (m.id === botId ? fn(m) : m)))

      abort.current = new AbortController()
      let completedProfile: Profile | null = null
      await streamChat(
        { message: text, session_id: sessionId.current, mode },
        {
          onSession: (id) => (sessionId.current = id),
          onSentence: (sentence) => {
            update((m) => ({ ...m, text: m.text ? `${m.text} ${sentence}` : sentence }))
            if (prefsRef.current.voiceReplies) speaker.current?.say(sentence)
          },
          onTool: (event) => {
            update((m) => ({ ...m, tools: [...m.tools, event] }))
            handlers.current.onTool?.(event)
          },
          onDone: (data) => {
            update((m) => ({ ...m, text: m.text || data.reply, pending: false }))
            if (data.complete && data.profile) completedProfile = data.profile
          },
          onError: (message) => {
            update((m) => ({ ...m, pending: false, error: true, text: m.text || "Sorry, I couldn't reply just then." }))
            setError(message)
          },
        },
        abort.current.signal,
      ).catch((e: unknown) => {
        if ((e as Error).name !== 'AbortError') {
          update((m) => ({ ...m, pending: false, error: true, text: m.text || "Sorry, I couldn't reach NatBot." }))
          setError(String((e as Error).message || e))
        }
      })
      busy.current = false
      setStatus(speaker.current?.speaking ? 'speaking' : 'idle')

      if (completedProfile) {
        await speaker.current?.whenIdle()
        handlers.current.onComplete?.(completedProfile)
        return
      }
      // Hands-free: once NatBot has finished talking, listen for the reply.
      if (voiceModeRef.current && prefsRef.current.autoListen && canListen) {
        await speaker.current?.whenIdle()
        if (!busy.current) listenRef.current()
      }
    },
    [mode, canListen],
  )

  const listen = useCallback(async () => {
    if (busy.current || recording.current) return
    speaker.current?.stop()
    setVoiceMode(true)
    setError(null)
    setInterim('')
    setStatus('listening')
    handlers.current.onMicStart?.()
    try {
      let text: string | null = null
      // Whisper needs our silence detector, which needs audio unlocked by a click. If NatBot was
      // woken by voice before any click, use the browser's recogniser for this turn instead.
      const audioReady = audioContext().state === 'running'
      if (capabilities.speech_to_text && micSupported() && (audioReady || !browserSttSupported())) {
        const rec = new Recording({ onLevel: setLevel, onSpeechStart: () => setStatus('hearing') })
        recording.current = rec
        const blob = await rec.result
        recording.current = null
        if (!blob) {
          setStatus('idle')
          return
        }
        setStatus('transcribing')
        text = (await api.transcribe(blob)).text
      } else {
        const rec = new BrowserRecognition((t) => {
          setInterim(t)
          setStatus('hearing')
        })
        recording.current = rec
        text = await rec.result
        recording.current = null
      }
      setInterim('')
      if (text && text.trim()) await send(text.trim())
      else {
        setStatus('idle')
        setError("I didn't catch that. Try again, or type your answer.")
      }
    } catch (e) {
      recording.current = null
      setStatus('idle')
      const name = (e as Error).name
      setError(
        name === 'NotAllowedError'
          ? 'Microphone access is blocked. Allow it in your browser settings, or type instead.'
          : `Voice didn't work: ${(e as Error).message || e}. You can type instead.`,
      )
    }
  }, [capabilities.speech_to_text, send])
  listenRef.current = listen

  /** Finish speaking now (keep what was said). */
  const stopListening = useCallback(() => recording.current?.stop(), [])

  /** Stop everything: recording, speech and the hands-free loop. */
  const interrupt = useCallback(() => {
    recording.current?.cancel()
    recording.current = null
    speaker.current?.stop()
    setVoiceMode(false)
    setStatus(busy.current ? 'thinking' : 'idle')
  }, [])

  const reset = useCallback(() => {
    interrupt()
    abort.current?.abort()
    busy.current = false
    sessionId.current = null
    setMessages([])
    setStatus('idle')
  }, [interrupt])

  return {
    messages,
    status,
    level,
    interim,
    error,
    canListen,
    voiceMode,
    send,
    listen,
    stopListening,
    interrupt,
    reset,
    setError,
    enableVoice: () => setVoiceMode(true),
  }
}
