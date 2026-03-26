import { describe, it, expect, vi, beforeEach } from 'vitest'
import { invokeCapability, fetchPermissions } from '../api'

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

describe('invokeCapability', () => {
  it('returns parsed JSON on success (2xx)', async () => {
    mockFetch.mockResolvedValue({
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ success: true, invocation_id: 'inv-1', result: { flights: [] } }),
    })

    const result = await invokeCapability('http://localhost:9100', 'token', 'search_flights', { origin: 'SEA' })
    expect(result.success).toBe(true)
    expect(result.invocation_id).toBe('inv-1')

    // Verify correct request shape
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:9100/anip/invoke/search_flights',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ parameters: { origin: 'SEA' } }),
      }),
    )
  })

  it('returns structured failure on non-2xx JSON response (does NOT throw)', async () => {
    mockFetch.mockResolvedValue({
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        success: false,
        failure: { type: 'budget_exceeded', detail: 'Over budget', retry: false, resolution: { action: 'request_increase' } },
        invocation_id: 'inv-2',
      }),
    })

    const result = await invokeCapability('http://localhost:9100', 'token', 'book_flight', { flight: 'AA100' })
    expect(result.success).toBe(false)
    expect(result.failure.type).toBe('budget_exceeded')
    expect(result.invocation_id).toBe('inv-2')
  })

  it('throws on non-JSON response', async () => {
    mockFetch.mockResolvedValue({
      status: 502,
      headers: new Headers({ 'content-type': 'text/html' }),
    })

    await expect(invokeCapability('http://localhost:9100', 'token', 'search_flights', {}))
      .rejects.toThrow('non-JSON response')
  })
})

describe('fetchPermissions', () => {
  it('returns parsed JSON on success', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        available: [{ capability: 'search_flights', scope_match: 'flights:search' }],
        restricted: [],
        denied: [],
      }),
    })

    const result = await fetchPermissions('http://localhost:9100', 'token')
    expect(result.available).toHaveLength(1)
    expect(result.available[0].capability).toBe('search_flights')
  })

  it('passes capability in body when provided', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ available: [], restricted: [], denied: [] }),
    })

    await fetchPermissions('http://localhost:9100', 'token', 'search_flights')

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:9100/anip/permissions',
      expect.objectContaining({
        body: JSON.stringify({ capability: 'search_flights' }),
      }),
    )
  })

  it('sends empty body when no capability', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ available: [], restricted: [], denied: [] }),
    })

    await fetchPermissions('http://localhost:9100', 'token')

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:9100/anip/permissions',
      expect.objectContaining({
        body: JSON.stringify({}),
      }),
    )
  })

  it('throws on non-OK response', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 401 })

    await expect(fetchPermissions('http://localhost:9100', 'bad-token'))
      .rejects.toThrow('Permissions: 401')
  })
})
