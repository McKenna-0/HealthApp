export default function MetricCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string | number | null | undefined
  sub?: string
}) {
  return (
    <div className="metric-card">
      <div className="label">{label}</div>
      <div className="value">{value ?? '–'}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}
