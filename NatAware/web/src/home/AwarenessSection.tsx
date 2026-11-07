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
  const [selectedId, setSelectedId] = useState<string | undefined>(top?.id)
  const [saving, setSaving] = useState<string | null>(null)
  const [announce, setAnnounce] = useState('')

  if (!events.length) return null
  const selected = events.find((e) => e.id === selectedId)

  // Timeline: from the start of this month across the next four months.
  const t0 = new Date(today.slice(0, 8) + '01T00:00:00')
  const t1 = new Date(t0.getFullYear(), t0.getMonth() + 4, 1)
  const span = t1.getTime() - t0.getTime()
  const pos = (iso: string) => Math.max(2, Math.min(98, ((new Date(iso + 'T00:00:00').getTime() - t0.getTime()) / span) * 100))
  const months = [0, 1, 2, 3].map((i) => new Date(t0.getFullYear(), t0.getMonth() + i, 1))
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
        <p className="card-sub">Your history plus what's happening near you</p>
      </div>

      <div className="timeline" aria-hidden="true">
        <div className="timeline-track" />
        <div className="timeline-past" style={{ width: `${todayPos}%` }} />
        <span className="timeline-today" style={{ left: `${todayPos}%` }}>
          Today
        </span>
        {months.map((m) => (
          <span key={m.toISOString()} className="timeline-month" style={{ left: `${Math.max(3, ((m.getTime() - t0.getTime()) / span) * 100 + 3)}%` }}>
            {m.toLocaleDateString('en-GB', { month: 'short' })}
          </span>
        ))}
        {events.map((e, i) => {
          const base = pos(e.in_progress ? today : e.starts)
          const clash = events.slice(0, i).filter((o) => Math.abs(pos(o.in_progress ? today : o.starts) - base) < 2.5).length
          return (
            <span
              key={e.id}
              className={`timeline-dot ${selectedId === e.id ? 'on' : ''}`}
              style={{ left: `${Math.min(98, base + clash * 2.4)}%` }}
            />
          )
        })}
      </div>

      <div className="sr-only" aria-live="polite">
        {announce}
      </div>

      <ul className="aware-row" aria-label="Upcoming costs">
        {events.map((e) => {
          const Icon = EVENT_ICONS[e.icon] ?? EVENT_ICONS.gift
          const isSel = selectedId === e.id
          const pct = Math.round(e.confidence * 100)
          return (
            <li key={e.id} className={`aware-card ${isSel ? 'selected' : ''}`} aria-labelledby={`aware-${e.id}`}>
              <div className="spread">
                <span className="aware-icon">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <ImpactBadge impact={e.impact} />
              </div>
              <button
                type="button"
                className="aware-open"
                id={`aware-${e.id}`}
                aria-expanded={isSel}
                aria-controls="aware-why"
                onClick={() => setSelectedId(isSel ? undefined : e.id)}
              >
                <span className="aware-title">{e.title}</span>
                <span className="muted small">{e.in_progress ? 'Happening now' : `From ${shortDate(e.starts)}`}</span>
              </button>
              <div className="spread small">
                <span className="muted">Expected extra</span>
                <strong className="tabular">~{money(e.expected_extra)}</strong>
              </div>
              <div className="meter" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${pct}% confidence`}>
                <span style={{ width: `${pct}%` }} />
              </div>
              <button
                type="button"
                className={`btn btn-sm btn-block ${e.set_aside ? 'btn-success' : 'btn-primary'}`}
                onClick={() => toggleSave(e)}
                disabled={saving === e.id}
                aria-pressed={!!e.set_aside}
              >
                {e.set_aside ? (
                  <>
                    <Check size={16} aria-hidden="true" /> Saving {money(e.set_aside.weekly)}/wk
                  </>
                ) : (
                  <>Save {money(e.weekly_save)}/week</>
                )}
              </button>
            </li>
          )
        })}
      </ul>

      {selected && (
        <div className="why" id="aware-why" aria-live="polite">
          <h3>Why NatBot thinks this: {selected.title}</h3>
          <p>{selected.plain}</p>
          {!prefs.plainEnglish && <p className="muted">{selected.detail}</p>}
          <div className="why-grid">
            <p>
              <b>Your history:</b> {selected.why.history}
            </p>
            {selected.why.area && (
              <p>
                <b>Your area:</b> {selected.why.area}
              </p>
            )}
          </div>
          <p className="muted small">
            {selected.window_label} · {Math.round(selected.confidence * 100)}% confidence
          </p>
          <button type="button" className="link-btn" onClick={() => onAsk(`How should I prepare for ${selected.title.toLowerCase()}?`)}>
            <MessageCircle size={15} aria-hidden="true" /> Ask NatBot about {selected.title.toLowerCase()}
          </button>
        </div>
      )}
    </section>
  )
}
