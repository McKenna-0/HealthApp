import { type ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'

export default function MetricDrillDown({
  open,
  onClose,
  title,
  value,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  value?: string | number | null
  children: ReactNode
}) {
  if (!open) return null

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'var(--bg)',
      zIndex: 200,
      overflowY: 'auto',
      WebkitOverflowScrolling: 'touch',
      animation: 'sheet-up 0.3s ease-out',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '16px',
        paddingTop: 'calc(16px + env(safe-area-inset-top))',
        borderBottom: '1px solid var(--border)',
        position: 'sticky',
        top: 0,
        background: 'var(--bg)',
        zIndex: 1,
      }}>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: 'var(--text)', padding: 8, minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center' }}
          aria-label="Back"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <div className="text-title">{title}</div>
          {value != null && <div className="text-display">{value}</div>}
        </div>
      </div>
      <div style={{ padding: 16, paddingBottom: 'calc(32px + env(safe-area-inset-bottom))' }}>
        {children}
      </div>
    </div>
  )
}
