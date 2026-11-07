import {
  Car,
  Cloud,
  Flame,
  Gem,
  Gift,
  GraduationCap,
  Heart,
  House,
  Landmark,
  LifeBuoy,
  PiggyBank,
  Pill,
  Plane,
  ShoppingBag,
  Sparkles,
  Sun,
  Tag,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'
import { money } from '../format'
import type { BotStatus } from '../voice/useNatBot'
import type { Transaction } from '../types'

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <a className="logo" href="#/home" aria-label="NatAware home">
      <img className="logo-mark" src="/favicon.svg" alt="" />
      {!compact && (
        <span>
          Nat<b>Aware</b>
        </span>
      )}
    </a>
  )
}

const STATUS_LABEL: Record<BotStatus, string> = {
  idle: 'NatBot',
  listening: 'NatBot is listening',
  hearing: 'NatBot is listening',
  transcribing: 'NatBot is working out what you said',
  thinking: 'NatBot is thinking',
  speaking: 'NatBot is speaking',
}

export function Orb({ status = 'idle', size }: { status?: BotStatus; size?: number }) {
  return (
    <span
      className={`orb ${status}`}
      style={size ? ({ '--size': `${size}px` } as React.CSSProperties) : undefined}
      role="img"
      aria-label={STATUS_LABEL[status]}
    />
  )
}

export const GOAL_ICONS: Record<string, LucideIcon> = {
  house: House,
  emergency: LifeBuoy,
  debt: Landmark,
  travel: Plane,
  education: GraduationCap,
  car: Car,
  family: Heart,
  wedding: Gem,
  retirement: PiggyBank,
  other: Sparkles,
}

export const EVENT_ICONS: Record<string, LucideIcon> = {
  pill: Pill,
  gift: Gift,
  flame: Flame,
  cloud: Cloud,
  tag: Tag,
  'shopping-bag': ShoppingBag,
  sun: Sun,
  heart: Heart,
}

export function ImpactBadge({ impact }: { impact: 'high' | 'medium' | 'low' }) {
  return <span className={`badge badge-${impact}`}>{impact[0].toUpperCase() + impact.slice(1)} impact</span>
}

export function TxnTable({ txns, caption, showFlags = true }: { txns: Transaction[]; caption?: string; showFlags?: boolean }) {
  if (!txns.length) return <p className="empty">No transactions to show.</p>
  return (
    <div className="table-wrap">
      <table>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Merchant</th>
            <th scope="col">Category</th>
            <th scope="col" className="num">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {txns.map((t) => (
            <tr key={t.id} className={showFlags && t.is_flagged ? 'flagged' : undefined}>
              <td className="tabular">
                {new Date(t.date + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                {t.time && <div className="muted small">{t.time}</div>}
              </td>
              <td>
                {t.merchant}
                {showFlags && t.is_flagged && t.highlight_reason && (
                  <div className="flag">
                    <TriangleAlert size={14} aria-hidden="true" />
                    <span>
                      <span className="sr-only">Flagged: </span>
                      {t.highlight_reason}
                    </span>
                  </div>
                )}
              </td>
              <td className="muted">{t.category}</td>
              <td className="num">
                {t.direction === 'credit' ? '+' : ''}
                {money(t.amount, true)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Switch({
  id,
  checked,
  onChange,
  label,
  description,
}: {
  id: string
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  description?: string
}) {
  return (
    <div className="toggle-row">
      <label htmlFor={id}>
        <div style={{ fontWeight: 600 }}>{label}</div>
        {description && <div className="desc" id={`${id}-desc`}>{description}</div>}
      </label>
      <span className="switch">
        <input
          id={id}
          type="checkbox"
          role="switch"
          checked={checked}
          aria-describedby={description ? `${id}-desc` : undefined}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span aria-hidden="true" />
      </span>
    </div>
  )
}
