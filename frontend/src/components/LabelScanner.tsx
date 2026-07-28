import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import type { CustomFoodPrefill } from './CustomFoodForm'

export default function LabelScanner({
  onResult,
  onClose,
}: {
  onResult: (data: CustomFoodPrefill) => void
  onClose: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('image', file)
      const resp = await fetch('/api/food/ocr-label', {
        method: 'POST',
        body: form,
      })
      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(text || `HTTP ${resp.status}`)
      }
      return resp.json() as Promise<{ ocr: Record<string, unknown> }>
    },
    onSuccess: (data) => {
      const o = data.ocr
      onResult({
        name: typeof o.name === 'string' ? o.name : undefined,
        kcal: typeof o.calories === 'number' ? o.calories : undefined,
        protein_g: typeof o.protein_g === 'number' ? o.protein_g : null,
        carbs_g: typeof o.carbs_g === 'number' ? o.carbs_g : null,
        fat_g: typeof o.fat_g === 'number' ? o.fat_g : null,
        serving_size_g: typeof o.serving_size_g === 'number' ? o.serving_size_g : null,
        per_serving: true,
      })
    },
    onError: (err) => {
      setError(String(err).replace(/^\d+: /, '').slice(0, 120))
    },
  })

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setError(null)
      upload.mutate(file)
    }
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <strong>Scan nutrition label</strong>
        <button className="secondary fixed" onClick={onClose}>
          Close
        </button>
      </div>

      <p className="muted" style={{ marginBottom: 8, fontSize: '0.8rem' }}>
        Take a photo of a nutrition facts label to auto-fill the values.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFile}
        style={{ display: 'none' }}
      />

      <div className="row" style={{ gap: 8 }}>
        <button
          onClick={() => {
            if (inputRef.current) {
              inputRef.current.capture = 'environment'
              inputRef.current.click()
            }
          }}
          disabled={upload.isPending}
          style={{ flex: 1 }}
        >
          {upload.isPending ? 'Analysing...' : 'Take photo'}
        </button>
        <button
          className="secondary"
          onClick={() => {
            if (inputRef.current) {
              inputRef.current.removeAttribute('capture')
              inputRef.current.click()
            }
          }}
          disabled={upload.isPending}
          style={{ flex: 1 }}
        >
          Choose file
        </button>
      </div>

      {upload.isPending && (
        <p className="muted" style={{ textAlign: 'center', marginTop: 8 }}>
          Reading label with AI...
        </p>
      )}

      {error && <p className="error-text">{error}</p>}
    </div>
  )
}
