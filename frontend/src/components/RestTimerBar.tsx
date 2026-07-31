import { useEffect, useState } from 'react'

const ENDS_KEY = 'rest_timer_ends_at'
const SECONDS_KEY = 'rest_timer_seconds'
const OPTIONS = [0, 60, 90, 120, 180]

export function configuredRestSeconds(): number {
  const raw = localStorage.getItem(SECONDS_KEY)
  return raw == null ? 90 : parseInt(raw)
}

/** Call when a set is logged: (re)starts the countdown if enabled. */
export function startRestTimer() {
  const secs = configuredRestSeconds()
  if (secs > 0) localStorage.setItem(ENDS_KEY, String(Date.now() + secs * 1000))
}

export function clearRestTimer() {
  localStorage.removeItem(ENDS_KEY)
}

function fmt(totalSecs: number) {
  const m = Math.floor(totalSecs / 60)
  const s = totalSecs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function RestTimerBar() {
  const [remaining, setRemaining] = useState<number | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const [configured, setConfigured] = useState(configuredRestSeconds)
  const [customInput, setCustomInput] = useState('')

  useEffect(() => {
    const tick = () => {
      const raw = localStorage.getItem(ENDS_KEY)
      if (raw == null) {
        setRemaining(null)
        return
      }
      const left = Math.ceil((parseInt(raw) - Date.now()) / 1000)
      if (left <= 0) {
        localStorage.removeItem(ENDS_KEY)
        setRemaining(0)
        if (navigator.vibrate) navigator.vibrate([200, 100, 200])
        setTimeout(() => setRemaining(null), 3000)
      } else {
        setRemaining(left)
      }
    }
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [])

  const pick = (secs: number) => {
    localStorage.setItem(SECONDS_KEY, String(secs))
    setConfigured(secs)
    setShowConfig(false)
    setCustomInput('')
    if (secs === 0) clearRestTimer()
  }

  const handleCustomBlur = () => {
    const val = parseInt(customInput)
    if (val > 0 && val <= 600) {
      pick(val)
    }
  }

  return (
    <div className="rest-bar">
      {showConfig && (
        <div className="rest-config">
          {OPTIONS.map((o) => (
            <button
              key={o}
              className={`chip ${configured === o ? 'active' : ''}`}
              onClick={() => pick(o)}
            >
              {o === 0 ? 'Off' : fmt(o)}
            </button>
          ))}
          <input
            type="number"
            placeholder="Custom"
            min={0}
            max={600}
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            onBlur={handleCustomBlur}
            style={{
              width: 72,
              textAlign: 'center',
              background: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--text)',
              padding: '8px',
              fontSize: '1rem',
            }}
          />
        </div>
      )}
      <div className="rest-bar-inner">
        <button className="secondary rest-config-btn" onClick={() => setShowConfig((v) => !v)}>
          ⏱ {configured === 0 ? 'Off' : fmt(configured)}
        </button>
        {remaining != null ? (
          <span className={`rest-countdown ${remaining === 0 ? 'done' : ''}`}>
            {remaining === 0 ? 'Rest done — go!' : fmt(remaining)}
          </span>
        ) : (
          <span className="muted">Rest timer starts after each set</span>
        )}
        {remaining != null && remaining > 0 && (
          <button className="secondary rest-config-btn" onClick={() => { clearRestTimer(); setRemaining(null) }}>
            Skip
          </button>
        )}
      </div>
    </div>
  )
}
