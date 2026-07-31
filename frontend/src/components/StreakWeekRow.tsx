import { Flame } from 'lucide-react'
import type { StreakInfo } from '../api/types'

export default function StreakWeekRow({ streak }: { streak: StreakInfo | undefined }) {
  if (!streak) return null
  return (
    <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px' }}>
      {/* Flame + count */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Flame size={22} style={{ color: 'var(--amber)' }} />
        <div>
          <span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text)' }}>{streak.current_streak}</span>
          <div className="text-caption" style={{ color: 'var(--muted)' }}>
            day streak · best {streak.longest_streak}
          </div>
        </div>
      </div>

      {/* Week dots */}
      <div style={{ display: 'flex', gap: 6 }}>
        {streak.week.map((d, i) => {
          const isToday = i === 6
          const dotColor = d.complete
            ? 'var(--green)'
            : !d.complete && (d.food_logged || d.checkin_done)
            ? 'var(--amber)'
            : 'var(--border)'
          return (
            <div key={d.date} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
              <span className="text-caption" style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>
                {d.weekday[0]}
              </span>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: dotColor,
                  outline: isToday ? '2px solid var(--accent)' : 'none',
                  outlineOffset: 1,
                }}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
