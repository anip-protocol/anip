const headers = (bearer?: string): HeadersInit => {
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  if (bearer) h['Authorization'] = `Bearer ${bearer}`
  return h
}

export async function fetchDiscovery(baseUrl: string) {
  const res = await fetch(`${baseUrl}/.well-known/anip`)
  if (!res.ok) throw new Error(`Discovery: ${res.status}`)
  return res.json()
}

export async function fetchManifest(baseUrl: string) {
  const res = await fetch(`${baseUrl}/anip/manifest`)
  if (!res.ok) throw new Error(`Manifest: ${res.status}`)
  const signature = res.headers.get('X-ANIP-Signature') || ''
  const body = await res.json()
  return { manifest: body, signature }
}

export async function fetchJwks(baseUrl: string) {
  const res = await fetch(`${baseUrl}/.well-known/jwks.json`)
  if (!res.ok) throw new Error(`JWKS: ${res.status}`)
  return res.json()
}

export async function fetchAudit(
  baseUrl: string,
  bearer: string,
  filters?: Record<string, string>,
) {
  const params = new URLSearchParams(filters || {})
  const url = `${baseUrl}/anip/audit${params.toString() ? '?' + params : ''}`
  const res = await fetch(url, {
    method: 'POST',
    headers: headers(bearer),
    body: '{}',
  })
  if (!res.ok) throw new Error(`Audit: ${res.status}`)
  return res.json()
}

export async function fetchCheckpoints(baseUrl: string, limit = 20) {
  const res = await fetch(`${baseUrl}/anip/checkpoints?limit=${limit}`)
  if (!res.ok) throw new Error(`Checkpoints: ${res.status}`)
  return res.json()
}

export async function fetchCheckpointDetail(baseUrl: string, id: string) {
  const res = await fetch(`${baseUrl}/anip/checkpoints/${id}`)
  if (!res.ok) throw new Error(`Checkpoint: ${res.status}`)
  return res.json()
}

export async function invokeCapability(
  baseUrl: string,
  bearer: string,
  capability: string,
  inputs: Record<string, any>,
): Promise<any> {
  const res = await fetch(`${baseUrl}/anip/invoke/${capability}`, {
    method: 'POST',
    headers: headers(bearer),
    body: JSON.stringify({ parameters: inputs }),
  })
  // ANIP returns invocation failures as non-2xx JSON bodies.
  // Parse the body regardless of status — InvokeResult needs the full
  // { success, failure, invocation_id } payload for structured failure UX.
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return res.json()
  }
  // Non-JSON response is a transport error — throw.
  throw new Error(`Invoke ${capability}: ${res.status} (non-JSON response)`)
}

export async function fetchPermissions(
  baseUrl: string,
  bearer: string,
  capability?: string,
): Promise<any> {
  const res = await fetch(`${baseUrl}/anip/permissions`, {
    method: 'POST',
    headers: headers(bearer),
    body: JSON.stringify(capability ? { capability } : {}),
  })
  if (!res.ok) throw new Error(`Permissions: ${res.status}`)
  return res.json()
}
