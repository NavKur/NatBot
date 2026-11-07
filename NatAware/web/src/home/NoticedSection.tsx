import { CircleAlert, CircleCheck, Info, MessageCircle } from 'lucide-react'
import { usePrefs } from '../prefs'
import type { Insight } from '../types'

const TONE_ICON = { warning: CircleAlert, positive: CircleCheck, info: Info }

export function NoticedSection({ insights, live, onAsk }: { insights: Insight[]; live: boolean; onAsk: (q: string) => void }) {
  const { prefs } = usePrefs()
  return (
    <section className="card" aria-labelledby="noticed-title">
      <div className="card-head">
        <h2 id="noticed-title" className="card-title">
          NatBot noticed
        </h2>
        {live && <span className="badge badge-live">AI live</span>}
      </div>
      <div className="stack" style={{ gap: '0.85rem' }}>
        {insights.map((i) => {
          const Icon = TONE_ICON[i.tone]
          return (
            <article key={i.id} className={`insight tone-${i.tone}`}>
              <p className="insight-label">
                <Icon size={15} aria-hidden="true" /> {i.label}
              </p>
              <p className="insight-text">{i.plain}</p>
              {!prefs.plainEnglish && <p className="insight-detail">{i.detail}</p>}
              {i.ask && (
                <button type="button" className="link-btn" onClick={() => onAsk(i.ask!)}>
                  <MessageCircle size={15} aria-hidden="true" /> Ask NatBot
                </button>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
