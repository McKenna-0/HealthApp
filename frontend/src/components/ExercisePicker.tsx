import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, X } from 'lucide-react'
import { useState } from 'react'
import { apiGet, apiPost } from '../api/client'
import type { Exercise } from '../api/types'

const MUSCLES = [
  'chest', 'front_delts', 'side_delts', 'rear_delts', 'biceps', 'triceps',
  'forearms', 'lats', 'traps', 'upper_back', 'lower_back', 'abs', 'obliques',
  'glutes', 'quads', 'hamstrings', 'calves',
]
const CATEGORIES = ['push', 'pull', 'legs', 'core', 'other']

export default function ExercisePicker({
  onPick,
  onClose,
}: {
  onPick: (exercise: Exercise) => void
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [category, setCategory] = useState('push')
  const [primary, setPrimary] = useState<string[]>([])

  const exercises = useQuery({
    queryKey: ['exercises'],
    queryFn: () => apiGet<Exercise[]>('/api/exercises'),
  })

  const create = useMutation({
    mutationFn: () =>
      apiPost<Exercise>('/api/exercises', {
        name: name.trim(),
        category,
        primary_muscles: primary,
        secondary_muscles: [],
      }),
    onSuccess: (ex) => {
      qc.invalidateQueries({ queryKey: ['exercises'] })
      onPick(ex)
    },
  })

  const filtered = (exercises.data ?? []).filter((e) =>
    e.name.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'var(--bg)',
      zIndex: 200,
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Fixed header */}
      <div style={{
        padding: '16px',
        paddingTop: 'calc(16px + env(safe-area-inset-top))',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--muted)',
              padding: 8,
              minWidth: 44,
              minHeight: 44,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
            aria-label="Close"
          >
            <X size={20} />
          </button>
          <span className="text-title">{creating ? 'New exercise' : 'Add Exercise'}</span>
        </div>
        {!creating && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--card)',
            borderRadius: 10,
            padding: '10px 12px',
          }}>
            <Search size={16} color="var(--muted)" />
            <input
              type="text"
              placeholder="Search exercises…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                color: 'var(--text)',
                fontSize: '1rem',
                outline: 'none',
              }}
            />
          </div>
        )}
      </div>

      {/* Scrollable content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        WebkitOverflowScrolling: 'touch' as React.CSSProperties['WebkitOverflowScrolling'],
        padding: '8px 16px',
        paddingBottom: 'max(16px, env(safe-area-inset-bottom))',
      }}>
        {!creating ? (
          <>
            {filtered.map((e) => (
              <button
                key={e.id}
                onClick={() => onPick(e)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '14px 0',
                  borderTop: 'none',
                  borderLeft: 'none',
                  borderRight: 'none',
                  borderBottom: '1px solid var(--border)',
                  background: 'none',
                  color: 'var(--text)',
                  minHeight: 44,
                  cursor: 'pointer',
                }}
              >
                <div className="text-body">{e.name}</div>
                <div className="text-caption" style={{ marginTop: 2 }}>
                  {e.category}{e.equipment ? ` · ${e.equipment}` : ''}
                  {e.primary_muscles?.length ? ` · ${e.primary_muscles.slice(0, 3).join(', ')}` : ''}
                </div>
              </button>
            ))}
            {filtered.length === 0 && exercises.data && (
              <p className="text-caption" style={{ color: 'var(--muted)', padding: '16px 0' }}>No matches.</p>
            )}
            <button
              onClick={() => { setName(query); setCreating(true) }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '14px 0',
                background: 'none',
                border: 'none',
                color: 'var(--accent)',
                minHeight: 44,
                cursor: 'pointer',
                fontSize: '0.9rem',
              }}
            >
              <Plus size={18} /> Create new exercise
            </button>
          </>
        ) : (
          <div style={{ paddingTop: 8 }}>
            <input
              placeholder="Exercise name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              style={{ width: '100%', marginBottom: 12, fontSize: '1rem' }}
            />
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Category</div>
            <div className="tabs" style={{ marginBottom: 12 }}>
              {CATEGORIES.map((c) => (
                <button key={c} className={`chip ${category === c ? 'active' : ''}`} onClick={() => setCategory(c)}>
                  {c}
                </button>
              ))}
            </div>
            <div className="text-caption" style={{ color: 'var(--muted)', marginBottom: 6 }}>Primary muscles (for heatmap)</div>
            <div className="tabs" style={{ flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
              {MUSCLES.map((mu) => (
                <button
                  key={mu}
                  className={`chip ${primary.includes(mu) ? 'active' : ''}`}
                  onClick={() =>
                    setPrimary((p) => (p.includes(mu) ? p.filter((x) => x !== mu) : [...p, mu]))
                  }
                >
                  {mu.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
            {create.isError && (
              <p className="error-text">{String(create.error).replace(/^\d+: /, '').slice(0, 120)}</p>
            )}
            <div className="row" style={{ marginTop: 8 }}>
              <button className="secondary" onClick={() => setCreating(false)}>Back</button>
              <button onClick={() => create.mutate()} disabled={name.trim().length < 2 || create.isPending}>
                Create & add
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
