import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

/** Accessibility and voice preferences, saved on this device. */
export interface Prefs {
  textSize: 'standard' | 'large' | 'largest'
  highContrast: boolean
  reduceMotion: boolean
  readableSpacing: boolean // extra letter / line spacing, helps many dyslexic readers
  plainEnglish: boolean // simplest wording on insight cards
  voiceReplies: boolean // NatBot reads replies aloud
  autoListen: boolean // start listening again after NatBot finishes speaking
}

const DEFAULTS: Prefs = {
  textSize: 'standard',
  highContrast: false,
  reduceMotion: typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
  readableSpacing: false,
  plainEnglish: true,
  voiceReplies: true,
  autoListen: true,
}

const KEY = 'nataware.prefs.v1'

interface PrefsContextValue {
  prefs: Prefs
  setPref: <K extends keyof Prefs>(key: K, value: Prefs[K]) => void
}

const PrefsContext = createContext<PrefsContextValue | null>(null)

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(() => {
    try {
      return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') }
    } catch {
      return DEFAULTS
    }
  })

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(prefs))
    const root = document.documentElement
    root.dataset.textSize = prefs.textSize
    root.dataset.contrast = prefs.highContrast ? 'high' : 'normal'
    root.dataset.motion = prefs.reduceMotion ? 'reduce' : 'full'
    root.dataset.spacing = prefs.readableSpacing ? 'readable' : 'normal'
  }, [prefs])

  const value = useMemo<PrefsContextValue>(
    () => ({ prefs, setPref: (key, value) => setPrefs((p) => ({ ...p, [key]: value })) }),
    [prefs],
  )
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

export function usePrefs() {
  const ctx = useContext(PrefsContext)
  if (!ctx) throw new Error('usePrefs outside PrefsProvider')
  return ctx
}
