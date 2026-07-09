import type { ReactNode } from 'react'
import { ResponsiveContainer } from 'recharts'

export default function ChartCard({
  title,
  height = 180,
  children,
}: {
  title: string
  height?: number
  children: ReactNode
}) {
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <ResponsiveContainer width="100%" height={height}>
        {children as never}
      </ResponsiveContainer>
    </div>
  )
}
