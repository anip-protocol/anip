import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchDiscovery, fetchManifest, invokeCapability, fetchPermissions } from '../api'
import {
  downloadRegistryTemplatePackage,
  getRegistryTemplate,
  getStudioSettings,
  listRegistryTemplates,
  publishRegistryPackage,
  publishRegistryTemplate,
  updateStudioSettings,
} from '../design/project-api'

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

describe('fetchDiscovery', () => {
  it('rejects SPA fallback HTML as a non-ANIP service root', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'text/html' }),
      json: () => Promise.reject(new Error('should not parse HTML')),
    })

    await expect(fetchDiscovery('http://localhost:8080'))
      .rejects.toThrow('does not look like an ANIP service root')
  })
})

describe('fetchManifest', () => {
  it('rejects SPA fallback HTML as a non-ANIP service root', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'text/html' }),
      json: () => Promise.reject(new Error('should not parse HTML')),
    })

    await expect(fetchManifest('http://localhost:8080'))
      .rejects.toThrow('does not look like an ANIP service root')
  })
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

describe('studio settings api', () => {
  it('loads combined assistant and Registry settings', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        assistant: {
          assistant_provider: 'deterministic',
          temperature: 0.2,
          timeout_seconds: 20,
          strict: false,
          api_key_configured: false,
          stored_api_key_configured: false,
          provider_source: 'default',
          model_source: 'default',
          base_url_source: 'default',
          api_key_source: 'none',
          temperature_source: 'default',
          timeout_seconds_source: 'default',
          strict_source: 'default',
          read_only_mode: false,
        },
        registry: {
          registry_url: 'http://127.0.0.1:8200',
          registry_url_source: 'default',
          required_registry_mode: null,
          required_registry_mode_source: 'unset',
          trusted_registry_key_id: null,
          trusted_registry_key_id_source: 'unset',
          publish_token_configured: false,
          publish_token_source: 'none',
          production_mode_detected: false,
          allows_development_registry: true,
          key_pinned: false,
          warning: 'Development Registry mode is allowed. Use only for local development.',
        },
      }),
    })

    const settings = await getStudioSettings()

    expect(mockFetch).toHaveBeenCalledWith('/api/settings', expect.objectContaining({}))
    expect(settings.assistant.assistant_provider).toBe('deterministic')
    expect(settings.registry.allows_development_registry).toBe(true)
  })

  it('falls back when the backend does not expose combined settings yet', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        text: () => Promise.resolve('{"detail":"Not Found"}'),
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({
          assistant_provider: 'deterministic',
          temperature: 0.2,
          timeout_seconds: 20,
          strict: false,
          api_key_configured: false,
          stored_api_key_configured: false,
          provider_source: 'default',
          model_source: 'default',
          base_url_source: 'default',
          api_key_source: 'none',
          temperature_source: 'default',
          timeout_seconds_source: 'default',
          strict_source: 'default',
          read_only_mode: false,
        }),
      })

    const settings = await getStudioSettings()

    expect(mockFetch).toHaveBeenNthCalledWith(1, '/api/settings', expect.objectContaining({}))
    expect(mockFetch).toHaveBeenNthCalledWith(2, '/api/runtime-config', expect.objectContaining({}))
    expect(settings.assistant.assistant_provider).toBe('deterministic')
    expect(settings.registry.registry_url_source).toBe('compatibility-default')
    expect(settings.registry.warning).toContain('does not expose /api/settings')
  })

  it('updates combined Studio settings', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        assistant: {
          assistant_provider: 'deterministic',
          temperature: 0.2,
          timeout_seconds: 20,
          strict: false,
          api_key_configured: false,
          stored_api_key_configured: false,
          provider_source: 'default',
          model_source: 'default',
          base_url_source: 'default',
          api_key_source: 'none',
          temperature_source: 'default',
          timeout_seconds_source: 'default',
          strict_source: 'default',
          read_only_mode: false,
        },
        registry: {
          registry_url: 'http://127.0.0.1:8300',
          registry_url_source: 'stored',
          required_registry_mode: 'production',
          required_registry_mode_source: 'stored',
          trusted_registry_key_id: 'registry-prod-local',
          trusted_registry_key_id_source: 'stored',
          publish_token_configured: true,
          publish_token_source: 'stored',
          production_mode_detected: false,
          allows_development_registry: false,
          key_pinned: true,
          warning: null,
        },
      }),
    })

    const settings = await updateStudioSettings({
      registry: {
        registry_url: 'http://127.0.0.1:8300',
        required_registry_mode: 'production',
        trusted_registry_key_id: 'registry-prod-local',
        registry_publish_token: 'publish-token',
      },
    })

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/settings',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          registry: {
            registry_url: 'http://127.0.0.1:8300',
            required_registry_mode: 'production',
            trusted_registry_key_id: 'registry-prod-local',
            registry_publish_token: 'publish-token',
          },
        }),
      }),
    )
    expect(settings.registry.required_registry_mode).toBe('production')
    expect(settings.registry.key_pinned).toBe(true)
  })
})

describe('registry publish api', () => {
  it('publishes through the Studio backend proxy', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        publication: {
          package_id: 'work-item-fronting',
          package_version: '0.2.0',
          project_ref: 'work-item-fronting',
          product_revision_ref: 'product-r3',
          developer_revision_ref: 'developer-r5',
          contract_signature: 'sha256:test-signature',
          publisher_id: 'studio-dev',
          publisher_type: 'studio',
          published_at: '2026-04-24T18:20:00Z',
        },
        package: {
          package_id: 'work-item-fronting',
          package_version: '0.2.0',
          project_ref: 'work-item-fronting',
          product_revision_ref: 'product-r3',
          developer_revision_ref: 'developer-r5',
          contract_signature: 'sha256:test-signature',
          publisher_id: 'studio-dev',
          publisher_type: 'studio',
          schema_version: 'anip-service-definition/v1',
          manifest_digest: 'sha256:manifest',
          definition_digest: 'sha256:definition',
          lock_digest: 'sha256:lock',
          published_at: '2026-04-24T18:20:00Z',
          manifest: {},
          service_definition: {},
          recommended_lock: {},
          implementation_materials: [
            {
              title: 'Reviewed app glue',
              ref: 'registry://acme/work-item-glue@1.2.3#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
            },
          ],
        },
        receipt: {
          receipt_id: 'receipt-1',
          package_id: 'work-item-fronting',
          package_version: '0.2.0',
          registry_signature: 'ed25519:key:sig',
          publisher_id: 'studio-dev',
          publisher_type: 'studio',
          issued_at: '2026-04-24T18:20:00Z',
        },
      }),
    })

    const payload = {
      package_id: 'work-item-fronting',
      package_version: '0.2.0',
      project_ref: 'work-item-fronting',
      product_revision_ref: 'product-r3',
      developer_revision_ref: 'developer-r5',
      contract_signature: 'sha256:test-signature',
      manifest: {},
      service_definition: {},
      recommended_lock: {},
      implementation_materials: [
        {
          title: 'Reviewed app glue',
          ref: 'registry://acme/work-item-glue@1.2.3#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        },
      ],
    }
    const result = await publishRegistryPackage(payload)

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/registry/publications',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    )
    expect(result.package.publisher_id).toBe('studio-dev')
    expect(result.package.implementation_materials?.[0]?.title).toBe('Reviewed app glue')
  })

  it('publishes starter templates through the Studio backend proxy', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({
        template: {
          template_id: 'notion-fronting-starter',
          template_version: '0.1.0',
          template_kind: 'fronting_starter',
          project_type: 'governed_service_project',
          anip_spec_version: 'anip/0.24',
          published_at: '2026-05-10T00:00:00Z',
          manifest_digest: 'sha256:manifest',
          template_digest: 'sha256:template',
          package_digest: 'sha256:package',
          manifest: {},
          template: {},
          package: {},
        },
      }),
    })

    const payload = {
      template_id: 'notion-fronting-starter',
      template_version: '0.1.0',
      manifest: {},
      template: {},
      package: {},
    }
    const result = await publishRegistryTemplate(payload)

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/registry/templates',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    )
    expect(result.template.template_id).toBe('notion-fronting-starter')
  })

  it('loads and downloads registry starter templates through the Studio backend proxy', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({
          items: [
            {
              template_id: 'notion-fronting-starter',
              template_version: '0.1.0',
              template_kind: 'fronting_starter',
              project_type: 'governed_service_project',
              anip_spec_version: 'anip/0.24',
              published_at: '2026-05-10T00:00:00Z',
              manifest: { template_title: 'Notion Fronting Starter' },
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({
          template_id: 'notion-fronting-starter',
          template_version: '0.1.0',
          template_kind: 'fronting_starter',
          project_type: 'governed_service_project',
          anip_spec_version: 'anip/0.24',
          manifest_digest: 'sha256:manifest',
          template_digest: 'sha256:template',
          package_digest: 'sha256:package',
          published_at: '2026-05-10T00:00:00Z',
          manifest: {},
          template: { id: 'notion-fronting-starter' },
          package: {},
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: () => Promise.resolve({
          schema: 'anip-starter-template-package/v0',
          package_kind: 'anip_starter_template',
          template: { id: 'notion-fronting-starter' },
        }),
      })

    const templates = await listRegistryTemplates()
    const template = await getRegistryTemplate('notion-fronting-starter', '0.1.0')
    const downloaded = await downloadRegistryTemplatePackage('notion-fronting-starter', '0.1.0')

    expect(mockFetch).toHaveBeenNthCalledWith(1, '/api/registry/templates', expect.objectContaining({}))
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      '/api/registry/templates/notion-fronting-starter/0.1.0',
      expect.objectContaining({}),
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      3,
      '/api/registry/templates/notion-fronting-starter/0.1.0/download',
      expect.objectContaining({}),
    )
    expect(templates.items[0].manifest.template_title).toBe('Notion Fronting Starter')
    expect(template.template_id).toBe('notion-fronting-starter')
    expect(downloaded.template.id).toBe('notion-fronting-starter')
  })
})
