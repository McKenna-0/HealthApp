const OPTIONS = [7, 30, 90]

export default function RangePicker({
  value,
  onChange,
}: {
  value: number
  onChange: (days: number) => void
}) {
  return (
    <div className="tabs">
      {OPTIONS.map((d) => (
        <button
          key={d}
          className={`chip ${value === d ? 'active' : ''}`}
          onClick={() => onChange(d)}
        >
          {d}d
        </button>
      ))}
    </div>
  )
}
