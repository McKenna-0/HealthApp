import { useRef, useState, type ReactNode } from 'react'
import { Trash2 } from 'lucide-react'

export default function SwipeToDelete({
  onDelete,
  confirm = false,
  children,
}: {
  onDelete: () => void
  confirm?: boolean
  children: ReactNode
}) {
  const startX = useRef(0)
  const currentX = useRef(0)
  const [offset, setOffset] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const threshold = containerRef.current
    ? containerRef.current.offsetWidth * 0.5
    : 150

  function handleTouchStart(e: React.TouchEvent) {
    startX.current = e.touches[0].clientX
    currentX.current = startX.current
  }

  function handleTouchMove(e: React.TouchEvent) {
    currentX.current = e.touches[0].clientX
    const diff = startX.current - currentX.current
    if (diff > 0) setOffset(diff)
  }

  function handleTouchEnd() {
    if (offset > threshold) {
      triggerDelete()
    } else {
      setOffset(0)
    }
  }

  function triggerDelete() {
    if (confirm && !window.confirm('Are you sure?')) {
      setOffset(0)
      return
    }
    if (navigator.vibrate) navigator.vibrate(10)
    setDeleting(true)
    setTimeout(() => onDelete(), 200)
  }

  if (deleting) {
    return <div className="swipe-deleting" style={{ maxHeight: 0 }} />
  }

  return (
    <div className="swipe-container" ref={containerRef}>
      {offset > 0 && (
        <div className="swipe-delete-bg" onClick={() => triggerDelete()}>
          <Trash2 size={20} />
        </div>
      )}
      <div
        className="swipe-content"
        style={{ transform: `translateX(-${offset}px)` }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {children}
      </div>
    </div>
  )
}
