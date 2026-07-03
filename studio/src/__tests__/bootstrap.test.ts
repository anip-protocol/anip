import { describe, expect, it, vi } from 'vitest'

describe('mountStudioApp', () => {
  it('mounts Vue immediately while config initialization continues in the background', async () => {
    vi.resetModules()
    let resolveInit!: () => void
    const initFromConfig = vi.fn(() => new Promise<void>((resolve) => {
      resolveInit = resolve
    }))
    const syncStudioAnipBaseUrl = vi.fn()
    const store = { baseUrl: 'http://127.0.0.1:49152' }

    vi.doMock('../store', () => ({ initFromConfig, store }))
    vi.doMock('../anip', () => ({ syncStudioAnipBaseUrl }))

    const { mountStudioApp } = await import('../bootstrap')
    const app = { mount: vi.fn() }

    mountStudioApp(app as any)

    expect(app.mount).toHaveBeenCalledWith('#app')
    expect(syncStudioAnipBaseUrl).not.toHaveBeenCalled()

    resolveInit()
    await Promise.resolve()

    expect(syncStudioAnipBaseUrl).toHaveBeenCalledWith('http://127.0.0.1:49152')
  })
})
