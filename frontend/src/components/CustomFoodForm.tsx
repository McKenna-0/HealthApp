import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiPost } from '../api/client'
import type { FoodItem } from '../api/types'

export interface CustomFoodPrefill {
  name?: string
  kcal?: number
  protein_g?: number | null
  carbs_g?: number | null
  fat_g?: number | null
  serving_size_g?: number | null
  per_serving?: boolean
}

export default function CustomFoodForm({
  prefillName,
  prefill,
  onCreated,
}: {
  prefillName?: string
  prefill?: CustomFoodPrefill
  onCreated?: (item: FoodItem) => void
}) {
  const qc = useQueryClient()
  const [name, setName] = useState(prefill?.name ?? prefillName ?? '')
  const [kcal, setKcal] = useState(prefill?.kcal?.toString() ?? '')
  const [protein, setProtein] = useState(prefill?.protein_g?.toString() ?? '')
  const [carbs, setCarbs] = useState(prefill?.carbs_g?.toString() ?? '')
  const [fat, setFat] = useState(prefill?.fat_g?.toString() ?? '')
  const [servingG, setServingG] = useState(prefill?.serving_size_g?.toString() ?? '')
  const [perServing, setPerServing] = useState(prefill?.per_serving ?? false)

  // Update form when prefill changes (e.g. OCR result arrives)
  useEffect(() => {
    if (prefill) {
      setName(prefill.name ?? '')
      setKcal(prefill.kcal?.toString() ?? '')
      setProtein(prefill.protein_g?.toString() ?? '')
      setCarbs(prefill.carbs_g?.toString() ?? '')
      setFat(prefill.fat_g?.toString() ?? '')
      setServingG(prefill.serving_size_g?.toString() ?? '')
      setPerServing(prefill.per_serving ?? false)
    }
  }, [prefill])

  const add = useMutation({
    mutationFn: () =>
      apiPost<FoodItem>('/api/food/custom', {
        name,
        per_serving: perServing,
        serving_size_g: servingG ? parseFloat(servingG) : null,
        kcal: parseFloat(kcal),
        protein_g: protein ? parseFloat(protein) : null,
        carbs_g: carbs ? parseFloat(carbs) : null,
        fat_g: fat ? parseFloat(fat) : null,
      }),
    onSuccess: (item) => {
      setName('')
      setKcal('')
      setProtein('')
      setCarbs('')
      setFat('')
      setServingG('')
      qc.invalidateQueries({ queryKey: ['food-custom'] })
      onCreated?.(item)
    },
  })

  return (
    <div style={{ marginTop: 12, borderTop: '1px solid #334155', paddingTop: 12 }}>
      <div className="muted" style={{ marginBottom: 8 }}>
        Add a custom food
      </div>
      <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
      <div className="row" style={{ marginBottom: 8 }}>
        <input type="number" inputMode="decimal" placeholder="kcal" value={kcal} onChange={(e) => setKcal(e.target.value)} />
        <input type="number" inputMode="decimal" placeholder="protein g" value={protein} onChange={(e) => setProtein(e.target.value)} />
        <input type="number" inputMode="decimal" placeholder="carbs g" value={carbs} onChange={(e) => setCarbs(e.target.value)} />
        <input type="number" inputMode="decimal" placeholder="fat g" value={fat} onChange={(e) => setFat(e.target.value)} />
      </div>
      <div className="row" style={{ marginBottom: 8 }}>
        <label className="muted" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox"
            checked={perServing}
            onChange={(e) => setPerServing(e.target.checked)}
            style={{ width: 'auto' }}
          />
          values are per serving
        </label>
        <input
          type="number"
          inputMode="decimal"
          placeholder="serving g"
          value={servingG}
          onChange={(e) => setServingG(e.target.value)}
        />
      </div>
      <button onClick={() => add.mutate()} disabled={add.isPending || !name || !kcal || (perServing && !servingG)}>
        Save custom food
      </button>
      {add.isError && <p className="error-text">{String(add.error).slice(0, 120)}</p>}
    </div>
  )
}
