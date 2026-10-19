async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.text()
    throw new Error(`${resp.status}: ${body}`)
  }
  // A 200 carrying HTML means the request fell through to the SPA shell rather
  // than reaching the route — a server running code that predates the endpoint,
  // or a stale service worker. Say so, instead of throwing an opaque JSON
  // parse error that reads like the data is merely missing.
  const contentType = resp.headers.get('content-type') ?? ''
  if (!contentType.includes('json')) {
    throw new Error(
      `Expected JSON from ${resp.url} but got "${contentType || 'unknown'}". ` +
        'The server may be running an older build than this app.',
    )
  }
  return resp.json() as Promise<T>
}

export function apiGet<T>(path: string): Promise<T> {
  return fetch(path).then((r) => handle<T>(r))
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return fetch(path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }).then((r) => handle<T>(r))
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((r) => handle<T>(r))
}

export function apiDelete<T>(path: string): Promise<T> {
  return fetch(path, { method: 'DELETE' }).then((r) => handle<T>(r))
}
