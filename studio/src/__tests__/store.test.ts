import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

async function loadStore() {
  vi.resetModules()
  return await import('../store')
}

beforeEach(() => {
  mockFetch.mockReset()
  window.history.replaceState({}, '', '/')
})

describe('initFromConfig', () => {
  it('does not auto-connect the full Studio product as an ANIP service', async () => {
    const { initFromConfig, store } = await loadStore()
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ embedded: false }),
    })

    await initFromConfig()

    expect(store.baseUrl).toBe('')
    expect(store.connected).toBe(false)
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('does not auto-connect to SPA fallback HTML from connect query', async () => {
    const { initFromConfig, store } = await loadStore()
    window.history.replaceState({}, '', '/inspect/discovery?connect=http%3A%2F%2Flocalhost%3A8080')
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ embedded: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'text/html' }),
      })

    await initFromConfig()

    expect(store.baseUrl).toBe('')
    expect(store.connected).toBe(false)
  })
})
