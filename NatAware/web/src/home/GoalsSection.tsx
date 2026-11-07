import { MessageCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { GOAL_ICONS } from '../components/bits'
import { compactMoney, duration, durationLong, money } from '../format'
import { usePrefs } from '../prefs'
import type { Goal, Strategy } from '../types'
import { C } from './chartTheme'

/** Same maths as nataware/insights/goals.py:plan_monthly, so toggles re-project instantly. */
function planMonthly(strategies: Strategy[], usual: number, selected: Set<string>): number {
  const chosen = strategies.filter((s) => selected.has(s.id))
  const base = usual + chosen.filter((s) => s.kind === 'add').reduce((a, s) => a + (s.monthly ?? 0), 0)
  const bonus = chosen
    .filter((s) => s.kind === 'bonus')
    .reduce((a, s) => a + Math.min(base * (s.rate ?? 0), s.cap_monthly ?? Infinity), 0)
  return base + bonus
}

const monthsTo = (remaining: number, monthly: number) =>
  remaining <= 0 ? 0 : monthly > 0 ? Math.ceil(remaining / monthly) : null

const axisLabel = (m: number) => (m === 0 ? 'Now' : m < 0 ? `${-m}m ago` : m % 12 === 0 ? `+${m / 12}y` : `+${m}m`)

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
                  <Icon size={18} aria-hidden="true" />
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
    const step = horizon > 36 ? 3 : 2
    const rows: { m: number; saved?: number; plan?: number; current?: number }[] = []
    const hist = goal.history.slice(-12)
    hist.forEach((h, i) => rows.push({ m: i - hist.length, saved: h.balance }))
    for (let m = 0; m <= horizon; m += step) {
      rows.push({
        m,
        saved: m === 0 ? goal.saved : undefined,
        plan: Math.min(goal.target, goal.saved + monthly * m),
        current: Math.min(goal.target, goal.saved + goal.usual_monthly * m),
      })
    }
    return rows
  }, [goal, monthly, planMonths])

  const minM = data[0]?.m ?? 0
  const maxM = data[data.length - 1]?.m ?? 24
  const ticks = [...(minM < 0 ? [minM] : []), 0, ...[12, 24, 36, 48, 60, 72].filter((t) => t <= maxM)]

  const summary =
    `${goal.name}: ${money(goal.saved)} saved of ${money(goal.target)}` +
    (goal.saved_last_12_months ? `, ${money(goal.saved_last_12_months)} added in the last year. ` : '. ') +
    `With the NatBot plan you reach it in ${durationLong(planMonths)}; on your current path it takes ${durationLong(currentMonths)}.`

  return (
    <div id="goal-panel" role="tabpanel" aria-labelledby={`goal-tab-${goal.id}`} className="goal-body">
      <div>
        <div className="legend" aria-hidden="true">
          <span className="legend-item" style={{ color: C.series1 }}>
            <span className="key-line" />
            <span style={{ color: 'var(--ink-2)' }}>Saved so far, then with NatBot plan</span>
          </span>
          <span className="legend-item" style={{ color: C.series2 }}>
            <span className="key-line dashed" />
            <span style={{ color: 'var(--ink-2)' }}>Current path</span>
          </span>
        </div>
        <div className="chart-wrap" role="img" aria-label={summary}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 14, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={C.grid} />
              <XAxis
                dataKey="m"
                type="number"
                domain={[minM, maxM]}
                ticks={ticks}
                tickFormatter={axisLabel}
                tickLine={false}
                axisLine={false}
                tick={{ fill: C.tick, fontSize: '0.75rem' }}
              />
              <YAxis
                width={50}
                tickLine={false}
                axisLine={false}
                tick={{ fill: C.tick, fontSize: '0.75rem' }}
                tickFormatter={compactMoney}
                domain={[0, goal.target]}
                ticks={[0, goal.target / 2, goal.target]}
              />
              <ReferenceLine y={goal.target} stroke={C.gridStrong} strokeDasharray="4 4" />
              <ReferenceLine x={0} stroke={C.gridStrong} />
              <Tooltip
                formatter={(v, name) => [
                  money(Number(v)),
                  name === 'plan' ? 'With NatBot plan' : name === 'saved' ? 'Saved' : 'Current path',
                ]}
                labelFormatter={(m) =>
                  Number(m) === 0 ? 'Now' : Number(m) < 0 ? `${-Number(m)} months ago` : `In ${durationLong(Number(m))}`
                }
                contentStyle={{ borderRadius: 12, border: '1px solid var(--border)' }}
              />
              <Line type="monotone" dataKey="saved" stroke={C.series1} strokeWidth={2.5} dot={false} connectNulls isAnimationActive={false} />
              <Line type="monotone" dataKey="current" stroke={C.series2} strokeWidth={2} strokeDasharray="6 5" dot={false} isAnimationActive={false} />
              <Line
                type="monotone"
                dataKey="plan"
                stroke={C.series1}
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5, stroke: C.surface, strokeWidth: 2 }}
                isAnimationActive={false}
              />
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
              <caption className="sr-only">{goal.name}: savings history and projection</caption>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col" className="num">
                    Saved / with plan
                  </th>
                  <th scope="col" className="num">
                    Current path
                  </th>
                </tr>
              </thead>
              <tbody>
                {data
                  .filter((r) => r.m === minM || r.m === 0 || (r.m > 0 && r.m % 12 === 0))
                  .map((r) => (
                    <tr key={r.m}>
                      <td>{axisLabel(r.m)}</td>
                      <td className="num">{money(r.m <= 0 ? r.saved ?? 0 : r.plan ?? 0)}</td>
                      <td className="num">{r.m >= 0 ? money(r.current ?? 0) : '–'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div>
        <h3 className="card-sub" style={{ marginBottom: '0.5rem', fontWeight: 600 }}>
          Recommended strategies · tap to include
        </h3>
        <fieldset className="strategies" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="sr-only">Strategies to include in your plan</legend>
          {goal.strategies.map((s) => {
            const on = chosen.has(s.id)
            const base =
              goal.usual_monthly +
              goal.strategies.filter((x) => chosen.has(x.id) && x.kind === 'add').reduce((a, x) => a + (x.monthly ?? 0), 0)
            const value = s.kind === 'bonus' ? Math.min(base * (s.rate ?? 0), s.cap_monthly ?? 0) : s.monthly ?? 0
            return (
              <label key={s.id} className={`strategy ${on ? 'on' : ''}`}>
                <input type="checkbox" checked={on} onChange={() => toggle(s.id)} />
                <span>
                  <span className="strategy-title">{s.title}</span>
                  <span className="strategy-detail" style={{ display: 'block' }}>
                    {s.plain ?? s.detail}
                  </span>
                  {!prefs.plainEnglish && (
                    <span className="strategy-evidence" style={{ display: 'block' }}>
                      {s.evidence_text ?? s.evidence}
                    </span>
                  )}
                </span>
                <span className="strategy-amount">+{money(value)}/mo</span>
              </label>
            )
          })}
        </fieldset>
        <p className="plan-total">
          Plan adds <strong>{money(extra)}/month</strong> on top of the {money(goal.usual_monthly)} you usually put
          {goal.pot_name ? ` in your ${goal.pot_name} pot` : ' aside'}.
        </p>
        <button type="button" className="link-btn" onClick={() => onAsk(`How can I reach my ${goal.name.toLowerCase()} goal faster?`)}>
          <MessageCircle size={16} aria-hidden="true" /> Talk this through with NatBot
        </button>
      </div>
    </div>
  )
}
