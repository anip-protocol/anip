import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ANIPClient } from '@anip-dev/client'
import { AnipClientKey } from '@anip-dev/vue'
import DiscoveryView from '../views/DiscoveryView.vue'
import { STUDIO_PROTOCOL_VERSION } from '../version'

const BASE_URL = 'http://127.0.0.1:9100'

vi.mock('../store', () => ({
  store: {
    baseUrl: 'http://127.0.0.1:9100',
    bearer: '',
    connected: true,
    error: '',
    loading: false,
    serviceId: 'anip-flight-service',
  },
}))

vi.mock('../design/store', () => ({
  designStore: { observedServiceMetadata: null, selectedObservedServiceMetadataId: null },
  recordObservedServiceMetadata: vi.fn(),
  setSelectedObservedServiceMetadataId: vi.fn(),
}))

vi.mock('../design/project-store', () => ({
  projectStore: { activeProject: null, artifacts: { serviceMetadata: [] } },
}))

vi.mock('../design/project-api', () => ({
  createServiceMetadata: vi.fn(),
  updateServiceMetadata: vi.fn(),
}))

/**
 * The discovery document as the Python flight example (`examples/anip`) sends
 * it. All five runtimes build this shape (SPEC.md §6.1): `side_effect` is a
 * string and the trust level is the top-level `trust_level`.
 */
function flightServiceDiscovery() {
  return {
    anip_discovery: {
      protocol: STUDIO_PROTOCOL_VERSION,
      compliance: 'anip-compliant',
      profile: { core: '1.0', cost: '1.0', capability_graph: '1.0', state_session: '1.0', observability: '1.0' },
      auth: {
        delegation_token_required: true,
        supported_formats: ['anip-v1'],
        minimum_scope_for_discovery: 'none',
      },
      capabilities: {
        search_flights: {
          description: 'Search available flights by origin, destination, and date',
          side_effect: 'read',
          minimum_scope: ['travel.search'],
          financial: false,
          contract: '1.0',
        },
        book_flight: {
          description: 'Book a confirmed flight reservation',
          side_effect: 'irreversible',
          minimum_scope: ['travel.book'],
          financial: true,
          contract: '1.0',
        },
      },
      trust_level: 'signed',
      posture: {
        audit: { enabled: true, signed: true, queryable: true, retention: 'P90D', retention_enforced: true },
        failure_disclosure: { detail_level: 'full', caller_classes: null },
        anchoring: { enabled: false, cadence: null, max_lag: null, proofs_available: false },
      },
      endpoints: {
        manifest: '/anip/manifest',
        permissions: '/anip/permissions',
        invoke: '/anip/invoke/{capability}',
        tokens: '/anip/tokens',
        audit: '/anip/audit',
      },
      base_url: BASE_URL,
    },
  }
}

/** The manifest carries the full declaration: `side_effect` is an object here. */
function flightServiceManifest() {
  return {
    protocol: STUDIO_PROTOCOL_VERSION,
    profile: { core: '1.0' },
    capabilities: {
      search_flights: {
        name: 'search_flights',
        description: 'Search available flights by origin, destination, and date',
        contract_version: '1.0',
        side_effect: { type: 'read', rollback_window: 'not_applicable' },
        minimum_scope: ['travel.search'],
      },
      book_flight: {
        name: 'book_flight',
        description: 'Book a confirmed flight reservation',
        contract_version: '1.0',
        side_effect: { type: 'irreversible', rollback_window: 'none' },
        minimum_scope: ['travel.book'],
      },
    },
    trust: { level: 'signed', anchoring: null, policies: null },
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

async function mountView(discovery: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url === `${BASE_URL}/.well-known/anip`) return jsonResponse(discovery)
    if (url === `${BASE_URL}/anip/manifest`) return jsonResponse(flightServiceManifest())
    return new Response('not found', { status: 404 })
  }))

  const wrapper = mount(DiscoveryView, {
    global: {
      provide: { [AnipClientKey as symbol]: new ANIPClient(BASE_URL) },
    },
  })
  await flushPromises()
  return wrapper
}

function capabilityRow(wrapper: Awaited<ReturnType<typeof mountView>>, name: string) {
  const row = wrapper.findAll('table.data-table tbody tr').find((tr) => tr.find('td').text() === name)
  if (!row) throw new Error(`no capability row for ${name}`)
  return row
}

beforeEach(() => {
  vi.unstubAllGlobals()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DiscoveryView', () => {
  it('shows each capability with the side effect the service declares', async () => {
    const wrapper = await mountView(flightServiceDiscovery())

    const search = capabilityRow(wrapper, 'search_flights').find('.status-badge')
    expect(search.text()).toBe('read')
    expect(search.classes()).toContain('success')

    const book = capabilityRow(wrapper, 'book_flight').find('.status-badge')
    expect(book.text()).toBe('irreversible')
    expect(book.classes()).toContain('danger')
  })

  it('shows scope, financial flag and contract per capability', async () => {
    const wrapper = await mountView(flightServiceDiscovery())

    const book = capabilityRow(wrapper, 'book_flight')
    expect(book.find('.scope-chip').text()).toBe('travel.book')
    expect(book.find('.check-mark').exists()).toBe(true)
    expect(book.findAll('td')[4].text()).toBe('1.0')
    expect(capabilityRow(wrapper, 'search_flights').find('.check-mark').exists()).toBe(false)
  })

  it('shows the protocol, compliance and trust level of the service', async () => {
    const wrapper = await mountView(flightServiceDiscovery())

    const badges = wrapper.findAll('.identity-row .status-badge').map((badge) => badge.text())
    expect(badges).toEqual([STUDIO_PROTOCOL_VERSION, 'anip-compliant', 'signed'])
    expect(wrapper.find('.identity-row .base-url').text()).toBe(BASE_URL)
  })

  it('shows an undeclared side effect as unknown instead of read', async () => {
    const discovery: any = flightServiceDiscovery()
    delete discovery.anip_discovery.capabilities.book_flight.side_effect

    const wrapper = await mountView(discovery)

    const book = capabilityRow(wrapper, 'book_flight').find('.status-badge')
    expect(book.text()).toBe('unknown')
    expect(book.classes()).toContain('neutral')
  })
})
