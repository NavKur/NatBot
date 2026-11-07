const gbp0 = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const gbp2 = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', minimumFractionDigits: 2 })

/** £1,299 (whole pounds) or £8.99 when pennies matter. */
export function money(value: number, pennies = false): string {
  return (pennies ? gbp2 : gbp0).format(value)
}

export function compactMoney(value: number): string {
  if (Math.abs(value) >= 10_000) return `£${Math.round(value / 1000)}K`
  if (Math.abs(value) >= 1000) return `£${(value / 1000).toFixed(1).replace(/\.0$/, '')}K`
  return gbp0.format(value)
}

/** 139 -> "11y 7m"; 4 -> "4m". */
export function duration(months: number | null): string {
  if (months === null) return 'Not on track'
  if (months <= 0) return 'Done'
  const y = Math.floor(months / 12)
  const m = months % 12
  return y ? `${y}y ${m}m` : `${m}m`
}

/** Spoken / screen-reader version: "11 years and 7 months". */
export function durationLong(months: number | null): string {
  if (months === null) return 'not reachable at the current rate'
  const y = Math.floor(months / 12)
  const m = months % 12
  const parts = []
  if (y) parts.push(`${y} year${y === 1 ? '' : 's'}`)
  if (m) parts.push(`${m} month${m === 1 ? '' : 's'}`)
  return parts.join(' and ') || 'now'
}

export function shortDate(iso: string): string {
  return new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

export function longDate(iso: string): string {
  return new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
}

export function greeting(): string {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export function monthName(ym: string): string {
  return new Date(ym + '-15T12:00:00').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10)
}

const FRIENDLY: Record<string, string> = {
  'Takeaway & Delivery': 'takeaways and delivery',
  'Shopping - Online': 'online shopping',
  'Shopping - Clothing': 'clothes shopping',
  'Alcohol & Nightlife': 'drinks and nights out',
  'Cash Withdrawal': 'cash withdrawals',
  'Health & Pharmacy': 'pharmacy',
}

/** Category as it reads mid-sentence. */
export function friendly(category: string): string {
  return FRIENDLY[category] ?? category.toLowerCase()
}

export function listJoin(items: string[]): string {
  return items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
