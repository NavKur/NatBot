import { ArrowRight, Repeat, Target } from 'lucide-react'
import { CAPACITY_TEXT, TENDENCY_TEXT, shortName } from '../archetypes'
import { money, shortDate } from '../format'
import type { Budget, Dashboard, Plan, Profile, Recurring, Threat } from '../types'

export function StatsStrip({ d }: { d: Dashboard }) {
  const mtd = d.stats.month_to_date
  const wb = d.stats.winter_buffer
  const up = (mtd.change_pct ?? 0) > 0
  return (
    <section className="card stats" aria-label="This month at a glance">
      <div className="stat">
        <span className="stat-label">Spent this month</span>
        <span className="stat-value">{money(mtd.spent)}</span>
        {mtd.change_pct !== null && (
          <span className={`stat-note ${up ? 'warn' : 'good'}`}>
            {up ? '+' : ''}
            {mtd.change_pct}% vs {mtd.previous_month_label} at this point
          </span>
        )}
      </div>
      <div className="stat">
        <span className="stat-label">Committed monthly</span>
        <span className="stat-value">{money(d.stats.committed.total)}</span>
        <span className="stat-note">{d.stats.committed.count} regular payments</span>
      </div>
      <div className="stat">
        <span className="stat-label">Seasonal alerts</span>
        <span className="stat-value">{d.stats.seasonal_alerts}</span>
        <span className="stat-note">for you in {d.account.city}</span>
      </div>
      <div className="stat">
        <span className="stat-label">Winter buffer</span>
        <span className="stat-value">{money(wb.weekly)}/wk</span>
        <span className="stat-note">of {money(wb.suggested_weekly)}/wk suggested</span>
      </div>
    </section>
  )
}

export function NearYou({ threats, city }: { threats: Threat[]; city: string }) {
  const max = Math.max(...threats.map((t) => t.estimated_dollar_burden), 1)
  return (
    <section className="card" aria-labelledby="near-title">
      <div className="card-head">
        <h2 id="near-title" className="card-title">
          Near you right now
        </h2>
        <span className="card-sub">{city}</span>
      </div>
      <ul className="list" style={{ gap: '0.25rem' }}>
        {threats.slice(0, 5).map((t) => (
          <li key={t.threat_id} style={{ display: 'grid', gap: '0.35rem', alignItems: 'stretch' }}>
            <div className="spread">
              <strong style={{ fontWeight: 650 }}>{t.threat_name}</strong>
              <span className={`badge badge-${t.priority}`}>{t.priority} priority</span>
            </div>
            <div className="bar-track" aria-hidden="true">
              <div className="bar-fill" style={{ width: `${(t.estimated_dollar_burden / max) * 100}%` }} />
              <div className="bar-text">~{money(t.estimated_dollar_burden)} for you</div>
            </div>
            <p className="muted small">
              <span className="sr-only">Estimated cost to you about {money(t.estimated_dollar_burden)}. </span>
              {t.recommended_budget_shift}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function RecurringCard({ items }: { items: Recurring[] }) {
  const bills = items.filter((r) => !r.is_savings)
  return (
    <section className="card" aria-labelledby="recurring-title">
      <div className="card-head">
        <h2 id="recurring-title" className="card-title">
          Recurring payments
        </h2>
        <Repeat size={20} aria-hidden="true" className="muted" />
      </div>
      <ul className="list">
        {bills.slice(0, 6).map((r) => (
          <li key={r.merchant}>
            <span>
              {r.merchant}
              {r.change > 0 && <span className="change-up"> · up {money(r.change)}</span>}
              <div className="muted small">Next {shortDate(r.next_due)}</div>
            </span>
            <span className="amount">{money(r.amount, true)}</span>
          </li>
        ))}
      </ul>
      <a className="link-btn" href="#/recurring">
        See all {bills.length} payments <ArrowRight size={15} aria-hidden="true" />
      </a>
    </section>
  )
}

export function PlanCard({ plan, onAsk }: { plan: Plan; onAsk: (q: string) => void }) {
  if (!plan?.stage) return null
  const pct = Math.min(100, (plan.spent_this_week / Math.max(plan.weekly_limit, 1)) * 100)
  return (
    <section className="card" aria-labelledby="plan-title">
      <div className="card-head">
        <div>
          <p className="eyebrow">
            Coaching plan · stage {plan.stage.number} of {plan.stage.of}
          </p>
          <h2 id="plan-title" className="card-title">
            {plan.stage.name}
          </h2>
        </div>
        <Target size={22} aria-hidden="true" className="muted" />
      </div>
      <p className="small">
        This week: <strong>{money(plan.spent_this_week)}</strong> of your {money(plan.weekly_limit)} limit on{' '}
        {plan.watch_categories.join(', ').toLowerCase()}
      </p>
      <div
        className={`progress ${plan.over_limit ? 'over' : ''}`}
        role="progressbar"
        aria-valuenow={Math.round(plan.spent_this_week)}
        aria-valuemin={0}
        aria-valuemax={plan.weekly_limit}
        aria-label="Weekly limit used"
        style={{ margin: '0.6rem 0 0.4rem' }}
      >
        <span style={{ width: `${pct}%` }} />
      </div>
      <p className={`small ${plan.over_limit ? 'warn' : 'good'}`}>
        {plan.over_limit ? `${money(-plan.remaining_this_week)} over this week` : `${money(plan.remaining_this_week)} left this week`}
      </p>
      <h3 style={{ fontSize: '0.95rem', margin: '1rem 0 0.4rem' }}>Micro-goals</h3>
      <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.3rem' }} className="small">
        {plan.micro_goals.map((g) => (
          <li key={g}>{g}</li>
        ))}
      </ul>
      <p className="muted small" style={{ marginTop: '0.75rem' }}>
        Habit swap: {plan.habit_swap}
      </p>
      <button type="button" className="link-btn" onClick={() => onAsk("What's my goal this week and how am I doing?")}>
        Check in with NatBot <ArrowRight size={15} aria-hidden="true" />
      </button>
    </section>
  )
}

export function ProfileCard({ profile, budget }: { profile: Profile; budget: Budget }) {
  const rows = (['needs', 'wants', 'savings'] as const).map((k) => ({
    k,
    actual: budget.actual[k].percent_of_income,
    target: budget.target_percent[k],
  }))
  const monthLabel = new Date(budget.month + '-15').toLocaleDateString('en-GB', { month: 'long' })
  return (
    <section className="card" aria-labelledby="profile-title">
      <p className="eyebrow">Your money profile</p>
      <h2 id="profile-title" className="card-title">
        {shortName(profile.capacity)} · {shortName(profile.tendency)}
      </h2>
      <p className="small" style={{ margin: '0.5rem 0' }}>
        {CAPACITY_TEXT[profile.capacity]} {TENDENCY_TEXT[profile.tendency]}
      </p>
      <h3 style={{ fontSize: '0.95rem', margin: '1rem 0 0.25rem' }}>{monthLabel} vs your healthy split</h3>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Share of income by bucket in {monthLabel}, against your target</caption>
          <thead>
            <tr>
              <th scope="col">Bucket</th>
              <th scope="col" className="num">Actual</th>
              <th scope="col" className="num">Target</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const off = r.k === 'savings' ? r.actual < r.target : r.actual > r.target
              return (
                <tr key={r.k}>
                  <td style={{ textTransform: 'capitalize' }}>{r.k}</td>
                  <td className={`num ${off ? 'warn' : 'good'}`}>
                    {r.actual}%<span className="sr-only">{off ? ', off target' : ', on target'}</span>
                  </td>
                  <td className="num">{r.target}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
