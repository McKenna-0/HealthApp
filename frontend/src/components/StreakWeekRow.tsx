import type { StreakInfo } from '../api/types'

export default function StreakWeekRow({ streak }: { streak: StreakInfo | undefined }) {
  if (!streak) return null
  return (
    <div className="card streak-row">
      <div className="streak-flame">
        <span style={{ fontSize: '1.5rem' }}>🔥</span>
        <div>
          <strong style={{ fontSize: '1.2rem' }}>{streak.current_streak}</strong>
          <div className="muted" style={{ fontSize: '0.7rem' }}>
            day streak · best {streak.longest_streak}
          </div>
        </div>
      </div>
      <div className="week-dots">
        {streak.week.map((d, i) => (
          <div key={d.date} className="week-dot-col">
            <span className="muted week-dot-label">{d.weekday[0]}</span>
            <span
              className={`week-dot ${d.complete ? 'complete' : ''} ${i === 6 ? 'today' : ''} ${
                !d.complete && (d.food_logged || d.checkin_done) ? 'partial' : ''
              }`}
            >
              {d.complete ? '✓' : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
