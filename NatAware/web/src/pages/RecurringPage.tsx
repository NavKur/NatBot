import { useEffect, useState } from 'react'
import { api } from '../api'
import { money, shortDate } from '../format'
import type { Recurring } from '../types'

export function RecurringPage({ onAsk, version }: { onAsk: (q: string) => void; version: number }) {
  const [data, setData] = useState<{ recurring: Recurring[]; committed: { total: number; count: number } } | null>(null)
  useEffect(() => {
    api.recurring().then(setData)
  }, [version])

  const bills = data?.recurring.filter((r) => !r.is_savings) ?? []
  const savings = data?.recurring.filter((r) => r.is_savings) ?? []

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Recurring</p>
          <h1 className="page-title" id="page-title" tabIndex={-1}>
            Bills and subscriptions
          </h1>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => onAsk('Which of my subscriptions should I cancel?')}>
          Ask NatBot what to cut
        </button>
      </div>
      {data && (
        <section className="card" aria-labelledby="rec-title">
          <div className="card-head">
            <h2 id="rec-title" className="card-title">
              {money(data.committed.total)} a month across {data.committed.count} payments
            </h2>
          </div>
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Recurring payments</caption>
              <thead>
                <tr>
                  <th scope="col">Payee</th>
                  <th scope="col">Category</th>
                  <th scope="col">Next due</th>
                  <th scope="col" className="num">Change</th>
                  <th scope="col" className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {bills.map((r) => (
                  <tr key={r.merchant}>
                    <td>{r.merchant}</td>
                    <td className="muted">{r.category}</td>
                    <td>{shortDate(r.next_due)}</td>
                    <td className={`num ${r.change > 0 ? 'warn' : r.change < 0 ? 'good' : 'muted'}`}>
                      {r.change ? `${r.change > 0 ? 'Up' : 'Down'} ${money(Math.abs(r.change), true)}` : 'No change'}
                    </td>
                    <td className="num">{money(r.amount, true)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {savings.length > 0 && (
            <p className="muted small" style={{ marginTop: '0.75rem' }}>
              Plus regular savings: {savings.map((s) => `${s.merchant} ${money(s.amount)}`).join(', ')}. Nice.
            </p>
          )}
        </section>
      )}
    </>
  )
}
