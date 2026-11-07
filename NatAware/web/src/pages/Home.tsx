import { MapPin, Sparkles } from 'lucide-react'
import { greeting } from '../format'
import { AwarenessSection } from '../home/AwarenessSection'
import { NearYou, PlanCard, ProfileCard, RecurringCard, StatsStrip } from '../home/Cards'
import { ForecastSection } from '../home/ForecastSection'
import { GoalsSection } from '../home/GoalsSection'
import { NoticedSection } from '../home/NoticedSection'
import { usePrefs } from '../prefs'
import type { Dashboard } from '../types'

export function Home({ d, onAsk, refresh }: { d: Dashboard; onAsk: (q: string) => void; refresh: () => void }) {
  const { prefs, setPref } = usePrefs()
  const months = d.awareness.length
    ? `${new Date(d.today).toLocaleDateString('en-GB', { month: 'short' })}–${new Date(
        d.awareness.reduce((a, e) => (e.ends > a ? e.ends : a), d.today),
      ).toLocaleDateString('en-GB', { month: 'short' })}`
    : ''

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">NatBot · Awareness</p>
          <h1 className="page-title" id="page-title" tabIndex={-1}>
            {greeting()}, {d.account.first_name}
          </h1>
        </div>
        <div className="head-chips">
          <span className="chip">
            <MapPin size={16} aria-hidden="true" /> {d.account.city}, UK{months && ` · ${months}`}
          </span>
          <button type="button" className="chip" aria-pressed={prefs.plainEnglish} onClick={() => setPref('plainEnglish', !prefs.plainEnglish)}>
            Plain English
          </button>
        </div>
      </div>

      {d.narration.status === 'pending' && (
        <p className="banner" role="status">
          <Sparkles size={18} aria-hidden="true" /> NatBot is writing your insights in plain English…
        </p>
      )}

      <div className="stack">
        <StatsStrip d={d} />
        <GoalsSection goals={d.goals.goals} onAsk={onAsk} />
        <div className="grid-2">
          <ForecastSection forecast={d.forecast} onAsk={onAsk} />
          <NoticedSection insights={d.noticed} live={d.narration.status !== 'templates'} onAsk={onAsk} />
        </div>
        <AwarenessSection events={d.awareness} today={d.today} onChanged={refresh} onAsk={onAsk} />
        <div className="grid-2-even">
          <NearYou threats={d.threats} city={d.account.city} />
          <RecurringCard items={d.recurring} />
        </div>
        <div className="grid-2-even">
          <PlanCard plan={d.plan} onAsk={onAsk} />
          <ProfileCard profile={d.profile} budget={d.budget} />
        </div>
      </div>
    </>
  )
}
