import { useEffect, type ReactNode } from 'react'
import { X } from 'lucide-react'

export default function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
}) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div className="sheet">
        <div className="sheet-handle" />
        {title && (
          <div className="sheet-header">
            <span className="text-title">{title}</span>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: 'var(--muted)', padding: 12 }}
              aria-label="Close"
            >
              <X size={20} />
            </button>
          </div>
        )}
        {children}
      </div>
    </>
  )
}
