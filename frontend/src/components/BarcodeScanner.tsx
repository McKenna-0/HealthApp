import { useEffect, useRef, useState } from 'react'

export default function BarcodeScanner({
  onResult,
  onClose,
}: {
  onResult: (code: string) => void
  onClose: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const onResultRef = useRef(onResult)
  onResultRef.current = onResult
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState('')
  const [active, setActive] = useState(true)
  const [cameraStarted, setCameraStarted] = useState(false)

  const cameraAvailable =
    typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && window.isSecureContext

  useEffect(() => {
    if (!cameraAvailable || !videoRef.current || !active) return
    let stopped = false
    let controls: { stop: () => void } | undefined

    ;(async () => {
      try {
        const { BrowserMultiFormatReader } = await import('@zxing/browser')
        if (stopped) return
        const reader = new BrowserMultiFormatReader()
        controls = await reader.decodeFromVideoDevice(
          undefined,
          videoRef.current!,
          (result, _err) => {
            if (!stopped) setCameraStarted(true)
            if (result) {
              const text = result.getText()
              if (text && text.length >= 6) {
                controls?.stop()
                setActive(false)
                onResultRef.current(text)
              }
            }
            // err is normal when no barcode is in frame — ignore
          },
        )
        if (!stopped) setCameraStarted(true)
      } catch (e) {
        if (!stopped) {
          setError(
            String(e).includes('Permission')
              ? 'Camera permission denied'
              : String(e).includes('NotFound')
                ? 'No camera found'
                : `Camera error: ${String(e).slice(0, 80)}`,
          )
        }
      }
    })()

    return () => {
      stopped = true
      controls?.stop()
    }
  }, [cameraAvailable, active])

  const submit = () => {
    const code = manual.trim()
    if (code) onResult(code)
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <strong>Scan barcode</strong>
        <button className="secondary fixed" onClick={onClose}>
          Close
        </button>
      </div>

      {cameraAvailable && (
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <video
            ref={videoRef}
            style={{
              width: '100%',
              borderRadius: 8,
              display: active ? 'block' : 'none',
              background: '#000',
              minHeight: active && !cameraStarted ? 200 : undefined,
            }}
            muted
            playsInline
          />
          {active && !cameraStarted && !error && (
            <p className="muted" style={{ textAlign: 'center', margin: '8px 0' }}>
              Starting camera…
            </p>
          )}
          {!active && (
            <p className="muted" style={{ textAlign: 'center', margin: '8px 0' }}>
              Looking up barcode…
            </p>
          )}
          {active && cameraStarted && (
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '10%',
                right: '10%',
                height: 2,
                background: 'var(--red)',
                opacity: 0.7,
                pointerEvents: 'none',
              }}
            />
          )}
        </div>
      )}

      {!cameraAvailable && (
        <p className="muted" style={{ marginBottom: 8 }}>
          Camera requires HTTPS. Enter the barcode number manually:
        </p>
      )}

      {error && <p className="error-text">{error}</p>}

      <div className="muted" style={{ fontSize: '0.75rem', marginBottom: 6 }}>
        {cameraAvailable ? 'Or enter barcode manually:' : ''}
      </div>
      <div className="row">
        <input
          type="text"
          inputMode="numeric"
          placeholder="e.g. 5000128065363"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          autoFocus={!cameraAvailable}
        />
        <button className="fixed" onClick={submit} disabled={!manual.trim()}>
          Look up
        </button>
      </div>
    </div>
  )
}
