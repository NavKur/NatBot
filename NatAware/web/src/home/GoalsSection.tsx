import { MessageCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { GOAL_ICONS } from '../components/bits'
import { C } from './chartTheme'
import { compactMoney, duration, durationLong, money } from '../format'
import { usePrefs } from '../prefs'
import type { Goal, Strategy } from '../types'

const PLAN = C.series1
const CURRENT = C.series2

/** Same maths as nataware/insights/goals.py:plan_monthly, so toggles re-project instantly. */
export function planMonthly(strategies: Strategy[], usual: number, selected: Set<string>): number {
  const chosen = strategies.filter((s) => selected.has(s.id))
  const base = usual + chosen.filter((s) => s.kind === 'add').reduce((a, s) => a + (s.monthly ?? 0), 0)
  const bonus = chosen
    .filter((s) => s.kind === 'bonus')
    .reduce((a, s) => a + Math.min(base * (s.rate ?? 0), s.cap_monthly ?? Infinity), 0)
  return base + bonus
}

const monthsTo = (remaining: number, monthly: number) =>
  remaining <= 0 ? 0 : monthly > 0 ? Math.ceil(remaining / monthly) : null

export function GoalsSection({ goals, onAsk }: { goals: Goal[]; onAsk: (q: string) => void }) {
  const [goalId, setGoalId] = useState(goals[0]?.id)
  const goal = goals.find((g) => g.id === goalId) ?? goals[0]
  const [selected, setSelected] = useState<Record<string, Set<string>>>({})

  if (!goal) {
    return (
      <section className="card" aria-labelledby="goals-title">
        <h2 id="goals-title" className="card-title">
          Your goals
        </h2>
        <p className="empty">
          No goals yet.{' '}
          <button type="button" className="link-btn" onClick={() => onAsk('Help me set a savings goal')}>
            Tell NatBot what you're saving for
          </button>
        </p>
      </section>
    )
  }

  const chosen = selected[goal.id] ?? new Set(goal.strategies.map((s) => s.id))
  const toggle = (id: string) => {
    const next = new Set(chosen)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected((s) => ({ ...s, [goal.id]: next }))
  }

  return (
    <section className="card" aria-labelledby="goals-title">
      <div className="card-head">
        <h2 id="goals-title" className="card-title">
          Your goals
        </h2>
        <p className="card-sub">Understood from what you told NatBot</p>
      </div>

      <div className="goal-tabs" role="tablist" aria-label="Choose a goal">
        {goals.map((g) => {
          const Icon = GOAL_ICONS[g.kind] ?? GOAL_ICONS.other
          return (
            <button
              key={g.id}
              type="button"
              role="tab"
              id={`goal-tab-${g.id}`}
              aria-selected={g.id === goal.id}
              aria-controls="goal-panel"
              className="goal-tab"
              onClick={() => setGoalId(g.id)}
            >
              <span className="goal-icon">
                <Icon size={20} aria-hidden="true" />
              </span>
              <span>
                <strong>{g.name}</strong>
                <span>
                  {money(g.saved)} of {money(g.target)}
                </span>
              </span>
            </button>
          )
        })}
      </div>

      <GoalBody key={goal.id} goal={goal} chosen={chosen} toggle={toggle} onAsk={onAsk} />
    </section>
  )
}

function GoalBody({
  goal,
  chosen,
  toggle,
  onAsk,
}: {
  goal: Goal
  chosen: Set<string>
  toggle: (id: string) => void
  onAsk: (q: string) => void
}) {
  const { prefs } = usePrefs()
  const monthly = planMonthly(goal.strategies, goal.usual_monthly, chosen)
  const planMonths = monthsTo(goal.remaining, monthly)
  const currentMonths = monthsTo(goal.remaining, goal.usual_monthly)
  const sooner = currentMonths !== null && planMonths !== null ? currentMonths - planMonths : null
  const extra = monthly - goal.usual_monthly

  const data = useMemo(() => {
    const horizon = Math.min(72, Math.max(24, (planMonths ?? 24) + 6))
    const step = horizon > 36 ? 3 : 1
    const rows = []
    for (let m = 0; m <= horizon; m += step) {
      rows.push({
        m,
        label: m === 0 ? 'Now' : m % 12 === 0 ? `${m / 12}y` : `${m}m`,
        plan: Math.min(goal.target, goal.saved + monthly * m),
        current: Math.min(goal.target, goal.saved + goal.usual_monthly * m),
      })
    }
    return rows
  }, [goal, monthly, planMonths])

  const summary = `With the NatBot plan, ${goal.name} reaches ${money(goal.target)} in ${durationLong(planMonths)}. On your current path it takes ${durationLong(currentMonths)}.`

  return (
    <div id="goal-panel" role="tabpanel" aria-labelledby={`goal-tab-${goal.id}`} className="goal-body">
      <div>
        <div className="legend" aria-hidden="true" style={{ marginBottom: '0.5rem' }}>
          <span className="legend-item" style={{ color: PLAN }}>
            <span className="key-line" />
            <span style={{ color: 'var(--ink-2)' }}>With NatBot plan</span>
          </span>
          <span className="legend-item" style={{ color: CURRENT }}>
            <span className="key-line dashed" />
            <span style={{ color: 'var(--ink-2)' }}>Current path</span>
          </span>
        </div>
        <div className="chart-wrap" role="img" aria-label={summary}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={C.grid} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: C.tick, fontSize: 12 }} interval="preserveStartEnd" minTickGap={24} />
              <YAxis
                width={56}
                tickLine={false}
                axisLine={false}
                tick={{ fill: C.tick, fontSize: 12 }}
                tickFormatter={compactMoney}
                domain={[0, goal.target]}
                ticks={[0, goal.target / 2, goal.target]}
              />
              <ReferenceLine y={goal.target} stroke={C.gridStrong} strokeDasharray="4 4" />
              <Tooltip
                formatter={(v, name) => [money(Number(v)), name === 'plan' ? 'With NatBot plan' : 'Current path']}
                labelFormatter={(l) => (l === 'Now' ? 'Now' : `In ${l}`)}
                contentStyle={{ borderRadius: 12, border: '1px solid var(--border)' }}
              />
              <Line type="monotone" dataKey="current" stroke={CURRENT} strokeWidth={2} strokeDasharray="6 5" dot={false} isAnimationActive={!prefs.reduceMotion} />
              <Line type="monotone" dataKey="plan" stroke={PLAN} strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: C.surface, strokeWidth: 2 }} isAnimationActive={!prefs.reduceMotion} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="path-summary">
          <div className="path-box">
            <div className="k">Current path</div>
            <div className="v">{duration(currentMonths)}</div>
          </div>
          <div className="path-box plan">
            <div className="k">With NatBot plan</div>
            <div className="v">{duration(planMonths)}</div>
          </div>
          <div className="path-box sooner" aria-live="polite">
            <div className="k">You'd get there</div>
            <div className="v">{sooner && sooner > 0 ? `${sooner} months sooner` : 'Pick a strategy'}</div>
          </div>
        </div>
        <details className="data-table">
          <summary>Show as a table</summary>
          <div className="table-wrap" style={{ marginTop: '0.5rem' }}>
            <table>
              <caption className="sr-only">{goal.name} projection</caption>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col" className="num">With plan</th>
                  <th scope="col" className="num">Current path</th>
                </tr>
              </thead>
              <tbody>
                {data.filter((r) => r.m % 12 === 0).map((r) => (
                  <tr key={r.m}>
                    <td>{r.label}</td>
                    <td className="num">{money(r.plan)}</td>
                    <td className="num">{money(r.current)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div>
        <h3 className="card-sub" style={{ marginBottom: '0.75rem', fontWeight: 600 }}>
          Recommended strategies · tap to include
        </h3>
        <fieldset className="strategies" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="sr-only">Strategies to include in your plan</legend>
          {goal.strategies.map((s) => {
            const on = chosen.has(s.id)
            const base = goal.usual_monthly + goal.strategies.filter((x) => chosen.has(x.id) && x.kind === 'add').reduce((a, x) => a + (x.monthly ?? 0), 0)
            const value = s.kind === 'bonus' ? Math.min(base * (s.rate ?? 0), s.cap_monthly ?? 0) : s.monthly ?? 0
            return (
              <label key={s.id} className={`strategy ${on ? 'on' : ''}`}>
                <input type="checkbox" checked={on} onChange={() => toggle(s.id)} />
                <span>
                  <span className="strategy-title">{s.title}</span>
                  <span className="strategy-detail" style={{ display: 'block' }}>
                    {prefs.plainEnglish ? s.plain ?? s.detail : s.detail}
                  </span>
                  {!prefs.plainEnglish && <span className="strategy-evidence" style={{ display: 'block' }}>{s.evidence_text ?? s.evidence}</span>}
                </span>
                <span className="strategy-amount">+{money(value)}/mo</span>
              </label>
            )
          })}
        </fieldset>
        <p className="plan-total">
          Plan adds <strong>{money(extra)}/month</strong> on top of your usual {money(goal.usual_monthly)}.
        </p>
        <button type="button" className="link-btn" onClick={() => onAsk(`How can I reach my ${goal.name.toLowerCase()} goal faster?`)}>
          <MessageCircle size={16} aria-hidden="true" /> Talk this through with NatBot
        </button>
      </div>
    </div>
  )
}
