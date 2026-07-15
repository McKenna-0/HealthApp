import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        {!creating ? (
          <>
            <div className="row" style={{ marginBottom: 8 }}>
              <input
                autoFocus
                placeholder="Search exercises…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button className="secondary fixed" onClick={onClose}>✕</button>
            </div>
            <div className="sheet-list">
              {filtered.map((e) => (
                <div key={e.id} className="list-item" style={{ cursor: 'pointer' }} onClick={() => onPick(e)}>
                  <div className="main">
                    <div className="name">{e.name}</div>
                    <div className="detail">
                      {e.category}
                      {e.equipment ? ` · ${e.equipment}` : ''}
                    </div>
                  </div>
                  <span className="muted">+</span>
                </div>
              ))}
              {filtered.length === 0 && <p className="muted">No matches.</p>}
            </div>
            <button
              className="secondary"
              style={{ width: '100%', marginTop: 8 }}
              onClick={() => {
                setName(query)
                setCreating(true)
              }}
            >
              + Create new exercise
            </button>
          </>
        ) : (
          <>
            <h2 style={{ marginTop: 0 }}>New exercise</h2>
            <input
              placeholder="Exercise name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ width: '100%', marginBottom: 8 }}
            />
            <div className="tabs">
              {CATEGORIES.map((c) => (
                <button key={c} className={`chip ${category === c ? 'active' : ''}`} onClick={() => setCategory(c)}>
                  {c}
                </button>
              ))}
            </div>
            <p className="muted" style={{ margin: '4px 0' }}>Primary muscles (for the heatmap)</p>
            <div className="tabs">
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
          </>
        )}
      </div>
    </div>
  )
}
