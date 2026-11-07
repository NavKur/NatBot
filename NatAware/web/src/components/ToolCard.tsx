import { Bell, CalendarClock, Check, PiggyBank, Search, Sparkles, Star, Target, TrendingUp } from 'lucide-react'
import { duration, money } from '../format'
import type { ToolEvent } from '../types'
import { TxnTable } from './bits'

/** Visual result of a tool NatBot used, shown under its reply (the "on screen" half of a voice answer). */
export function ToolCard({ event }: { event: ToolEvent }) {
  const r = event.result
  if (r?.error) return <p className="tool-chip">Couldn't run {event.tool.replace(/_/g, ' ')}: {String(r.error)}</p>

  switch (event.tool) {
    case 'highlight_transactions':
      return (
        <section className="tool-card" aria-label={`Highlighted: ${r.label}`}>
          <h4>
            <Star size={16} aria-hidden="true" /> {r.label}
          </h4>
          <p className="muted small">
            {r.highlighted_count} transactions · {money(r.total, true)}
            {r.reason ? ` · ${r.reason}` : ''}
          </p>
          <TxnTable txns={r.transactions} caption={r.label} />
        </section>
      )
    case 'search_transactions':
      return (
        <p className="tool-chip">
          <Search size={14} aria-hidden="true" /> Checked your transactions: {r.match_count} found, {money(r.total)}
        </p>
      )
    case 'get_behavioural_flags':
      return (
        <section className="tool-card">
          <h4>Spending NatBot flagged</h4>
          <p className="muted small">
            {r.flag_count} flagged · {money(r.total)}
          </p>
          <TxnTable txns={r.transactions.slice(0, 10)} caption="Flagged transactions" />
        </section>
      )
    case 'get_spending_summary': {
      const max = Math.max(...r.rows.map((x: any) => x.total), 1)
      return (
        <section className="tool-card">
          <h4>Spending by {r.group_by}</h4>
          {r.rows.slice(0, 8).map((row: any) => (
            <div key={row.group} className="bar-row">
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${(row.total / max) * 100}%` }} />
                <div className="bar-text spread">
                  <span>{row.group}</span>
                  <strong className="tabular">{money(row.total)}</strong>
                </div>
              </div>
            </div>
          ))}
        </section>
      )
    }
    case 'get_budget_status':
      return (
        <section className="tool-card">
          <h4>Budget for {r.month}</h4>
          <table>
            <thead>
              <tr>
                <th scope="col">Bucket</th>
                <th scope="col" className="num">Spent</th>
                <th scope="col" className="num">Actual</th>
                <th scope="col" className="num">Target</th>
              </tr>
            </thead>
            <tbody>
              {(['needs', 'wants', 'savings'] as const).map((k) => (
                <tr key={k}>
                  <td style={{ textTransform: 'capitalize' }}>{k}</td>
                  <td className="num">{money(r.actual[k].amount)}</td>
                  <td className="num">{r.actual[k].percent_of_income}%</td>
                  <td className="num">{r.target_percent[k]}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )
    case 'get_active_threats':
      return (
        <section className="tool-card">
          <h4>Coming up near you</h4>
          <ul className="list">
            {r.threats.slice(0, 5).map((t: any) => (
              <li key={t.threat_id}>
                <span>
                  {t.threat_name}
                  <div className="muted small">{t.recommended_budget_shift}</div>
                </span>
                <span className="amount">~{money(t.estimated_dollar_burden)}</span>
              </li>
            ))}
          </ul>
        </section>
      )
    case 'get_coaching_plan':
      if (!r.stage) return null
      return (
        <section className="tool-card">
          <h4>
            <Target size={16} aria-hidden="true" /> Stage {r.stage.number} of {r.stage.of}: {r.stage.name}
          </h4>
          <p className="small">
            {money(r.spent_this_week)} of {money(r.weekly_limit)} weekly limit used
          </p>
          <div className={`progress ${r.over_limit ? 'over' : ''}`} aria-hidden="true">
            <span style={{ width: `${Math.min(100, (r.spent_this_week / r.weekly_limit) * 100)}%` }} />
          </div>
        </section>
      )
    case 'log_transaction':
      return (
        <section className="tool-card">
          <h4>
            <Check size={16} aria-hidden="true" /> Logged {money(r.transaction.amount, true)} at {r.transaction.merchant}
          </h4>
          {r.transaction.is_flagged && <p className="flag small">{r.transaction.highlight_reason}</p>}
          {r.nudge && (
            <div className="nudge">
              <strong>
                <Bell size={14} aria-hidden="true" style={{ display: 'inline' }} /> {r.nudge.title}
              </strong>
              <span>{r.nudge.message}</span>
            </div>
          )}
        </section>
      )
    case 'get_goals_and_strategies':
      return (
        <section className="tool-card">
          <h4>
            <PiggyBank size={16} aria-hidden="true" /> Your goals
          </h4>
          <ul className="list">
            {r.goals.map((g: any) => (
              <li key={g.id}>
                <span>
                  {g.name}
                  <div className="muted small">
                    {money(g.saved)} of {money(g.target)}
                  </div>
                </span>
                <span className="small" style={{ textAlign: 'right' }}>
                  <span className="muted">Now {duration(g.current_path_months)}</span>
                  <br />
                  <strong className="good">With plan {duration(g.plan_months)}</strong>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )
    case 'get_spending_forecast':
      return (
        <section className="tool-card">
          <h4>
            <TrendingUp size={16} aria-hidden="true" /> Spending forecast
          </h4>
          <ul className="list">
            {r.forecast.map((p: any) => (
              <li key={p.month}>
                <span>{p.label}</span>
                <span className="amount">
                  {money(p.predicted)} <span className="muted small">({money(p.low)} to {money(p.high)})</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )
    case 'get_seasonal_outlook':
      return (
        <section className="tool-card">
          <h4>
            <CalendarClock size={16} aria-hidden="true" /> Coming up
          </h4>
          <ul className="list">
            {r.events.map((e: any) => (
              <li key={e.id}>
                <span>
                  {e.title}
                  <div className="muted small">{e.window_label}</div>
                </span>
                <span className="amount">
                  ~{money(e.expected_extra)} <div className="muted small">save {money(e.weekly_save)}/wk</div>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )
    case 'get_insights':
      return (
        <section className="tool-card">
          <h4>
            <Sparkles size={16} aria-hidden="true" /> NatBot noticed
          </h4>
          {r.insights.map((i: any) => (
            <p key={i.id} className="small">
              <strong>{i.label}:</strong> {i.plain}
            </p>
          ))}
        </section>
      )
    case 'set_aside_for_event':
      return (
        <p className="tool-chip good">
          <Check size={14} aria-hidden="true" /> Setting aside {money(r.set_aside.weekly)} a week for {r.set_aside.event_id}
        </p>
      )
    case 'update_goal':
      return (
        <p className="tool-chip good">
          <Check size={14} aria-hidden="true" /> Goal saved: {r.goal.name} ({money(r.goal.target)})
        </p>
      )
    case 'get_recent_nudges':
      return (
        <section className="tool-card">
          {r.nudges.map((n: any) => (
            <div key={n.id} className="nudge">
              <strong>{n.title}</strong>
              <span>{n.message}</span>
            </div>
          ))}
        </section>
      )
    default:
      return null
  }
}
