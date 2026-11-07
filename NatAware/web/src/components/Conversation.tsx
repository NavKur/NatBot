import { Mic, MicOff, Send, Square } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { unlockAudio } from '../voice/audio'
import type { useNatBot } from '../voice/useNatBot'
import { ToolCard } from './ToolCard'

type Bot = ReturnType<typeof useNatBot>

const STATUS_TEXT: Record<string, string> = {
  listening: 'Listening… just start talking',
  hearing: "I'm listening. Pause when you're done.",
  transcribing: 'Getting that down…',
  thinking: 'NatBot is thinking…',
  speaking: 'NatBot is speaking',
}

interface Props {
  bot: Bot
  suggestions?: string[]
  placeholder?: string
  autoFocusInput?: boolean
  intro?: ReactNode
}

export function Conversation({ bot, suggestions = [], placeholder = 'Type a message', autoFocusInput, intro }: Props) {
  const [text, setText] = useState('')
  const [announce, setAnnounce] = useState('')
  const list = useRef<HTMLDivElement>(null)
  const listening = bot.status === 'listening' || bot.status === 'hearing'
  const busy = bot.status === 'thinking' || bot.status === 'transcribing'

  // Keep the newest message in view.
  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: 'smooth' })
  }, [bot.messages, bot.interim])

  // Screen readers hear each complete reply once (not every streamed fragment).
  const lastAnnounced = useRef<string | null>(null)
  useEffect(() => {
    const last = bot.messages[bot.messages.length - 1]
    if (last?.role === 'bot' && !last.pending && last.text && lastAnnounced.current !== last.id) {
      lastAnnounced.current = last.id
      setAnnounce(`NatBot says: ${last.text}`)
    }
  }, [bot.messages])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim() || busy) return
    unlockAudio()
    bot.interrupt()
    void bot.send(text.trim())
    setText('')
  }

  return (
    <div className="convo">
      <div className="messages" ref={list} role="log" aria-label="Conversation with NatBot" aria-live="off">
        {intro}
        {bot.messages.map((m) => (
          <div key={m.id} className={`msg ${m.role} ${m.error ? 'error' : ''}`}>
            {(m.text || m.pending) && (
              <div className="bubble">
                <span className="sr-only">{m.role === 'user' ? 'You said: ' : 'NatBot: '}</span>
                {m.text}
                {m.pending && !m.text && (
                  <span className="typing" aria-label="NatBot is typing">
                    <i />
                    <i />
                    <i />
                  </span>
                )}
              </div>
            )}
            {m.tools.map((t, i) => (
              <ToolCard key={i} event={t} />
            ))}
          </div>
        ))}
        {bot.interim && (
          <div className="msg user" aria-hidden="true">
            <div className="bubble" style={{ opacity: 0.7 }}>
              {bot.interim}
            </div>
          </div>
        )}
      </div>

      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announce}
      </div>

      <div className="composer">
        {suggestions.length > 0 && (
          <div className="suggestions" role="group" aria-label="Suggested questions">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                className="chip"
                disabled={busy}
                onClick={() => {
                  unlockAudio()
                  bot.interrupt()
                  void bot.send(s)
                }}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="status-line" aria-live="polite">
          {listening && (
            <span className="level" aria-hidden="true">
              {[0.6, 1, 0.75, 0.9, 0.5].map((k, i) => (
                <i key={i} style={{ height: `${4 + Math.round(bot.level * 16 * k)}px` }} />
              ))}
            </span>
          )}
          <span>{STATUS_TEXT[bot.status] ?? ''}</span>
          {bot.status === 'speaking' && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={bot.interrupt}>
              <Square size={14} aria-hidden="true" /> Stop speaking
            </button>
          )}
        </div>
        {bot.error && (
          <p className="error-text" role="alert">
            {bot.error}
          </p>
        )}

        <form className="composer-row" onSubmit={submit}>
          <button
            type="button"
            className={`mic-btn ${listening ? 'active' : ''}`}
            onClick={() => {
              unlockAudio()
              if (listening) bot.stopListening()
              else void bot.listen()
            }}
            disabled={!bot.canListen || busy}
            aria-pressed={listening}
            aria-label={
              !bot.canListen ? 'Voice input is not available in this browser' : listening ? "I'm done speaking" : 'Speak to NatBot'
            }
            title={!bot.canListen ? 'Voice input is not available here. Type instead.' : undefined}
          >
            {bot.canListen ? listening ? <Square size={20} aria-hidden="true" /> : <Mic size={22} aria-hidden="true" /> : <MicOff size={22} aria-hidden="true" />}
          </button>
          <label htmlFor="natbot-input" className="sr-only">
            Message NatBot
          </label>
          <input
            id="natbot-input"
            className="input"
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              if (bot.status === 'speaking' || listening) bot.interrupt()
            }}
            placeholder={placeholder}
            autoComplete="off"
            data-autofocus={autoFocusInput ? '' : undefined}
          />
          <button type="submit" className="icon-btn" aria-label="Send message" disabled={!text.trim() || busy}>
            <Send size={20} aria-hidden="true" />
          </button>
        </form>
      </div>
    </div>
  )
}
