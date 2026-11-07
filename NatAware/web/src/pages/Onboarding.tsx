import { ArrowRight, Clock, Keyboard, Lock, Mic, Settings2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { GOAL_ICONS, Logo, Orb } from '../components/bits'
import { Conversation } from '../components/Conversation'
import { money } from '../format'
import type { AppState, Profile } from '../types'
import { unlockAudio } from '../voice/audio'
import { useNatBot } from '../voice/useNatBot'

interface Props {
  state: AppState
  onDone: () => void
  onSkip: () => void
  onOpenSettings: () => void
}

export function Onboarding({ state, onDone, onSkip, onOpenSettings }: Props) {
  const [stage, setStage] = useState<'welcome' | 'chat' | 'reveal'>('welcome')
  const [profile, setProfile] = useState<Profile | null>(null)
  const bot = useNatBot({
    mode: 'onboarding',
    capabilities: state.capabilities,
    onComplete: (p) => {
      setProfile(p)
      setStage('reveal')
    },
  })
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    heading.current?.focus()
  }, [stage])

  const start = (voice: boolean) => {
    if (voice) {
      unlockAudio(true)
      bot.enableVoice()
    } else unlockAudio()
    setStage('chat')
    void bot.send('', { hidden: true })
  }

  const answered = bot.messages.filter((m) => m.role === 'user').length
  const firstName = state.account.first_name

  return (
    <div className="onboard">
      <a className="skip-link" href="#onboard-main">
        Skip to content
      </a>
      <header className="onboard-top">
        <Logo />
        <button type="button" className="btn btn-ghost" onClick={onOpenSettings}>
          <Settings2 size={18} aria-hidden="true" /> Accessibility
        </button>
      </header>

      <main id="onboard-main" className="onboard-main" tabIndex={-1}>
        {stage === 'welcome' && (
          <section className="welcome" aria-labelledby="welcome-title">
            <Orb size={148} />
            <h1 id="welcome-title" ref={heading} tabIndex={-1}>
              Hi {firstName}, I'm NatBot
            </h1>
            <p>
              I'll ask you three quick questions about how you handle money. There are no right or wrong answers. Then
              I'll look at your spending, what's coming up, and build a plan that fits you.
            </p>
            {state.capabilities.chat ? (
              <div className="welcome-actions">
                <button type="button" className="btn btn-primary" onClick={() => start(true)} disabled={!bot.canListen}>
                  <Mic size={20} aria-hidden="true" /> Start talking
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => start(false)}>
                  <Keyboard size={20} aria-hidden="true" /> Type instead
                </button>
              </div>
            ) : (
              <p className="banner" role="status">
                NatBot's conversation needs an Anthropic API key on the server. You can still explore with a demo
                profile.
              </p>
            )}
            <div className="promise">
              <span>
                <Clock size={16} aria-hidden="true" /> About 2 minutes
              </span>
              <span>
                <Mic size={16} aria-hidden="true" /> Speak or type, switch any time
              </span>
              <span>
                <Lock size={16} aria-hidden="true" /> Demo data only
              </span>
            </div>
            <button type="button" className="btn btn-ghost" onClick={onSkip}>
              Skip and explore with a demo profile
            </button>
          </section>
        )}

        {stage === 'chat' && (
          <section className="onboard-convo" aria-labelledby="chat-title">
            <div className="onboard-progress">
              <Orb status={bot.status} size={44} />
              <div style={{ flex: 1 }}>
                <h1 id="chat-title" ref={heading} tabIndex={-1} style={{ fontSize: '1.1rem' }}>
                  Getting to know you
                </h1>
                <p className="muted small" aria-live="polite">
                  {answered >= 3 ? 'Building your profile…' : `Question ${Math.min(answered + 1, 3)} of 3`}
                </p>
              </div>
              <div className="steps" aria-hidden="true">
                {[0, 1, 2].map((i) => (
                  <i key={i} className={i < answered ? 'done' : ''} />
                ))}
              </div>
            </div>
            <Conversation bot={bot} placeholder="Type your answer" />
          </section>
        )}

        {stage === 'reveal' && profile && (
          <section className="reveal" aria-labelledby="reveal-title">
            <div className="reveal-hero">
              <Orb size={84} />
              <p className="eyebrow">Thanks, {firstName}</p>
              <h1 id="reveal-title" ref={heading} tabIndex={-1} className="page-title">
                Here's what I'll help you with
              </h1>
            </div>

            {profile.goals.length > 0 && (
              <div className="card">
                <h2 className="card-title">Your goals</h2>
                <ul className="list" style={{ marginTop: '0.5rem' }}>
                  {profile.goals.map((g) => {
                    const Icon = GOAL_ICONS[g.kind] ?? GOAL_ICONS.other
                    return (
                      <li key={g.id}>
                        <span className="row">
                          <Icon size={20} aria-hidden="true" /> {g.name}
                        </span>
                        <span className="amount">{money(g.target)}</span>
                      </li>
                    )
                  })}
                </ul>
                <p className="muted small">Picked up from what you told me. You can change these any time by telling NatBot.</p>
              </div>
            )}

            <div className="card">
              <h2 className="card-title">A healthy split for you</h2>
              <p className="muted small" style={{ margin: '0.25rem 0 0.9rem' }}>
                Of every pound you earn, here's the balance we'll work towards together, a step at a time.
              </p>
              <BaselineBar baseline={profile.optimal_baseline} />
            </div>

            <button type="button" className="btn btn-primary" style={{ justifySelf: 'center', minHeight: 56 }} onClick={onDone}>
              See my dashboard <ArrowRight size={20} aria-hidden="true" />
            </button>
          </section>
        )}
      </main>
    </div>
  )
}

export function BaselineBar({ baseline }: { baseline: Profile['optimal_baseline'] }) {
  const parts = [
    { k: 'Needs', v: baseline.needs, c: '#4b1d7a' },
    { k: 'Wants', v: baseline.wants, c: '#6e3fd0' },
    { k: 'Savings', v: baseline.savings, c: '#1d6f4f' },
  ]
  return (
    <div>
      <div className="baseline-bar" role="img" aria-label={parts.map((p) => `${p.k} ${p.v}%`).join(', ')}>
        {parts.map((p) => (
          <span key={p.k} style={{ width: `${p.v}%`, background: p.c }}>
            {p.v >= 12 ? `${p.v}%` : ''}
          </span>
        ))}
      </div>
      <div className="legend" style={{ marginTop: '0.6rem' }} aria-hidden="true">
        {parts.map((p) => (
          <span key={p.k} className="legend-item">
            <span className="key-band" style={{ background: p.c }} /> {p.k} {p.v}%
          </span>
        ))}
      </div>
    </div>
  )
}
