import { FileText, LoaderCircle, Upload } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { api } from '../api'
import { TxnTable } from '../components/bits'
import type { Transaction } from '../types'

export function Statements({ onUploaded }: { onUploaded: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ added: number; flagged: number; transactions: Transaction[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const upload = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const r = await api.uploadStatement(file)
      setResult(r)
      onUploaded()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDrag(false)
    void upload(e.dataTransfer.files[0])
  }

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Statements</p>
          <h1 className="page-title" id="page-title" tabIndex={-1}>
            Add a bank statement
          </h1>
        </div>
      </div>
      <section className="card">
        <div
          className={`dropzone ${drag ? 'drag' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDrag(true)
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <FileText size={36} aria-hidden="true" className="muted" />
          <p>
            <strong>Drop a CSV or PDF statement here</strong>
          </p>
          <p className="muted small">
            NatAware reads the date, payee and amount, sorts each payment into a category, and checks it against your
            spending habits.
          </p>
          <input
            ref={input}
            type="file"
            accept=".csv,.pdf,text/csv,application/pdf"
            className="sr-only"
            id="statement-file"
            onChange={(e) => upload(e.target.files?.[0])}
          />
          <button type="button" className="btn btn-primary" onClick={() => input.current?.click()} disabled={busy}>
            {busy ? <LoaderCircle size={18} className="spinner" aria-hidden="true" /> : <Upload size={18} aria-hidden="true" />}
            {busy ? 'Reading your statement…' : 'Choose a file'}
          </button>
        </div>
        <div aria-live="polite">
          {error && (
            <p className="error-text" role="alert" style={{ marginTop: '1rem' }}>
              {error}
            </p>
          )}
          {result && (
            <div style={{ marginTop: '1.25rem' }} className="stack">
              <p>
                <strong>
                  Added {result.added} payments, {result.flagged} flagged.
                </strong>{' '}
                Your dashboard has been updated.
              </p>
              <TxnTable txns={result.transactions} caption="Payments from your statement" />
            </div>
          )}
        </div>
      </section>
    </>
  )
}
