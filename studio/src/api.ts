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
