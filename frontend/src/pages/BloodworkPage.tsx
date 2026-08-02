import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'
import { apiDelete, apiGet, apiPost } from '../api/client'
import BottomSheet from '../components/BottomSheet'
import ChartCard from '../components/ChartCard'
import SkeletonLoader from '../components/SkeletonLoader'
import SwipeToDelete from '../components/SwipeToDelete'

interface MarkerRef {
  marker: string
  unit: string
  low: number | null
  high: number | null
  group: string
}

interface Result {
  id: number
  marker: string
  value: number
  unit: string
  ref_low: number | null
  ref_high: number | null
  flag: 'low' | 'high' | null
}

interface Panel {
  id: number
  date: string
  lab_name: string | null
  note: string | null
  results: Result[]
}

interface HistoryPoint extends Result {
  date: string
}

const axisStyle = { fontSize: 10, fill: '#94a3b8' }
const tooltipStyle = {
  contentStyle: { background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function BloodworkPage() {
  const qc = useQueryClient()
  const [historyMarker, setHistoryMarker] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const markers = useQuery({
    queryKey: ['blood-markers'],
    queryFn: () => apiGet<MarkerRef[]>('/api/bloodwork/markers'),
  })
  const panels = useQuery({
    queryKey: ['blood-panels'],
    queryFn: () => apiGet<Panel[]>('/api/bloodwork/panels'),
  })
  const history = useQuery({
    queryKey: ['blood-history', historyMarker],
    queryFn: () => apiGet<HistoryPoint[]>(`/api/bloodwork/history?marker=${encodeURIComponent(historyMarker!)}`),
    enabled: !!historyMarker,
  })

  const deletePanel = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/bloodwork/panels/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['blood-panels'] }),
  })

  const historyRef = markers.data?.find((m) => m.marker === historyMarker)

  return (
    <>
      <h1>Bloodwork</h1>

      <button
        style={{ width: '100%', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
        onClick={() => setSheetOpen(true)}
      >
        <Plus size={16} />
        Add panel
      </button>

      <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Add Panel">
        <PanelForm
          markers={markers.data ?? []}
          onSaved={() => setSheetOpen(false)}
        />
      </BottomSheet>

      {historyMarker && (history.data?.length ?? 0) >= 2 && (
        <ChartCard title={`${historyMarker} history (${historyRef?.unit ?? ''})`}>
          <LineChart data={history.data}>
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={axisStyle} minTickGap={30} />
            <YAxis tick={axisStyle} width={45} domain={['auto', 'auto']} />
            <Tooltip {...tooltipStyle} />
            {historyRef?.low != null && <ReferenceLine y={historyRef.low} stroke="#fbbf24" strokeDasharray="4 4" />}
            {historyRef?.high != null && <ReferenceLine y={historyRef.high} stroke="#fbbf24" strokeDasharray="4 4" />}
            <Line dataKey="value" stroke="#38bdf8" strokeWidth={2} dot={{ r: 2.5, fill: '#38bdf8' }} />
          </LineChart>
        </ChartCard>
      )}
      {historyMarker && (history.data?.length ?? 0) < 2 && (
        <p className="text-caption" style={{ margin: '0 4px 12px' }}>Log {historyMarker} in at least two panels to see a trend.</p>
      )}

      {panels.isLoading && (
        <div>
          {[1, 2].map((i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <SkeletonLoader height="100px" borderRadius="14px" />
            </div>
          ))}
        </div>
      )}

      {(panels.data ?? []).map((p) => (
        <SwipeToDelete key={p.id} onDelete={() => deletePanel.mutate(p.id)} confirm>
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="text-body" style={{ fontWeight: 600 }}>
                {p.date}
                {p.lab_name ? ` · ${p.lab_name}` : ''}
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Marker</th>
                  <th>Value</th>
                  <th>Range</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {p.results.map((r) => (
                  <tr key={r.id} onClick={() => setHistoryMarker(r.marker)} style={{ cursor: 'pointer' }}>
                    <td>{r.marker}</td>
                    <td style={{ color: r.flag ? 'var(--red)' : undefined, fontWeight: r.flag ? 700 : undefined }}>
                      {r.value} {r.unit}
                    </td>
                    <td className="text-caption">
                      {r.ref_low ?? ''}–{r.ref_high ?? ''}
                    </td>
                    <td>{r.flag && <span className="badge error">{r.flag}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SwipeToDelete>
      ))}
      {!panels.isLoading && (panels.data ?? []).length === 0 && (
        <p className="text-caption" style={{ margin: '0 4px' }}>No panels logged yet.</p>
      )}
    </>
  )
}

function PanelForm({ markers, onSaved }: { markers: MarkerRef[]; onSaved: () => void }) {
  const qc = useQueryClient()
  const [date, setDate] = useState(todayIso())
  const [lab, setLab] = useState('')
  const [rows, setRows] = useState<{ marker: string; value: string }[]>([{ marker: '', value: '' }])

  const add = useMutation({
    mutationFn: () => {
      const results = rows
        .filter((r) => r.marker && r.value)
        .map((r) => {
          const ref = markers.find((m) => m.marker === r.marker)
          return {
            marker: r.marker,
            value: parseFloat(r.value),
            unit: ref?.unit ?? '-',
            ref_low: ref?.low ?? null,
            ref_high: ref?.high ?? null,
          }
        })
      return apiPost('/api/bloodwork/panels', { date, lab_name: lab || null, results })
    },
    onSuccess: () => {
      setRows([{ marker: '', value: '' }])
      setLab('')
      qc.invalidateQueries({ queryKey: ['blood-panels'] })
      qc.invalidateQueries({ queryKey: ['blood-history'] })
      onSaved()
    },
  })

  const groups = [...new Set(markers.map((m) => m.group))]
  const valid = rows.some((r) => r.marker && r.value)

  return (
    <div style={{ paddingBottom: 8 }}>
      <div className="row" style={{ marginBottom: 12 }}>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <input placeholder="Lab (optional)" value={lab} onChange={(e) => setLab(e.target.value)} />
      </div>

      {rows.map((row, i) => {
        const ref = markers.find((m) => m.marker === row.marker)
        return (
          <div className="row" style={{ marginBottom: 8 }} key={i}>
            <select
              value={row.marker}
              onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, marker: e.target.value } : r)))}
            >
              <option value="">Marker…</option>
              {groups.map((g) => (
                <optgroup key={g} label={g}>
                  {markers
                    .filter((m) => m.group === g)
                    .map((m) => (
                      <option key={m.marker} value={m.marker}>
                        {m.marker}
                      </option>
                    ))}
                </optgroup>
              ))}
            </select>
            <input
              type="number"
              inputMode="decimal"
              placeholder={ref ? ref.unit : 'value'}
              value={row.value}
              onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))}
            />
          </div>
        )
      })}

      <div className="row" style={{ marginTop: 4 }}>
        <button
          className="secondary"
          onClick={() => setRows([...rows, { marker: '', value: '' }])}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Plus size={14} /> Row
        </button>
        <button onClick={() => add.mutate()} disabled={add.isPending || !valid}>
          {add.isPending ? 'Saving…' : 'Save panel'}
        </button>
      </div>
      {add.isError && <p className="error-text" style={{ marginTop: 8 }}>{String(add.error).slice(0, 120)}</p>}
    </div>
  )
}
