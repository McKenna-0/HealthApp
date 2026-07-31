import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Camera, Plus, ScanLine, Search, Star, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiDelete, apiGet, apiPost } from '../api/client'
import type { FoodItem, FoodLogRow, Meal } from '../api/types'
import BarcodeScanner from '../components/BarcodeScanner'
import CustomFoodForm from '../components/CustomFoodForm'
import type { CustomFoodPrefill } from '../components/CustomFoodForm'
import LabelScanner from '../components/LabelScanner'
import SwipeToDelete from '../components/SwipeToDelete'

const MEAL_LABELS: Record<Meal, string> = {
  breakfast: 'Breakfast',
  lunch: 'Lunch',
  dinner: 'Dinner',
  snack: 'Snacks',
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function FoodLogPage() {
  const { meal: mealParam } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const meal = (mealParam ?? 'snack') as Meal
  const date = params.get('date') ?? todayIso()

  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [tab, setTab] = useState<'history' | 'favorites' | 'mine'>('history')
  const [scanning, setScanning] = useState(false)
  const [scanningLabel, setScanningLabel] = useState(false)
  const [labelPrefill, setLabelPrefill] = useState<CustomFoodPrefill | null>(null)
  const [barcodeMiss, setBarcodeMiss] = useState(false)
  const [showQuickAdd, setShowQuickAdd] = useState(false)
  const [freeText, setFreeText] = useState('')
  const [freeKcal, setFreeKcal] = useState('')
  const [justAdded, setJustAdded] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 500)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    if (!justAdded) return
    const t = setTimeout(() => setJustAdded(null), 2500)
    return () => clearTimeout(t)
  }, [justAdded])

  const searching = debounced.length >= 2
  const search = useQuery({
    queryKey: ['food-search', debounced],
    queryFn: () => apiGet<FoodItem[]>(`/api/food/search?q=${encodeURIComponent(debounced)}`),
    enabled: searching,
  })
  const recent = useQuery({
    queryKey: ['food-recent'],
    queryFn: () => apiGet<FoodItem[]>('/api/food/recent'),
  })
  const favs = useQuery({
    queryKey: ['food-favorites'],
    queryFn: () => apiGet<FoodItem[]>('/api/food/favorites'),
    enabled: tab === 'favorites',
  })
  const mine = useQuery({
    queryKey: ['food-custom'],
    queryFn: () => apiGet<FoodItem[]>('/api/food/custom'),
    enabled: tab === 'mine',
  })
  const log = useQuery({
    queryKey: ['food-log', date],
    queryFn: () => apiGet<FoodLogRow[]>(`/api/food/log?date=${date}`),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['food-log', date] })
    qc.invalidateQueries({ queryKey: ['food-recent'] })
    qc.invalidateQueries({ queryKey: ['streak'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['energy-balance'] })
    qc.invalidateQueries({ queryKey: ['tdee'] })
  }

  const addItem = useMutation({
    mutationFn: (payload: { food: FoodItem; qty: number }) =>
      apiPost('/api/food/log', {
        date,
        meal,
        food_cache_id: payload.food.id,
        quantity_g: payload.qty,
      }),
    onSuccess: (_, payload) => {
      setJustAdded(payload.food.name)
      invalidate()
    },
  })

  const addFree = useMutation({
    mutationFn: () =>
      apiPost('/api/food/log', {
        date,
        meal,
        description: freeText,
        calories: parseFloat(freeKcal),
      }),
    onSuccess: () => {
      setJustAdded(freeText)
      setFreeText('')
      setFreeKcal('')
      setShowQuickAdd(false)
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/food/log/${id}`),
    onSuccess: invalidate,
  })

  const toggleFavorite = useMutation({
    mutationFn: (id: number) => apiPost(`/api/food/favorite/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['food-favorites'] })
      qc.invalidateQueries({ queryKey: ['food-recent'] })
      qc.invalidateQueries({ queryKey: ['food-search'] })
      qc.invalidateQueries({ queryKey: ['food-custom'] })
    },
  })

  const barcodeLookup = useMutation({
    mutationFn: (code: string) =>
      apiGet<{ found: boolean; item?: FoodItem }>(`/api/food/barcode/${code}`),
    onSuccess: (data) => {
      setScanning(false)
      if (data.found && data.item) {
        navigateToDetail(data.item)
        setBarcodeMiss(false)
      } else {
        setBarcodeMiss(true)
        setTab('mine')
      }
    },
  })

  const navigateToDetail = (f: FoodItem) => {
    navigate(`/log/food/${meal}/detail?date=${date}&cacheId=${f.id}`)
  }

  const quickLog = (f: FoodItem) => {
    addItem.mutate({ food: f, qty: f.last_quantity_g ?? f.serving_size_g ?? 100 })
  }

  const mealEntries = (log.data ?? []).filter((e) => e.meal === meal)

  const lowerQuery = debounced.toLowerCase()
  const recentMatches = searching
    ? (recent.data ?? []).filter(
        (f) =>
          f.name.toLowerCase().includes(lowerQuery) ||
          (f.brand && f.brand.toLowerCase().includes(lowerQuery)),
      )
    : []
  const recentMatchIds = new Set(recentMatches.map((f) => f.id))
  const apiResults = searching
    ? (search.data ?? []).filter((f) => !recentMatchIds.has(f.id))
    : []
  const tabList = tab === 'history' ? recent.data : tab === 'favorites' ? favs.data : mine.data

  const renderFoodRow = (f: FoodItem) => (
    <div key={f.id} className="list-item">
      <div className="main" onClick={() => navigateToDetail(f)} style={{ cursor: 'pointer' }}>
        <div className="name">{f.name}</div>
        <div className="detail">
          {f.kcal_per_100g != null
            ? `${Math.round(
                (f.kcal_per_100g * (f.last_quantity_g ?? f.serving_size_g ?? 100)) / 100,
              )} cal · ${f.last_quantity_g ?? f.serving_size_g ?? 100}g`
            : ''}
          {f.brand ? ` · ${f.brand}` : ''}
        </div>
      </div>
      <button
        className="del fixed"
        style={{
          color: f.is_favorite ? 'var(--amber)' : 'var(--muted)',
          padding: '8px',
          minWidth: 44,
          minHeight: 44,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        onClick={() => toggleFavorite.mutate(f.id)}
        aria-label={f.is_favorite ? 'Remove favorite' : 'Add favorite'}
      >
        <Star size={16} fill={f.is_favorite ? 'var(--amber)' : 'none'} />
      </button>
      <button
        className="quick-add-btn fixed"
        onClick={() => quickLog(f)}
        disabled={addItem.isPending}
        title={`Add ${f.last_quantity_g ?? f.serving_size_g ?? 100}g`}
      >
        <Plus size={16} />
      </button>
    </div>
  )

  return (
    <>
      {/* Header */}
      <div className="row" style={{ marginBottom: 12, marginTop: 8 }}>
        <button
          className="secondary fixed"
          onClick={() => navigate(`/log?date=${date}`)}
          style={{ minWidth: 44, minHeight: 44, padding: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          aria-label="Back"
        >
          <ArrowLeft size={20} />
        </button>
        <h1 style={{ margin: 0, flex: 1, textAlign: 'center' }}>{MEAL_LABELS[meal]}</h1>
        <span className="fixed" style={{ width: 44 }} />
      </div>

      {/* Search */}
      <div className="row" style={{ marginBottom: 10, position: 'relative' }}>
        <Search size={16} style={{ position: 'absolute', left: 14, color: 'var(--muted)', pointerEvents: 'none' }} />
        <input
          placeholder="Search foods, brands…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ width: '100%', paddingLeft: 38, paddingRight: 14, paddingTop: 12, paddingBottom: 12, fontSize: '1rem' }}
        />
      </div>

      {/* Action buttons */}
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="secondary" onClick={() => setScanning(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center' }}>
          <Camera size={15} /> Barcode
        </button>
        <button className="secondary" onClick={() => setScanningLabel(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center' }}>
          <ScanLine size={15} /> Scan label
        </button>
        <button className="secondary" onClick={() => setShowQuickAdd((v) => !v)} style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center' }}>
          <Zap size={15} /> Quick add
        </button>
      </div>

      {scanning && (
        <BarcodeScanner onResult={(code) => barcodeLookup.mutate(code)} onClose={() => setScanning(false)} />
      )}

      {scanningLabel && (
        <LabelScanner
          onResult={(data) => {
            setScanningLabel(false)
            setLabelPrefill(data)
            setTab('mine')
          }}
          onClose={() => setScanningLabel(false)}
        />
      )}

      {showQuickAdd && (
        <div className="card" style={{ marginBottom: 12 }}>
          <p className="text-caption" style={{ marginBottom: 8 }}>Quick add (name + kcal)</p>
          <div className="row">
            <input placeholder="e.g. flat white" value={freeText} onChange={(e) => setFreeText(e.target.value)} style={{ minWidth: 0 }} />
            <input
              type="number"
              inputMode="numeric"
              placeholder="kcal"
              value={freeKcal}
              onChange={(e) => setFreeKcal(e.target.value)}
              style={{ maxWidth: 80, minWidth: 0 }}
            />
            <button className="fixed" onClick={() => addFree.mutate()} disabled={addFree.isPending || !freeText || !freeKcal}>
              Add
            </button>
          </div>
        </div>
      )}

      {justAdded && <div className="toast">Added {justAdded}</div>}

      {searching ? (
        <>
          {recentMatches.length > 0 && (
            <>
              <p className="settings-section-header" style={{ marginTop: 4 }}>Recent matches</p>
              <div className="card">{recentMatches.map(renderFoodRow)}</div>
            </>
          )}
          <p className="settings-section-header" style={{ marginTop: recentMatches.length ? undefined : 4 }}>
            Search results
            {search.isFetching && <span style={{ color: 'var(--muted)', fontWeight: 400, textTransform: 'none' }}> — searching…</span>}
          </p>
          <div className="card">
            {apiResults.length === 0 && !search.isFetching && (
              <p className="text-caption">No results.</p>
            )}
            {apiResults.map(renderFoodRow)}
          </div>
        </>
      ) : (
        <>
          <div className="tabs">
            {(
              [
                ['history', 'History'],
                ['favorites', 'Favorites'],
                ['mine', 'My foods'],
              ] as const
            ).map(([k, label]) => (
              <button key={k} className={`chip ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)}>
                {label}
              </button>
            ))}
          </div>
          {tab === 'history' && (
            <p className="settings-section-header" style={{ marginTop: 0 }}>Recently logged</p>
          )}
          <div className="card">
            {(tabList ?? []).length === 0 && <p className="text-caption">Nothing here yet.</p>}
            {(tabList ?? []).map(renderFoodRow)}
            {tab === 'mine' && (
              <>
                {barcodeMiss && (
                  <p className="error-text" style={{ marginBottom: 8 }}>Barcode not found — add it as a custom food:</p>
                )}
                <CustomFoodForm
                  prefill={labelPrefill ?? undefined}
                  onCreated={(item) => {
                    setLabelPrefill(null)
                    navigateToDetail(item)
                  }}
                />
              </>
            )}
          </div>
        </>
      )}

      {mealEntries.length > 0 && (
        <div className="card">
          <p className="text-body" style={{ fontWeight: 600, marginBottom: 8 }}>
            Added to {MEAL_LABELS[meal].toLowerCase()}
          </p>
          {mealEntries.map((e) => (
            <SwipeToDelete key={e.id} onDelete={() => remove.mutate(e.id)}>
              <div
                className="list-item"
                style={e.food_cache_id ? { cursor: 'pointer' } : undefined}
                onClick={
                  e.food_cache_id
                    ? () => navigate(`/log/food/${meal}/detail?date=${date}&logId=${e.id}&cacheId=${e.food_cache_id}`)
                    : undefined
                }
              >
                <div className="main">
                  <div className="name">{e.description ?? 'Food'}</div>
                  <div className="detail">
                    {e.quantity_g ? `${e.quantity_g}g · ` : ''}
                    {Math.round(e.calories)} cal
                  </div>
                </div>
              </div>
            </SwipeToDelete>
          ))}
          <div className="text-caption" style={{ textAlign: 'right', paddingTop: 8 }}>
            {Math.round(mealEntries.reduce((a, e) => a + e.calories, 0))} cal total
          </div>
        </div>
      )}

      <button style={{ width: '100%', marginTop: 4 }} onClick={() => navigate(`/log?date=${date}`)}>
        Done
      </button>
    </>
  )
}
