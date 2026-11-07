import { Accessibility, Bell, ChartColumn, FileText, House, Repeat, Search, X, Zap } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api'
import { usePrefs } from '../prefs'
import type { AppState, Nudge } from '../types'
import type { useNatBot } from '../voice/useNatBot'
import { Conversation } from './Conversation'
import { Dialog } from './Dialog'
import { Logo, Orb, Switch } from './bits'

export type Route = 'home' | 'spending' | 'recurring' | 'statements'

export function Header({
  state,
  nudges,
  onSearch,
  onOpenSettings,
}: {
  state: AppState
  nudges: Nudge[]
  onSearch: (q: string) => void
  onOpenSettings: () => void
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const seenKey = 'nataware.nudges.seen'
  const [seen, setSeen] = useState(() => localStorage.getItem(seenKey) || '')
  const unseen = nudges.length > 0 && nudges[0].id !== seen
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    if (nudges[0]) {
      localStorage.setItem(seenKey, nudges[0].id)
      setSeen(nudges[0].id)
    }
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open, nudges])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSearch(q.trim())
  }
  const initials = state.account.display_name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Logo />
        <form className="search" role="search" onSubmit={submit}>
          <Search size={18} aria-hidden="true" />
          <label htmlFor="global-search" className="sr-only">
            Search payments and payees
          </label>
          <input
            id="global-search"
            className="input"
            type="search"
            placeholder="Search payments, payees…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </form>
        <div className="topbar-actions">
          <button type="button" className="icon-btn" onClick={onOpenSettings} aria-label="Accessibility and voice settings">
            <Accessibility size={22} aria-hidden="true" />
          </button>
          <div ref={box} style={{ position: 'relative' }}>
            <button
              type="button"
              className="icon-btn"
              aria-label={`Notifications${unseen ? ', new' : ''}`}
              aria-expanded={open}
              aria-haspopup="true"
              onClick={() => setOpen((o) => !o)}
            >
              <Bell size={22} aria-hidden="true" />
              {unseen && <span className="dot-badge" aria-hidden="true" />}
            </button>
            {open && (
              <div className="popover" role="region" aria-label="Notifications from NatBot">
                <strong>From NatBot</strong>
                {nudges.length === 0 && <p className="muted small">No nudges yet. NatBot will check in when it matters.</p>}
                {nudges.map((n) => (
                  <div key={n.id} className="nudge">
                    <strong>{n.title}</strong>
                    <span>{n.message}</span>
                    <span className="muted small">
                      {n.trigger} nudge · {new Date(n.created_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="user-chip">
            <span className="avatar" aria-hidden="true">
              {initials}
            </span>
            <span className="who">
              <span className="name" style={{ display: 'block' }}>
                {state.account.display_name}
              </span>
              <span className="sub">{state.account.account_type}</span>
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}

const NAV: { route: Route; label: string; Icon: typeof House }[] = [
  { route: 'home', label: 'Home', Icon: House },
  { route: 'spending', label: 'Spending', Icon: ChartColumn },
  { route: 'recurring', label: 'Recurring', Icon: Repeat },
  { route: 'statements', label: 'Statements', Icon: FileText },
]

export function BottomNav({ route, onNatBot }: { route: Route; onNatBot: () => void }) {
  return (
    <nav className="bottom-nav" aria-label="Main">
      <div className="bottom-nav-inner">
        {NAV.map(({ route: r, label, Icon }) => (
          <a key={r} href={`#/${r}`} className="nav-item" aria-current={route === r ? 'page' : undefined}>
            <Icon size={22} aria-hidden="true" />
            {label}
          </a>
        ))}
        <button type="button" className="btn btn-primary natbot-btn" onClick={onNatBot} aria-label="Talk to NatBot">
          <Zap size={20} aria-hidden="true" />
          <span>NatBot</span>
        </button>
      </div>
    </nav>
  )
}

const SUGGESTIONS = [
  'How can I reach my house deposit faster?',
  'What will December cost me?',
  'Highlight my takeaways last month',
  'Will I make it to payday?',
  'Any money worries coming up near me?',
  'I just spent £28 on Deliveroo',
]

export function NatBotPanel({
  open,
  onClose,
  bot,
  firstName,
}: {
  open: boolean
  onClose: () => void
  bot: ReturnType<typeof useNatBot>
  firstName: string
}) {
  return (
    <Dialog open={open} onClose={onClose} labelledBy="natbot-title">
      <div className="drawer-head">
        <Orb status={bot.status} size={44} />
        <div style={{ flex: 1 }}>
          <h2 id="natbot-title">NatBot</h2>
          <p className="muted small">Your money coach · speak or type</p>
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close NatBot">
          <X size={22} aria-hidden="true" />
        </button>
      </div>
      <Conversation
        bot={bot}
        autoFocusInput
        placeholder="Ask about your money"
        suggestions={bot.messages.length < 2 ? SUGGESTIONS : SUGGESTIONS.slice(0, 3)}
        intro={
          bot.messages.length === 0 ? (
            <div className="msg bot">
              <div className="bubble">
                Hi {firstName}. Ask me anything about your money: where it went, what's coming up, or how to hit your goals
                sooner. Tap the mic to talk, or type below.
              </div>
            </div>
          ) : null
        }
      />
    </Dialog>
  )
}

export function SettingsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { prefs, setPref } = usePrefs()
  const [resetting, setResetting] = useState(false)
  return (
    <Dialog open={open} onClose={onClose} labelledBy="settings-title" variant="modal">
      <div className="spread">
        <h2 id="settings-title" className="card-title">
          Accessibility and voice
        </h2>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close settings">
          <X size={22} aria-hidden="true" />
        </button>
      </div>
      <p className="muted small">Saved on this device. Make NatAware work the way you do.</p>

      <div className="settings-group" role="group" aria-labelledby="text-size-label">
        <div className="toggle-row">
          <span id="text-size-label" style={{ fontWeight: 600 }}>
            Text size
          </span>
          <div className="segmented">
            {(['standard', 'large', 'largest'] as const).map((s, i) => (
              <button
                key={s}
                type="button"
                aria-pressed={prefs.textSize === s}
                onClick={() => setPref('textSize', s)}
                aria-label={`${s[0].toUpperCase()}${s.slice(1)} text`}
                style={{ fontSize: `${0.85 + i * 0.15}rem` }}
              >
                A
              </button>
            ))}
          </div>
        </div>
        <Switch id="pref-contrast" checked={prefs.highContrast} onChange={(v) => setPref('highContrast', v)} label="High contrast" description="Stronger colours and borders." />
        <Switch id="pref-spacing" checked={prefs.readableSpacing} onChange={(v) => setPref('readableSpacing', v)} label="Easier reading spacing" description="More space between letters and lines. Helps many people with dyslexia." />
        <Switch id="pref-motion" checked={prefs.reduceMotion} onChange={(v) => setPref('reduceMotion', v)} label="Reduce motion" description="Turns off animations." />
        <Switch id="pref-plain" checked={prefs.plainEnglish} onChange={(v) => setPref('plainEnglish', v)} label="Plain English" description="Shortest, simplest wording. Turn off to see the numbers behind each insight." />
      </div>

      <div className="settings-group">
        <h3>Voice</h3>
        <Switch id="pref-voice" checked={prefs.voiceReplies} onChange={(v) => setPref('voiceReplies', v)} label="NatBot speaks replies" description="Replies are always shown as text too." />
        <Switch id="pref-listen" checked={prefs.autoListen} onChange={(v) => setPref('autoListen', v)} label="Hands-free conversation" description="After NatBot speaks, it listens for your reply automatically." />
      </div>

      <div className="settings-group">
        <h3>Demo</h3>
        <div className="toggle-row">
          <span>
            <span style={{ fontWeight: 600, display: 'block' }}>Start again</span>
            <span className="desc">Reset the demo data and go back to the first-run interview.</span>
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={resetting}
            onClick={async () => {
              setResetting(true)
              await api.reset()
              localStorage.removeItem('nataware.nudges.seen')
              window.location.hash = '#/home'
              window.location.reload()
            }}
          >
            Reset demo
          </button>
        </div>
      </div>
    </Dialog>
  )
}
