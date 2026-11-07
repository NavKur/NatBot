import { LoaderCircle } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Orb } from './components/bits'
import { BottomNav, Header, NatBotPanel, SettingsPanel, WakeOptIn, type Route } from './components/Shell'
import { Home } from './pages/Home'
import { Onboarding } from './pages/Onboarding'
import { PlanPage } from './pages/PlanPage'
import { RecurringPage } from './pages/RecurringPage'
import { Spending } from './pages/Spending'
import { Statements } from './pages/Statements'
import type { AppState, Dashboard, ToolEvent } from './types'
import { audioContext, unlockAudio } from './voice/audio'
import { useNatBot } from './voice/useNatBot'
import { WakeWordListener, chime, wakeWordSupported, type WakeState } from './voice/wakeWord'
import { usePrefs } from './prefs'

const ROUTES: Route[] = ['home', 'spending', 'plan', 'recurring', 'statements']

function parseHash(): { route: Route; q: string } {
  const [path, query] = window.location.hash.replace(/^#\/?/, '').split('?')
  const route = (ROUTES.includes(path as Route) ? path : 'home') as Route
  return { route, q: new URLSearchParams(query).get('q') ?? '' }
}

export default function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const load = useCallback(() => {
    setLoadError(null)
    api.state().then(setState).catch((e) => setLoadError(String(e.message || e)))
  }, [])
  useEffect(load, [load])

  if (loadError) {
    return (
      <div className="center-screen">
        <div className="stack" style={{ justifyItems: 'center' }}>
          <Orb size={72} />
          <h1 className="page-title">NatAware can't reach its server</h1>
          <p className="muted">
            Start the API with <code>uvicorn nataware.api.main:app --reload</code>, then try again.
          </p>
          <button type="button" className="btn btn-primary" onClick={load}>
            Try again
          </button>
        </div>
      </div>
    )
  }
  if (!state) {
    return (
      <div className="center-screen" role="status">
        <LoaderCircle className="spinner" size={32} aria-label="Loading NatAware" />
      </div>
    )
  }

  return (
    <>
      {state.onboarded ? (
        <Shell state={state} onOpenSettings={() => setSettingsOpen(true)} />
      ) : (
        <Onboarding
          state={state}
          onDone={load}
          onSkip={() => api.skipOnboarding().then(setState)}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  )
}

const MUTATING_TOOLS = new Set(['log_transaction', 'set_aside_for_event', 'update_goal', 'highlight_transactions'])

function Shell({ state, onOpenSettings }: { state: AppState; onOpenSettings: () => void }) {
  const [{ route, q }, setLocation] = useState(parseHash)
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [dashError, setDashError] = useState<string | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [version, setVersion] = useState(0)
  const polls = useRef(0)
  const mainRef = useRef<HTMLElement>(null)

  const refresh = useCallback(() => {
    api
      .dashboard()
      .then((d) => {
        setDash(d)
        setDashError(null)
      })
      .catch((e) => setDashError(String(e.message || e)))
    setVersion((v) => v + 1)
  }, [])

  useEffect(refresh, [refresh])

  // Claude writes the insight wording in the background; pick it up when it's ready.
  useEffect(() => {
    if (dash?.narration.status !== 'pending' || polls.current > 10) return
    const t = setTimeout(() => {
      polls.current++
      api.dashboard().then(setDash).catch(() => {})
    }, 4000)
    return () => clearTimeout(t)
  }, [dash])

  useEffect(() => {
    const onHash = () => {
      setLocation(parseHash())
      requestAnimationFrame(() => document.getElementById('page-title')?.focus())
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const onTool = useCallback(
    (e: ToolEvent) => {
      if (MUTATING_TOOLS.has(e.tool)) refresh()
    },
    [refresh],
  )
  const { prefs, setPref } = usePrefs()
  const wake = useRef<WakeWordListener | null>(null)
  const [wakeState, setWakeState] = useState<WakeState>('off')
  const bot = useNatBot({ mode: 'coach', capabilities: state.capabilities, onTool, onMicStart: () => wake.current?.pause() })
  const botRef = useRef(bot)
  botRef.current = bot

  // "Hey NatBot": open the panel, then either answer what followed the phrase or start listening.
  const onWake = useCallback((rest: string) => {
    const b = botRef.current
    chime(audioContext())
    setPanelOpen(true)
    b.enableVoice()
    if (rest.split(/\s+/).filter(Boolean).length >= 2) void b.send(rest)
    else void b.listen()
  }, [])

  useEffect(() => {
    wake.current = new WakeWordListener((rest) => onWake(rest), setWakeState)
    return () => wake.current?.stop()
  }, [onWake])

  useEffect(() => {
    if (!wake.current) return
    if (prefs.wakeWord && wakeWordSupported()) wake.current.start()
    else wake.current.stop()
  }, [prefs.wakeWord])

  // Pause while NatBot is listening, thinking or talking; resume after a quiet moment.
  useEffect(() => {
    if (!wake.current || !prefs.wakeWord) return
    if (bot.status !== 'idle') {
      wake.current.pause()
      return
    }
    const t = setTimeout(() => wake.current?.resume(), 1500)
    return () => clearTimeout(t)
  }, [bot.status, prefs.wakeWord])

  const ask = useCallback(
    (question: string) => {
      unlockAudio()
      setPanelOpen(true)
      bot.interrupt()
      void bot.send(question)
    },
    [bot],
  )

  const closePanel = () => {
    bot.interrupt()
    setPanelOpen(false)
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main" onClick={(e) => {
        e.preventDefault()
        mainRef.current?.focus()
      }}>
        Skip to main content
      </a>
      <Header
        state={state}
        nudges={dash?.nudges ?? []}
        onOpenSettings={onOpenSettings}
        wakeState={wakeState}
        onWakeOff={() => setPref('wakeWord', false)}
        onSearch={(text) => {
          window.location.hash = `#/spending${text ? `?q=${encodeURIComponent(text)}` : ''}`
        }}
      />

      <main id="main" ref={mainRef} tabIndex={-1}>
        {route === 'home' &&
          (dash ? (
            <Home d={dash} onAsk={ask} refresh={refresh} />
          ) : dashError ? (
            <p className="banner" role="alert">
              Couldn't load your dashboard: {dashError}
            </p>
          ) : (
            <div className="center-screen" style={{ minHeight: '50vh' }} role="status">
              <LoaderCircle className="spinner" size={28} aria-label="Loading your dashboard" />
            </div>
          ))}
        {route === 'spending' && <Spending today={state.today} query={q} version={version} />}
        {route === 'plan' && (dash ? <PlanPage d={dash} onAsk={ask} /> : null)}
        {route === 'recurring' && <RecurringPage onAsk={ask} version={version} />}
        {route === 'statements' && <Statements onUploaded={refresh} />}
      </main>

      {!panelOpen && (
        <button
          type="button"
          className="fab-orb"
          onClick={() => {
            unlockAudio()
            setPanelOpen(true)
          }}
          aria-label="Open NatBot"
        >
          <Orb status={bot.status} />
        </button>
      )}
      <BottomNav
        route={route}
        onNatBot={() => {
          unlockAudio()
          setPanelOpen(true)
        }}
      />
      <NatBotPanel open={panelOpen} onClose={closePanel} bot={bot} firstName={state.account.first_name} />
      {!prefs.wakeAsked && wakeWordSupported() && dash && !panelOpen && (
        <WakeOptIn
          onAnswer={(yes) => {
            if (yes) unlockAudio(true)
            setPref('wakeWord', yes)
            setPref('wakeAsked', true)
          }}
        />
      )}
    </div>
  )
}
