import { useEffect, useRef, useState } from 'react'

export default function BarcodeScanner({
  onResult,
  onClose,
}: {
  onResult: (code: string) => void
  onClose: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [manual, setManual] = useState('')

  const cameraAvailable =
    typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && window.isSecureContext

  useEffect(() => {
    if (!cameraAvailable || !videoRef.current) return
    let stopped = false
    let controls: { stop: () => void } | undefined

    import('@zxing/browser')
      .then(async ({ BrowserMultiFormatReader }) => {
        if (stopped) return
        const reader = new BrowserMultiFormatReader()
        controls = await reader.decodeFromVideoDevice(undefined, videoRef.current!, (result) => {
          if (result) {
            controls?.stop()
            onResult(result.getText())
          }
        })
      })
      .catch((e) => setError(String(e)))

    return () => {
      stopped = true
      controls?.stop()
    }
  }, [cameraAvailable, onResult])

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
        <strong>Scan barcode</strong>
        <button className="secondary fixed" onClick={onClose}>
          Close
        </button>
      </div>
      {cameraAvailable ? (
        <video ref={videoRef} style={{ width: '100%', borderRadius: 8 }} muted playsInline />
      ) : (
        <p className="muted">
          Camera scanning needs HTTPS (available once the app is served via Tailscale). Enter the barcode
          number manually:
        </p>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="row" style={{ marginTop: 8 }}>
        <input
          type="text"
          inputMode="numeric"
          placeholder="Barcode number"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
        />
        <button className="fixed" onClick={() => manual && onResult(manual.trim())} disabled={!manual.trim()}>
          Look up
        </button>
      </div>
    </div>
  )
}
