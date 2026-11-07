// Shapes returned by the NatAware API (see nataware/api/main.py and nataware/insights/).

export interface Capabilities {
  chat: boolean
  speech_to_text: boolean
  text_to_speech: boolean
}

export interface AppState {
  agent: string
  onboarded: boolean
  account: { display_name: string; first_name: string; account_type: string; city: string }
  today: string
  capabilities: Capabilities
}

export interface Goal {
  id: string
  name: string
  kind: string
  target: number
  saved: number
  remaining: number
  progress: number
  usual_monthly: number
  current_path_months: number | null
  plan_monthly: number
  plan_months: number | null
  strategies: Strategy[]
}

export interface Strategy {
  id: string
  title: string
  detail: string
  plain?: string
  evidence: string
  evidence_text?: string
  kind: 'add' | 'bonus'
  monthly: number | null
  rate?: number
  cap_monthly?: number
}

export interface Profile {
  capacity: string
  tendency: string
  optimal_baseline: { needs: number; wants: number; savings: number }
  rationale: string
  goals: { id: string; name: string; kind: string; target: number; saved: number | null }[]
  assessed_at: string | null
  label?: string
}

export interface ForecastPoint {
  month: string
  label: string
  predicted: number
  low: number
  high: number
  actual_to_date?: number
  seasonal_index: number
  drivers: { label: string; amount: number }[]
}

export interface Forecast {
  baseline_monthly: number
  typical_swing: number
  actual: { month: string; label: string; total: number }[]
  forecast: ForecastPoint[]
  peak: { month: string; label: string; predicted: number; above_baseline: number } | null
  basis: string[]
  method: string
}

export interface Insight {
  id: string
  kind: string
  label: string
  tone: 'warning' | 'positive' | 'info'
  plain: string
  detail: string
  ask?: string
  narrated?: boolean
}

export interface AwarenessEvent {
  id: string
  title: string
  icon: string
  window_label: string
  starts: string
  ends: string
  in_progress: boolean
  expected_extra: number
  still_to_come: number
  last_year_spend: number
  contributors: { category: string; extra: number }[]
  confidence: number
  impact: 'high' | 'medium' | 'low'
  weekly_save: number
  why: { history: string; area: string }
  area_sources: { id: string; headline: string }[]
  set_aside: { event_id: string; weekly: number } | null
  plain: string
  detail: string
}

export interface Threat {
  threat_id: string
  threat_name: string
  detail: string
  kind: string
  starts: string | null
  estimated_dollar_burden: number
  priority: 'high' | 'medium' | 'low'
  recommended_budget_shift: string
  affected_categories: string[]
}

export interface Recurring {
  merchant: string
  category: string
  amount: number
  previous_amount: number | null
  change: number
  changed_on: string | null
  day_of_month: number
  next_due: string
  first_seen: string
  is_savings: boolean
}

export interface Plan {
  profile: string
  stage: { number: number; of: number; id: string; name: string }
  micro_goals: string[]
  habit_swap: string
  watch_categories: string[]
  week: { start: string; end: string }
  weekly_limit: number
  spent_this_week: number
  remaining_this_week: number
  over_limit: boolean
  next_stage: string | null
}

export interface Budget {
  month: string
  income: number
  actual: Record<'needs' | 'wants' | 'savings', { amount: number; percent_of_income: number }>
  target_percent: Record<'needs' | 'wants' | 'savings', number>
  gap_percent: Record<'needs' | 'wants' | 'savings', number>
}

export interface Nudge {
  id: string
  trigger: string
  title: string
  message: string
  channel: string
  created_at: string
}

export interface Dashboard {
  today: string
  account: AppState['account'] & { balance: number; savings_balance: number; payday_day: number }
  profile: Profile
  stats: {
    month_to_date: { spent: number; previous_same_point: number; change_pct: number | null; previous_month_label: string }
    committed: { total: number; count: number }
    seasonal_alerts: number
    winter_buffer: { weekly: number; suggested_weekly: number }
  }
  goals: { usual_monthly_savings: number; savings_balance: number; goals: Goal[] }
  forecast: Forecast
  noticed: Insight[]
  awareness: AwarenessEvent[]
  threats: Threat[]
  recurring: Recurring[]
  plan: Plan
  budget: Budget
  nudges: Nudge[]
  narration: { status: 'ready' | 'pending' | 'templates'; error: string | null }
}

export interface Transaction {
  id: string
  date: string
  time: string | null
  merchant: string
  amount: number
  direction: 'debit' | 'credit'
  category: string
  is_flagged: boolean
  highlight_reason: string | null
}

export interface Highlight {
  label: string
  reason: string | null
  transaction_ids: string[]
  created_at: string
  transactions: Transaction[]
}

export interface ToolEvent {
  tool: string
  input: Record<string, unknown>
  result: Record<string, any>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  tools: ToolEvent[]
  pending?: boolean
  error?: boolean
}
