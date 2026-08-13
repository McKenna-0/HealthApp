import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiPut } from '../api/client'
import type { WeightGoalSummary } from '../api/types'

/**
 * Sets the three things the goal chart needs: where you're heading, how fast,
 * and the point the plan is measured from.
 *
 * The anchor matters — without it the plan line would start wherever the chart
 * window happens to begin, so "am I ahead or behind" would change every time
 * the range picker moved. Saving pins it to today's smoothed trend weight.
 */
export default function WeightGoalEditor({
  goal,
  trendKg,
  today,
  onSaved,
}: {
  goal: WeightGoalSummary | null
  trendKg: number | null
  today: string
  onSaved?: () => void
}) {
  const qc = useQueryClient()
  const [target, setTarget] = useState('')
  const [rate, setRate] = useState('')
  const [reanchor, setReanchor] = useState(false)

  useEffect(() => {
    setTarget(goal?.target_kg?.toString() ?? '')
    setRate(goal?.rate_kg_per_week?.toString() ?? '')
  }, [goal?.target_kg, goal?.rate_kg_per_week])

  const anchored = goal?.rate_kg_per_week != null

  const save = useMutation({
    mutationFn: (restart: boolean) => {
      setReanchor(restart)
      const body: Record<string, string | number | null> = {
        weight_goal_kg: target ? parseFloat(target) : null,
        weight_goal_rate_kg_per_week: rate ? parseFloat(rate) : null,
      }
      // Re-anchor when the goal is new, or when explicitly asked to start over
      // from today. Otherwise the existing anchor is left alone so history
      // doesn't shift under the user.
      if (restart || !anchored) {
        body.weight_goal_start_date = today
        if (trendKg != null) body.weight_goal_start_kg = trendKg
      }
      return apiPut('/api/settings', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['weight-progress'] })
      setReanchor(false)
      onSaved?.()
    },
  })

  const rateNum = parseFloat(rate)
  const direction = !rate || Number.isNaN(rateNum)
    ? null
    : rateNum > 0 ? 'gain' : rateNum < 0 ? 'lose' : 'maintain'

  return (
    <div className="card">
      <div className="text-title" style={{ marginBottom: 4 }}>Your goal</div>
      <div className="text-caption" style={{ marginBottom: 12 }}>
        Rate is signed: <strong>+0.25</strong> to gain a quarter kilo a week, <strong>−0.5</strong> to
        lose half, <strong>0</strong> to hold.
      </div>

      <div className="row" style={{ marginBottom: 10, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <label className="text-caption" htmlFor="goal-target" style={{ display: 'block', marginBottom: 4 }}>
            Target weight (kg)
          </label>
          <input
            id="goal-target"
            type="number"
            inputMode="decimal"
            step="0.1"
            placeholder="optional"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            style={{ width: '100%', fontSize: 16, minHeight: 44 }}
          />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <label className="text-caption" htmlFor="goal-rate" style={{ display: 'block', marginBottom: 4 }}>
            Rate (kg / week)
          </label>
          <input
            id="goal-rate"
            type="number"
            inputMode="decimal"
            step="0.05"
            placeholder="+0.25"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
            style={{ width: '100%', fontSize: 16, minHeight: 44 }}
          />
        </div>
      </div>

      {direction && (
        <div className="text-caption" style={{ marginBottom: 10 }}>
          {direction === 'gain' && 'Gaining — the band stays green up to 0.5% of body weight per week.'}
          {direction === 'lose' && 'Losing — the band stays green down to 1% of body weight per week.'}
          {direction === 'maintain' && 'Holding — the band stays green while drift stays under 0.25% of body weight per week.'}
        </div>
      )}

      {anchored && (
        <div className="text-caption" style={{ marginBottom: 10 }}>
          Plan measured from {goal.start_kg.toFixed(1)} kg on {goal.start_date}.
        </div>
      )}

      <button
        onClick={() => save.mutate(false)}
        disabled={save.isPending}
        style={{ width: '100%', marginTop: 4, minHeight: 44 }}
      >
        {save.isPending && !reanchor ? 'Saving…' : 'Save goal'}
      </button>

      {anchored && (
        <button
          className="secondary"
          onClick={() => save.mutate(true)}
          disabled={save.isPending}
          style={{ width: '100%', marginTop: 8, minHeight: 44 }}
        >
          {save.isPending && reanchor
            ? 'Saving…'
            : `Save & restart from today${trendKg != null ? ` (${trendKg.toFixed(1)} kg)` : ''}`}
        </button>
      )}

      {save.isError && (
        <p className="text-caption" style={{ marginTop: 6, color: 'var(--red)' }}>
          {String(save.error).replace(/^\d+: /, '').slice(0, 160)}
        </p>
      )}
    </div>
  )
}
