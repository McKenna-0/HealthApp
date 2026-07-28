import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiGet, apiPost, apiPut } from '../api/client'
import type { FoodItem, FoodLogRow, Meal, ServingOption } from '../api/types'
import CalorieDonut from '../components/CalorieDonut'
import ProgressBar from '../components/ProgressBar'

const NUTRI_COLORS: Record<string, string> = {
  a: '#038141', b: '#85bb2f', c: '#fecb02', d: '#ee8100', e: '#e63e11',
}
const ECO_COLORS = NUTRI_COLORS
const NOVA_COLORS: Record<number, string> = {
  1: '#038141', 2: '#85bb2f', 3: '#fecb02', 4: '#e63e11',
}

function NutriScoreBadge({ grade }: { grade: string }) {
  const g = grade.toLowerCase()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <span className="muted" style={{ fontSize: '0.65rem' }}>Nutri-Score</span>
      <div style={{
        background: NUTRI_COLORS[g] ?? '#888', color: '#fff', fontWeight: 700,
        width: 32, height: 32, borderRadius: 6, display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: '1rem', textTransform: 'uppercase',
      }}>{g}</div>
    </div>
  )
}

function NovaBadge({ group, label }: { group: number; label?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, maxWidth: 120 }}>
      <span className="muted" style={{ fontSize: '0.65rem' }}>NOVA Group</span>
      <div style={{
        background: NOVA_COLORS[group] ?? '#888', color: '#fff', fontWeight: 700,
        width: 32, height: 32, borderRadius: 6, display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: '1rem',
      }}>{group}</div>
      {label && <span className="muted" style={{ fontSize: '0.6rem', textAlign: 'center', lineHeight: 1.2 }}>{label}</span>}
    </div>
  )
}

function EcoScoreBadge({ grade }: { grade: string }) {
  const g = grade.toLowerCase()
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <span className="muted" style={{ fontSize: '0.65rem' }}>Eco-Score</span>
      <div style={{
        background: ECO_COLORS[g] ?? '#888', color: '#fff', fontWeight: 700,
        width: 32, height: 32, borderRadius: 6, display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: '1rem', textTransform: 'uppercase',
      }}>{g}</div>
    </div>
  )
}

const MEALS: Meal[] = ['breakfast', 'lunch', 'dinner', 'snack']
const MEAL_LABELS: Record<Meal, string> = {
  breakfast: 'Breakfast',
  lunch: 'Lunch',
  dinner: 'Dinner',
  snack: 'Snacks',
}

function nowHHMM() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const MICRO_LABELS: [string, string, string][] = [
  ['fiber_g', 'Fiber', 'g'],
  ['sugar_g', 'Sugars', 'g'],
  ['saturated_fat_g', 'Saturated Fat', 'g'],
  ['trans_fat_g', 'Trans Fat', 'g'],
  ['cholesterol_mg', 'Cholesterol', 'mg'],
  ['sodium_mg', 'Sodium', 'mg'],
  ['potassium_mg', 'Potassium', 'mg'],
  ['calcium_mg', 'Calcium', 'mg'],
  ['iron_mg', 'Iron', 'mg'],
  ['magnesium_mg', 'Magnesium', 'mg'],
  ['zinc_mg', 'Zinc', 'mg'],
  ['phosphorus_mg', 'Phosphorus', 'mg'],
  ['vitamin_a_mcg', 'Vitamin A', 'mcg'],
  ['vitamin_c_mg', 'Vitamin C', 'mg'],
  ['vitamin_d_mcg', 'Vitamin D', 'mcg'],
  ['vitamin_b6_mg', 'Vitamin B6', 'mg'],
  ['vitamin_b12_mcg', 'Vitamin B12', 'mcg'],
  ['folate_mcg', 'Folate', 'mcg'],
]

interface Targets {
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
  macro_mode: string | null
  protein_target_pct: number | null
  carbs_target_pct: number | null
  fat_target_pct: number | null
}

export default function FoodDetailPage() {
  const { meal: mealParam } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const date = params.get('date') ?? todayIso()
  const cacheId = params.get('cacheId')
  const logId = params.get('logId')
  const isEdit = !!logId

  const [meal, setMeal] = useState<Meal>((mealParam ?? 'snack') as Meal)
  const [servingIdx, setServingIdx] = useState(-1) // -1 = not yet initialised
  const [servings, setServings] = useState('1')
  const [time, setTime] = useState(nowHHMM())
  const [loaded, setLoaded] = useState(false)

  const servingOptions = useQuery({
    queryKey: ['food-servings', cacheId],
    queryFn: () => apiGet<ServingOption[]>(`/api/food/cache/${cacheId}/servings`),
    enabled: !!cacheId,
  })

  const existingLog = useQuery({
    queryKey: ['food-log-entry', logId],
    queryFn: () => apiGet<FoodLogRow[]>(`/api/food/log?date=${date}`).then(
      (rows) => rows.find((r) => r.id === Number(logId)) ?? null,
    ),
    enabled: isEdit,
  })

  // Fetch all favorites + recent to find our item
  const allRecent = useQuery({
    queryKey: ['food-recent'],
    queryFn: () => apiGet<FoodItem[]>('/api/food/recent'),
  })

  const allFavs = useQuery({
    queryKey: ['food-favorites'],
    queryFn: () => apiGet<FoodItem[]>('/api/food/favorites'),
  })

  const allCustom = useQuery({
    queryKey: ['food-custom'],
    queryFn: () => apiGet<FoodItem[]>('/api/food/custom'),
  })

  const targets = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiGet<Targets>('/api/settings'),
  })

  const nutrients = useQuery({
    queryKey: ['food-nutrients', cacheId],
    queryFn: () =>
      apiGet<{
        micronutrients: Record<string, number>
        scores?: {
          nutriscore_grade?: string
          nova_group?: number
          nova_group_label?: string
          ecoscore_grade?: string
          ingredients_text?: string
        }
      }>(`/api/food/cache/${cacheId}/nutrients`),
    enabled: !!cacheId,
  })

  const cid = Number(cacheId)

  // Direct lookup by ID — always enabled, acts as fallback when item isn't in recent/favs/custom
  const directLookup = useQuery({
    queryKey: ['food-cache-item', cacheId],
    queryFn: () => apiGet<FoodItem>(`/api/food/cache/${cacheId}`),
    enabled: !!cacheId,
  })

  // Find the food item from any loaded list or direct lookup
  const item: FoodItem | null =
    allRecent.data?.find((f) => f.id === cid) ??
    allFavs.data?.find((f) => f.id === cid) ??
    allCustom.data?.find((f) => f.id === cid) ??
    directLookup.data ??
    null

  // Initialise serving index once options load
  if (servingOptions.data && !loaded) {
    const opts = servingOptions.data
    if (isEdit && existingLog.data) {
      // Edit mode: reverse-compute from the logged quantity
      setLoaded(true)
      const entry = existingLog.data
      setMeal(entry.meal as Meal)
      if (entry.ts) {
        const timePart = entry.ts.split('T')[1]
        if (timePart) setTime(timePart.slice(0, 5))
      }
      const qty = entry.quantity_g ?? 100
      let bestIdx = opts.findIndex((o) => o.grams === 100)
      if (bestIdx < 0) bestIdx = 0
      for (let i = 0; i < opts.length; i++) {
        const ratio = qty / opts[i].grams
        if (Math.abs(ratio - Math.round(ratio)) < 0.01 && ratio >= 0.25) {
          bestIdx = i
          setServings(String(Math.round(ratio * 100) / 100))
          break
        }
      }
      setServingIdx(bestIdx)
    } else if (!isEdit && servingIdx === -1) {
      // New item: default to the food's recommended serving (first option)
      // which is serving_size_g if available, not 100g
      setLoaded(true)
      setServingIdx(0)
    }
  }

  const opts = servingOptions.data ?? [{ label: '100g', grams: 100 }]
  const actualIdx = servingIdx >= 0 ? servingIdx : 0
  const selectedServing = opts[actualIdx] ?? opts[0]
  const servingsNum = parseFloat(servings) || 1
  const finalGrams = selectedServing.grams * servingsNum

  const factor = finalGrams / 100
  const cal = Math.round((item?.kcal_per_100g ?? 0) * factor)
  const prot = item?.protein_g != null ? Math.round(item.protein_g * factor * 10) / 10 : null
  const carbs = item?.carbs_g != null ? Math.round(item.carbs_g * factor * 10) / 10 : null
  const fat = item?.fat_g != null ? Math.round(item.fat_g * factor * 10) / 10 : null

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['food-log'] })
    qc.invalidateQueries({ queryKey: ['food-recent'] })
    qc.invalidateQueries({ queryKey: ['streak'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['energy-balance'] })
    qc.invalidateQueries({ queryKey: ['tdee'] })
  }

  const save = useMutation({
    mutationFn: () => {
      const ts = `${date}T${time}:00`
      if (isEdit && logId) {
        return apiPut(`/api/food/log/${logId}`, {
          meal,
          quantity_g: finalGrams,
          ts,
        })
      }
      return apiPost('/api/food/log', {
        date,
        meal,
        food_cache_id: Number(cacheId),
        quantity_g: finalGrams,
        ts,
      })
    },
    onSuccess: () => {
      invalidate()
      navigate(`/log/food/${meal}?date=${date}`)
    },
  })

  const backPath = `/log/food/${mealParam ?? meal}?date=${date}`

  if (!item) {
    if (directLookup.isLoading || allRecent.isLoading) {
      return <p className="muted">Loading…</p>
    }
  }

  const t = targets.data
  // Resolve macro targets: if percent mode, compute grams from calorie target
  const proteinTarget = t?.macro_mode === 'percent' && t.calorie_target && t.protein_target_pct
    ? Math.round(t.calorie_target * t.protein_target_pct / 100 / 4)
    : t?.protein_target_g ?? null
  const carbsTarget = t?.macro_mode === 'percent' && t.calorie_target && t.carbs_target_pct
    ? Math.round(t.calorie_target * t.carbs_target_pct / 100 / 4)
    : t?.carbs_target_g ?? null
  const fatTarget = t?.macro_mode === 'percent' && t.calorie_target && t.fat_target_pct
    ? Math.round(t.calorie_target * t.fat_target_pct / 100 / 9)
    : t?.fat_target_g ?? null

  return (
    <>
      <div className="row" style={{ marginBottom: 8, marginTop: 8 }}>
        <button className="secondary fixed" onClick={() => navigate(backPath)}>
          ‹
        </button>
        <h1 style={{ margin: 0, flex: 1, textAlign: 'center', fontSize: '1.1rem' }}>
          {item?.name ?? 'Food'}
        </h1>
        <span className="fixed" style={{ width: 44 }} />
      </div>

      {item?.brand && (
        <p className="muted" style={{ textAlign: 'center', margin: '0 0 12px', fontSize: '0.82rem' }}>
          {item.brand}
        </p>
      )}

      <div className="card">
        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: 4 }}>
            Serving Size
          </label>
          <select
            className="serving-select"
            value={actualIdx}
            onChange={(e) => {
              setServingIdx(Number(e.target.value))
              setServings('1')
            }}
          >
            {opts.map((o, i) => (
              <option key={i} value={i}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: 4 }}>
            Number of Servings
          </label>
          <input
            type="number"
            inputMode="decimal"
            step="0.5"
            min="0.25"
            value={servings}
            onChange={(e) => setServings(e.target.value)}
            style={{ width: '100%', textAlign: 'center', fontSize: '1rem' }}
          />
        </div>

        <div className="row" style={{ gap: 12 }}>
          <div style={{ flex: '0 0 auto' }}>
            <label className="muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: 4 }}>
              Time
            </label>
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <label className="muted" style={{ fontSize: '0.75rem', display: 'block', marginBottom: 4 }}>
              Meal
            </label>
            <select
              className="serving-select"
              value={meal}
              onChange={(e) => setMeal(e.target.value as Meal)}
            >
              {MEALS.map((m) => (
                <option key={m} value={m}>
                  {MEAL_LABELS[m]}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {item && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <CalorieDonut calories={cal} protein_g={prot} carbs_g={carbs} fat_g={fat} />
        </div>
      )}

      {t && (t.calorie_target || proteinTarget || carbsTarget || fatTarget) && (
        <div className="card">
          <strong style={{ fontSize: '0.85rem' }}>% of Daily Goals</strong>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {t.calorie_target != null && (
              <div>
                <div className="row" style={{ justifyContent: 'space-between', fontSize: '0.78rem' }}>
                  <span>Calories</span>
                  <span className="muted">{Math.round((cal / t.calorie_target) * 100)}%</span>
                </div>
                <ProgressBar value={cal} target={t.calorie_target} />
              </div>
            )}
            {(
              [
                ['Carbs', carbs, carbsTarget, '#fbbf24'],
                ['Fat', fat, fatTarget, '#a78bfa'],
                ['Protein', prot, proteinTarget, '#4ade80'],
              ] as const
            ).map(([label, val, target, color]) =>
              target != null && val != null ? (
                <div key={label}>
                  <div className="row" style={{ justifyContent: 'space-between', fontSize: '0.78rem' }}>
                    <span>{label}</span>
                    <span className="muted">
                      {Math.round(val)}g / {Math.round(target)}g · {Math.round((val / target) * 100)}%
                    </span>
                  </div>
                  <ProgressBar value={val} target={target} color={color} />
                </div>
              ) : null,
            )}
          </div>
        </div>
      )}

      {nutrients.data?.scores && Object.keys(nutrients.data.scores).length > 0 && (
        <div className="card">
          <strong style={{ fontSize: '0.85rem' }}>Food Quality</strong>
          <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {nutrients.data.scores.nutriscore_grade && (
              <NutriScoreBadge grade={nutrients.data.scores.nutriscore_grade} />
            )}
            {nutrients.data.scores.nova_group != null && (
              <NovaBadge group={nutrients.data.scores.nova_group} label={nutrients.data.scores.nova_group_label} />
            )}
            {nutrients.data.scores.ecoscore_grade && (
              <EcoScoreBadge grade={nutrients.data.scores.ecoscore_grade} />
            )}
          </div>
          {nutrients.data.scores.ingredients_text && (
            <details style={{ marginTop: 8 }}>
              <summary className="muted" style={{ fontSize: '0.75rem', cursor: 'pointer' }}>Ingredients</summary>
              <p className="muted" style={{ fontSize: '0.72rem', margin: '4px 0 0', lineHeight: 1.4 }}>
                {nutrients.data.scores.ingredients_text}
              </p>
            </details>
          )}
        </div>
      )}

      {item && (
        <div className="card">
          <strong style={{ fontSize: '0.85rem' }}>Nutrition Facts</strong>
          <p className="muted" style={{ margin: '4px 0 8px', fontSize: '0.75rem' }}>
            Per {selectedServing.label} × {servingsNum} ({Math.round(finalGrams)}g)
          </p>
          <table className="nutrition-facts">
            <tbody>
              <tr>
                <td>Calories</td>
                <td>{cal} kcal</td>
              </tr>
              {prot != null && (
                <tr>
                  <td>Protein</td>
                  <td>{prot.toFixed(1)}g</td>
                </tr>
              )}
              {carbs != null && (
                <tr>
                  <td>Carbohydrates</td>
                  <td>{carbs.toFixed(1)}g</td>
                </tr>
              )}
              {fat != null && (
                <tr>
                  <td>Fat</td>
                  <td>{fat.toFixed(1)}g</td>
                </tr>
              )}
              {nutrients.data &&
                Object.keys(nutrients.data.micronutrients).length > 0 && (
                  <>
                    <tr>
                      <td colSpan={2} style={{ paddingTop: 10, fontWeight: 600, borderBottom: '2px solid var(--border)' }}>
                        Vitamins & Minerals
                      </td>
                    </tr>
                    {MICRO_LABELS.filter(([key]) => nutrients.data!.micronutrients[key] != null).map(
                      ([key, label, unit]) => {
                        const per100 = nutrients.data!.micronutrients[key]
                        const scaled = Math.round(per100 * factor * 100) / 100
                        return (
                          <tr key={key}>
                            <td>{label}</td>
                            <td>
                              {scaled < 1 ? scaled.toFixed(2) : scaled.toFixed(1)}
                              {unit}
                            </td>
                          </tr>
                        )
                      },
                    )}
                  </>
                )}
            </tbody>
          </table>
        </div>
      )}

      <button
        style={{ width: '100%', marginTop: 4 }}
        onClick={() => save.mutate()}
        disabled={save.isPending || !item}
      >
        {save.isPending ? 'Saving…' : isEdit ? 'Update' : 'Add'}
      </button>
      {save.isError && (
        <p className="error-text">{String(save.error).replace(/^\d+: /, '').slice(0, 120)}</p>
      )}
    </>
  )
}
