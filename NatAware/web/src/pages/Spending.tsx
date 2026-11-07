import { Star } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { TxnTable } from '../components/bits'
import { money, monthName } from '../format'
import type { Highlight, Transaction } from '../types'

function monthsBetween(from: string, to: string): string[] {
  const out: string[] = []
  let [y, m] = from.split('-').map(Number)
  const [ty, tm] = to.split('-').map(Number)
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`)
    m++
    if (m > 12) {
      m = 1
      y++
    }
  }
  return out.reverse()
}

function lastDay(month: string) {
  const [y, m] = month.split('-').map(Number)
  return `${month}-${String(new Date(y, m, 0).getDate()).padStart(2, '0')}`
}

export function Spending({ today, query, version }: { today: string; query: string; version: number }) {
  const months = useMemo(() => monthsBetween('2025-09', today.slice(0, 7)), [today])
  const [month, setMonth] = useState(months[0])
  const [search, setSearch] = useState(query)
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [txns, setTxns] = useState<{ count: number; total: number; list: Transaction[] } | null>(null)
  const [cats, setCats] = useState<{ group: string; total: number; count: number }[]>([])
  const [highlights, setHighlights] = useState<Highlight[]>([])

  useEffect(() => setSearch(query), [query])

  const range = month === 'all' ? {} : { date_from: `${month}-01`, date_to: lastDay(month) }

  useEffect(() => {
    let live = true
    api
      .transactions({ ...range, query: search, flagged_only: flaggedOnly, direction: 'debit', newest_first: true, limit: 300 })
      .then((r) => live && setTxns({ count: r.count, total: r.total_debits, list: r.transactions }))
    api.spendingSummary({ group_by: 'category', ...range }).then((r) => live && setCats(r.rows))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, search, flaggedOnly, version])

  useEffect(() => {
    api.highlights().then((r) => setHighlights(r.highlights))
  }, [version])

  const max = Math.max(...cats.map((c) => c.total), 1)
  const label = month === 'all' ? 'all time' : monthName(month)

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Spending</p>
          <h1 className="page-title" id="page-title" tabIndex={-1}>
            Where your money went
          </h1>
        </div>
      </div>

      {highlights.length > 0 && (
        <section className="card" aria-labelledby="hl-title" style={{ marginBottom: '1.5rem' }}>
          <div className="card-head">
            <h2 id="hl-title" className="card-title row">
              <Star size={20} aria-hidden="true" /> Highlighted by NatBot
            </h2>
            <span className="card-sub">From your conversations</span>
          </div>
          <div className="stack" style={{ gap: '1.25rem' }}>
            {highlights.slice(0, 3).map((h) => (
              <div key={h.created_at + h.label}>
                <h3 style={{ fontSize: '1rem' }}>{h.label}</h3>
                <p className="muted small" style={{ marginBottom: '0.5rem' }}>
                  {h.transactions.length} transactions · {money(h.transactions.reduce((a, t) => a + t.amount, 0), true)}
                  {h.reason ? ` · ${h.reason}` : ''}
                </p>
                <TxnTable txns={h.transactions} caption={h.label} />
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="toolbar" role="search" aria-label="Filter payments">
        <label className="sr-only" htmlFor="month">
          Month
        </label>
        <select id="month" className="input" value={month} onChange={(e) => setMonth(e.target.value)}>
          {months.map((m) => (
            <option key={m} value={m}>
              {monthName(m)}
            </option>
          ))}
          <option value="all">All time</option>
        </select>
        <label className="sr-only" htmlFor="txn-search">
          Search payments
        </label>
        <input
          id="txn-search"
          className="input"
          type="search"
          placeholder="Search merchant or category"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="button" className="chip" aria-pressed={flaggedOnly} onClick={() => setFlaggedOnly((v) => !v)}>
          Flagged only
        </button>
      </div>

      <div className="grid-2">
        <section className="card" aria-labelledby="txn-title">
          <div className="card-head">
            <h2 id="txn-title" className="card-title">
              Payments in {label}
            </h2>
            {txns && (
              <span className="card-sub" aria-live="polite">
                {txns.count} payments · {money(txns.total)}
              </span>
            )}
          </div>
          {txns ? <TxnTable txns={txns.list} caption={`Payments in ${label}`} /> : <p className="empty">Loading…</p>}
          {txns && txns.count > txns.list.length && (
            <p className="muted small" style={{ marginTop: '0.5rem' }}>
              Showing the latest {txns.list.length}. Narrow the month or search to see more.
            </p>
          )}
        </section>

        <section className="card" aria-labelledby="cat-title">
          <h2 id="cat-title" className="card-title" style={{ marginBottom: '0.75rem' }}>
            By category
          </h2>
          {cats.map((c) => (
            <div key={c.group} className="bar-row">
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${(c.total / max) * 100}%` }} />
                <div className="bar-text spread">
                  <span>{c.group}</span>
                  <strong className="tabular">{money(c.total)}</strong>
                </div>
              </div>
            </div>
          ))}
        </section>
      </div>
    </>
  )
}
