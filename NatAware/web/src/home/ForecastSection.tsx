import { MessageCircle } from 'lucide-react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compactMoney, money } from '../format'
import type { Forecast } from '../types'
import { C } from './chartTheme'

interface Row {
  label: string
  month: string
  actual?: number
  predicted?: number
  range?: [number, number]
  drivers?: { label: string; amount: number }[]
  toDate?: number
}

export function ForecastSection({ forecast, onAsk }: { forecast: Forecast; onAsk: (q: string) => void }) {
  const rows: Row[] = forecast.actual.map((a) => ({ label: a.label, month: a.month, actual: a.total }))
  // Join the dashed prediction to the last actual point so the line is continuous.
  if (rows.length) rows[rows.length - 1].predicted = rows[rows.length - 1].actual
  for (const p of forecast.forecast) {
    rows.push({
      label: p.label,
      month: p.month,
      predicted: p.predicted,
      range: [p.low, p.high],
      drivers: p.drivers,
      toDate: p.actual_to_date,
    })
  }
  const firstMonth = forecast.forecast[0]?.month
  const lastMonth = forecast.forecast[forecast.forecast.length - 1]?.month
  const labelFor = Object.fromEntries(rows.map((r) => [r.month, r.label]))
  const peak = forecast.peak

  const summary =
    `Monthly spending for the last ${forecast.actual.length} months averaged around ${money(forecast.baseline_monthly)}. ` +
    (peak ? `NatBot predicts ${peak.label} at about ${money(peak.predicted)}, ${money(peak.above_baseline)} above a normal month.` : '')

  return (
    <section className="card" aria-labelledby="forecast-title">
      <div className="card-head">
        <div>
          <h2 id="forecast-title" className="card-title">
            AI spending forecast
          </h2>
          {peak && (
            <p className="card-sub">
              {peak.label} could reach <strong className="warn">{money(peak.predicted)}</strong>, about{' '}
              {money(peak.above_baseline)} more than a normal month.
            </p>
          )}
        </div>
        <div className="legend" aria-hidden="true">
          <span className="legend-item" style={{ color: C.series1 }}>
            <span className="key-line" /> <span style={{ color: 'var(--ink-2)' }}>Actual</span>
          </span>
          <span className="legend-item" style={{ color: C.series1 }}>
            <span className="key-line dashed" /> <span style={{ color: 'var(--ink-2)' }}>Predicted</span>
          </span>
          <span className="legend-item">
            <span className="key-band" style={{ background: 'rgb(110 63 208 / 18%)' }} /> Likely range
          </span>
        </div>
      </div>

      <div className="chart-wrap" style={{ height: 220 }} role="img" aria-label={summary}>
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 22, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            {firstMonth && lastMonth && (
              <ReferenceArea
                x1={firstMonth}
                x2={lastMonth}
                fill={C.forecastZone}
                fillOpacity={1}
                label={{ value: 'Forecast', position: 'insideTopLeft', fill: C.tick, fontSize: '0.78rem' }}
              />
            )}
            <XAxis dataKey="month" tickFormatter={(m) => labelFor[m] ?? m} tickLine={false} axisLine={false} tick={{ fill: C.tick, fontSize: '0.78rem' }} />
            <YAxis width={56} tickLine={false} axisLine={false} tick={{ fill: C.tick, fontSize: '0.78rem' }} tickFormatter={compactMoney} domain={['auto', 'auto']} />
            <Tooltip content={<ForecastTooltip />} />
            <Area dataKey="range" stroke="none" fill={C.band} fillOpacity={0.14} isAnimationActive={false} />
            <Line dataKey="actual" stroke={C.series1} strokeWidth={2} dot={{ r: 4, fill: C.series1, stroke: C.surface, strokeWidth: 2 }} isAnimationActive={false} />
            <Line dataKey="predicted" stroke={C.series1} strokeWidth={2} strokeDasharray="6 5" dot={{ r: 4, fill: C.surface, stroke: C.series1, strokeWidth: 2, strokeDasharray: '0' }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="basis">
        <span className="muted">Based on:</span>
        {forecast.basis.map((b) => (
          <span key={b} className="pill">
            {b}
          </span>
        ))}
      </div>

      <details className="data-table">
        <summary>Show as a table and how it's worked out</summary>
        <p className="small muted" style={{ margin: '0.5rem 0' }}>
          {forecast.method}
        </p>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Monthly spending, actual and predicted</caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col" className="num">Actual</th>
                <th scope="col" className="num">Predicted</th>
                <th scope="col" className="num">Likely range</th>
              </tr>
            </thead>
            <tbody>
              {forecast.actual.map((a) => (
                <tr key={a.month}>
                  <td>{a.label}</td>
                  <td className="num">{money(a.total)}</td>
                  <td className="num">–</td>
                  <td className="num">–</td>
                </tr>
              ))}
              {forecast.forecast.map((p) => (
                <tr key={p.month}>
                  <td>{p.label}</td>
                  <td className="num">{p.actual_to_date !== undefined ? `${money(p.actual_to_date)} so far` : '–'}</td>
                  <td className="num">{money(p.predicted)}</td>
                  <td className="num">
                    {money(p.low)} to {money(p.high)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      {peak && (
        <button type="button" className="link-btn" onClick={() => onAsk(`How do I get ready for ${peak.label}?`)}>
          <MessageCircle size={16} aria-hidden="true" /> Ask NatBot how to prepare for {peak.label}
        </button>
      )}
    </section>
  )
}

function ForecastTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null
  const r = payload[0].payload
  return (
    <div className="card" style={{ padding: '0.75rem 0.9rem', fontSize: '0.85rem', maxWidth: 280, boxShadow: '0 8px 24px rgb(0 0 0 / 12%)' }}>
      <strong>{r.label}</strong>
      {r.actual !== undefined && <div>Spent {money(r.actual)}</div>}
      {r.range && (
        <>
          {r.toDate !== undefined && <div>So far {money(r.toDate)}</div>}
          <div>Predicted {money(r.predicted ?? 0)}</div>
          <div className="muted">
            Likely {money(r.range[0])} to {money(r.range[1])}
          </div>
          {r.drivers?.map((d) => (
            <div key={d.label} className="muted small">
              {d.amount >= 0 ? '+' : ''}
              {money(d.amount)} {d.label}
            </div>
          ))}
        </>
      )}
    </div>
  )
}
