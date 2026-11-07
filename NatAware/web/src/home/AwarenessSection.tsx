import { Check, MessageCircle } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import { EVENT_ICONS, ImpactBadge } from '../components/bits'
import { money, shortDate } from '../format'
import { usePrefs } from '../prefs'
import type { AwarenessEvent } from '../types'


export function AwarenessSection({
  events,
  today,
  onChanged,
  onAsk,
}: {
  events: AwarenessEvent[]
  today: string
  onChanged: () => void
  onAsk: (q: string) => void
}) {
  const { prefs } = usePrefs()
  const top = [...events].sort((a, b) => b.expected_extra - a.expected_extra)[0]
  const [selected, setSelected] = useState<string | undefined>(top?.id)
  const [saving, setSaving] = useState<string | null>(null)
  const [announce, setAnnounce] = useState('')

  if (!events.length) return null

  // Timeline: from the start of this month across the next four months.
  const t0 = new Date(today.slice(0, 8) + '01T00:00:00')
  const months = [0, 1, 2, 3].map((i) => new Date(t0.getFullYear(), t0.getMonth() + i, 1))
  const t1 = new Date(t0.getFullYear(), t0.getMonth() + 4, 1)
  const pos = (iso: string) => {
    const d = new Date(iso + 'T00:00:00').getTime()
    return Math.max(2, Math.min(98, ((d - t0.getTime()) / (t1.getTime() - t0.getTime())) * 100))
  }
  const todayPos = pos(today)

  const toggleSave = async (e: AwarenessEvent) => {
    setSaving(e.id)
    try {
      if (e.set_aside) {
        await api.removeSetAside(e.id)
        setAnnounce(`Stopped setting aside money for ${e.title}.`)
      } else {
        await api.setAside(e.id, e.weekly_save)
        setAnnounce(`Now setting aside ${money(e.weekly_save)} a week for ${e.title}.`)
      }
      onChanged()
    } finally {
      setSaving(null)
    }
  }

  return (
    <section className="card" aria-labelledby="aware-title">
      <div className="card-head">
        <h2 id="aware-title" className="card-title">
          Awareness for you
        </h2>
        <p className="card-sub">NatBot combines your history with what's happening near you</p>
      </div>

      <div className="timeline" role="group" aria-label="Timeline of upcoming costs">
        <div className="timeline-track" />
        <div className="timeline-past" style={{ width: `${todayPos}%` }} />
        <span className="timeline-today" style={{ left: `${todayPos}%` }} aria-hidden="true">
          Today
        </span>
        {months.map((m) => (
          <span
            key={m.toISOString()}
            className="timeline-month"
            style={{ left: `${Math.max(3, ((m.getTime() - t0.getTime()) / (t1.getTime() - t0.getTime())) * 100 + 3)}%` }}
            aria-hidden="true"
          >
            {m.toLocaleDateString('en-GB', { month: 'short' })}
          </span>
        ))}
        {events.map((e) => (
          <button
            key={e.id}
            type="button"
            className="timeline-dot"
            style={{ left: `${pos(e.in_progress ? today : e.starts)}%` }}
            aria-pressed={selected === e.id}
            aria-label={`${e.title}, ${e.in_progress ? 'happening now' : `from ${shortDate(e.starts)}`}`}
            onClick={() => setSelected(e.id)}
          />
        ))}
      </div>

      <div className="sr-only" aria-live="polite">
        {announce}
      </div>

      <div className="aware-grid">
        {events.map((e) => {
          const Icon = EVENT_ICONS[e.icon] ?? EVENT_ICONS.gift
          const isSel = selected === e.id
          const pct = Math.round(e.confidence * 100)
          return (
            <article key={e.id} className={`aware-card ${isSel ? 'selected' : ''}`} aria-labelledby={`aware-${e.id}`}>
              <div className="spread">
                <span className="aware-icon">
                  <Icon size={22} aria-hidden="true" />
                </span>
                <ImpactBadge impact={e.impact} />
              </div>
              <div>
                <h3 id={`aware-${e.id}`} className="aware-title">
                  <button
                    type="button"
                    onClick={() => setSelected(isSel ? undefined : e.id)}
                    aria-expanded={isSel}
                    style={{ all: 'unset', cursor: 'pointer' }}
                  >
                    {e.title}
                  </button>
                </h3>
                <p className="muted small">{e.window_label}</p>
              </div>
              <div>
                <div className="spread">
                  <span className="muted">Expected extra</span>
                  <strong className="tabular">~{money(e.expected_extra)}</strong>
                </div>
                <div className="meter" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Confidence" style={{ marginTop: '0.5rem' }}>
                  <span style={{ width: `${pct}%` }} />
                </div>
                <p className="muted small" style={{ marginTop: '0.35rem' }}>
                  {pct}% confidence
                </p>
              </div>

              {isSel && (
                <div className="why">
                  <h4>Why NatBot thinks this</h4>
                  <p>{prefs.plainEnglish ? e.plain : e.detail}</p>
                  {!prefs.plainEnglish && e.contributors.length > 0 && (
                    <p className="muted small">
                      Biggest jumps last time: {e.contributors.map((c) => `${c.category} (+${money(c.extra)})`).join(', ')}
                    </p>
                  )}
                  {prefs.plainEnglish && (
                    <>
                      <p>
                        <b>Your history:</b> {e.why.history}
                      </p>
                      {e.why.area && (
                        <p>
                          <b>Your area:</b> {e.why.area}
                        </p>
                      )}
                    </>
                  )}
                  <button type="button" className="link-btn" onClick={() => onAsk(`Tell me more about ${e.title.toLowerCase()} and how to prepare.`)}>
                    <MessageCircle size={15} aria-hidden="true" /> Ask NatBot
                  </button>
                </div>
              )}

              <button
                type="button"
                className={`btn btn-block ${e.set_aside ? 'btn-success' : 'btn-primary'}`}
                onClick={() => toggleSave(e)}
                disabled={saving === e.id}
                aria-pressed={!!e.set_aside}
              >
                {e.set_aside ? (
                  <>
                    <Check size={18} aria-hidden="true" /> Saving {money(e.set_aside.weekly)}/week
                  </>
                ) : (
                  <>Save {money(e.weekly_save)}/week</>
                )}
              </button>
            </article>
          )
        })}
      </div>
    </section>
  )
}
