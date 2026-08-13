import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import { apiPut } from '../api/client'
import type { Workout } from '../api/types'

const MAX_NAME = 80

const ellipsis: CSSProperties = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
}

/** Workout title that turns into a text field when tapped. Font is inherited
 *  from the heading it sits in, so callers keep control of the type scale. */
export default function EditableWorkoutName({
  workoutId,
  name,
  editable = true,
  align = 'left',
}: {
  workoutId: number
  name: string | null
  editable?: boolean
  align?: 'left' | 'center'
}) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  const rename = useMutation({
    mutationFn: (next: string) =>
      apiPut<Workout>(`/api/workouts/${workoutId}/name`, { name: next }),
    onSuccess: () => {
      setEditing(false)
      for (const key of [['workout'], ['workout-summary'], ['workouts'], ['active-session']]) {
        qc.invalidateQueries({ queryKey: key })
      }
    },
  })

  const label = name ?? 'Workout'

  if (!editable) return <span style={ellipsis}>{label}</span>

  if (editing) {
    const commit = () => {
      const next = draft.trim()
      if (!next || next === label) {
        setEditing(false)
        return
      }
      rename.mutate(next)
    }
    return (
      <>
        <input
          value={draft}
          autoFocus
          maxLength={MAX_NAME}
          disabled={rename.isPending}
          aria-label="Workout name"
          onFocus={(e) => e.target.select()}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commit()
            } else if (e.key === 'Escape') {
              setEditing(false)
            }
          }}
          style={{ width: '100%', minHeight: 44, padding: '4px 8px', textAlign: align }}
        />
        {rename.isError && (
          // span, not p: this renders inside the page's <h1>, whose weight it
          // would otherwise inherit
          <span className="error-text" style={{ display: 'block', fontWeight: 400 }}>
            {String(rename.error).replace(/^\d+: /, '').slice(0, 120)}
          </span>
        )}
      </>
    )
  }

  return (
    <button
      type="button"
      title="Tap to rename"
      onClick={() => {
        setDraft(name ?? '')
        setEditing(true)
      }}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: align === 'center' ? 'center' : 'flex-start',
        gap: 6,
        width: '100%',
        minHeight: 44,
        // keep the pencil off the screen edge when a long name fills the row
        padding: align === 'center' ? 0 : '0 8px 0 0',
        background: 'none',
        border: 'none',
        color: 'inherit',
        font: 'inherit',
        textAlign: align,
        overflow: 'hidden',
      }}
    >
      <span style={ellipsis}>{label}</span>
      <Pencil size={14} color="var(--muted)" style={{ flexShrink: 0 }} />
    </button>
  )
}
