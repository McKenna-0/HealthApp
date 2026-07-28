export default function Stepper({
  value,
  onChange,
  min = 0,
  max = 99,
  step = 1,
  format,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  format?: (v: number) => string
}) {
  const dec = () => onChange(Math.max(min, Math.round((value - step) * 10) / 10))
  const inc = () => onChange(Math.min(max, Math.round((value + step) * 10) / 10))
  return (
    <div className="stepper">
      <button className="stepper-btn" onClick={dec} disabled={value <= min}>
        −
      </button>
      <span className="stepper-value">{format ? format(value) : value}</span>
      <button className="stepper-btn" onClick={inc} disabled={value >= max}>
        +
      </button>
    </div>
  )
}
