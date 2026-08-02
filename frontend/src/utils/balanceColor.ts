/**
 * Returns CSS color variable for an energy balance value relative to a target.
 * - target >= 0 (surplus goal): green if 0 <= balance <= target, red otherwise
 * - target < 0 (deficit goal): green if target <= balance <= 0, red otherwise
 * - target == null: legacy (surplus=red, deficit=green)
 */
export function getBalanceColor(balance: number, target: number | null): string {
  if (target == null) {
    return balance > 0 ? 'var(--red)' : 'var(--green)'
  }
  if (target >= 0) {
    return (balance >= 0 && balance <= target) ? 'var(--green)' : 'var(--red)'
  }
  // target < 0 (deficit goal)
  return (balance >= target && balance <= 0) ? 'var(--green)' : 'var(--red)'
}
