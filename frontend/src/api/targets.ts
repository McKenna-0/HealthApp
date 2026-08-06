import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'

/** A target split into the configured base and the bonus earned from active calories. */
export interface TargetPart {
  base: number | null
  bonus: number
  target: number | null
}

export interface DailyTargets {
  date: string
  macro_mode: 'grams' | 'percent'
  active_calories: number
  calories: TargetPart
  protein: TargetPart
  carbs: TargetPart
  fat: TargetPart
}

/** Effective targets for a day — active calories are folded into the goal. */
export function useDailyTargets(date: string) {
  return useQuery({
    queryKey: ['targets', date],
    queryFn: () => apiGet<DailyTargets>(`/api/settings/targets?date=${date}`),
  })
}
