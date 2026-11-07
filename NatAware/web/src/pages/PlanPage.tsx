import { HealthySplitCard, NearYou, PlanCard } from '../home/Cards'
import type { Dashboard } from '../types'

/** The coaching side of NatAware: this week's plan, the healthy split, and local changes to prepare for. */
export function PlanPage({ d, onAsk }: { d: Dashboard; onAsk: (q: string) => void }) {
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Plan</p>
          <h1 className="page-title" id="page-title" tabIndex={-1}>
            Your plan this week
          </h1>
        </div>
      </div>
      <div className="stack">
        <div className="grid-2-even">
          <PlanCard plan={d.plan} onAsk={onAsk} />
          <HealthySplitCard budget={d.budget} />
        </div>
        <NearYou threats={d.threats} city={d.account.city} />
      </div>
    </>
  )
}
