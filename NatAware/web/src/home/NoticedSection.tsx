import { ChevronDown, CircleAlert, CircleCheck, Info, MessageCircle } from 'lucide-react'
import { useState } from 'react'
import { usePrefs } from '../prefs'
import type { Insight } from '../types'

const TONE_ICON = { warning: CircleAlert, positive: CircleCheck, info: Info }
const SHOWN = 4

export function NoticedSection({ insights, live, onAsk }: { insights: Insight[]; live: boolean; onAsk: (q: string) => void }) {
  const { prefs } = usePrefs()
  const [all, setAll] = useState(false)
  const visible = all ? insights : insights.slice(0, SHOWN)
  return (
    <section className="card" aria-labelledby="noticed-title">
      <div className="card-head">
        <h2 id="noticed-title" className="card-title">
          NatBot noticed
        </h2>
        {live && <span className="badge badge-live">AI live</span>}
      </div>
      <div className="insights">
        {visible.map((i) => {
          const Icon = TONE_ICON[i.tone]
          return (
            <article key={i.id} className={`insight tone-${i.tone}`}>
              <p className="insight-label">
                <Icon size={14} aria-hidden="true" /> {i.label}
              </p>
              <p className="insight-text">{i.plain}</p>
              {!prefs.plainEnglish && <p className="insight-detail">{i.detail}</p>}
              {i.ask && (
                <button type="button" className="link-btn" onClick={() => onAsk(i.ask!)}>
                  <MessageCircle size={14} aria-hidden="true" /> Ask NatBot
                </button>
              )}
            </article>
          )
        })}
      </div>
      {insights.length > SHOWN && (
        <button type="button" className="link-btn" aria-expanded={all} onClick={() => setAll((v) => !v)} style={{ marginTop: '0.4rem' }}>
          <ChevronDown size={15} aria-hidden="true" style={{ transform: all ? 'rotate(180deg)' : undefined }} />
          {all ? 'Show fewer' : `Show ${insights.length - SHOWN} more`}
        </button>
      )}
    </section>
  )
}
