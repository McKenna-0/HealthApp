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
          style={{ minHeight: 44 }}  // HIG tap target; the chip's padding alone is 33px
        >
          {d}d
        </button>
      ))}
    </div>
  )
}
