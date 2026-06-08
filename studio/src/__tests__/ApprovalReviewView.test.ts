import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ApprovalReviewView from '../views/ApprovalReviewView.vue'

vi.mock('../store', () => ({
  store: {
    baseUrl: 'http://localhost:9200',
    bearer: 'demo-human-key',
    connected: true,
    error: '',
    loading: false,
    serviceId: 'anip-gtm-pipeline-showcase',
  },
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      { path: '/inspect/approvals', name: 'approvals', component: ApprovalReviewView },
    ],
  })
}

async function mountView(
  initialRoute = '/inspect/approvals?listPath=%2Fgtm%2Fapprovals&approvePathTemplate=%2Fgtm%2Fapprovals%2F%7BapprovalRequestId%7D%2Fapprove&status=pending',
) {
  const router = makeRouter()
  router.push(initialRoute)
  await router.isReady()
  const wrapper = mount(ApprovalReviewView, {
    global: {
      plugins: [router],
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('ApprovalReviewView', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('hydrates the configured approval list surface and renders entries', async () => {
    ;(globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        entries: [
          {
            approval_request_id: 'apr-123',
            status: 'pending',
            capability: 'gtm.prepare_followup_tasks',
            requested_by: { actor_id: 'rev_ops_manager', role: 'rev_ops_manager' },
            required_role: 'sales_leader',
            requested_at: '2026-04-13T04:55:45Z',
          },
        ],
      }),
    })

    const { wrapper } = await mountView()
    await wrapper.find('.fetch-btn').trigger('click')
    await flushPromises()

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:9200/gtm/approvals?status=pending',
      expect.objectContaining({
        headers: { Authorization: 'Bearer demo-human-key' },
      }),
    )
    expect(wrapper.text()).toContain('Approval Review')
    expect(wrapper.text()).toContain('apr-123')
    expect(wrapper.text()).toContain('rev_ops_manager (rev_ops_manager)')
  })

  it('can approve a pending request through the configured approval action surface', async () => {
    ;(globalThis.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          entries: [
            {
              approval_request_id: 'apr-123',
              status: 'pending',
              capability: 'gtm.prepare_followup_tasks',
              requested_by: { actor_id: 'rev_ops_manager', role: 'rev_ops_manager' },
              required_role: 'sales_leader',
              requested_at: '2026-04-13T04:55:45Z',
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          approval: {
            approval_request_id: 'apr-123',
            status: 'approved',
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          entries: [
            {
              approval_request_id: 'apr-123',
              status: 'approved',
              capability: 'gtm.prepare_followup_tasks',
              requested_by: { actor_id: 'rev_ops_manager', role: 'rev_ops_manager' },
              approved_by: { actor_id: 'sales_leader', role: 'sales_leader' },
              required_role: 'sales_leader',
              requested_at: '2026-04-13T04:55:45Z',
            },
          ],
        }),
      })

    const { wrapper } = await mountView()
    await wrapper.find('.fetch-btn').trigger('click')
    await flushPromises()
    await wrapper.find('.approve-btn').trigger('click')
    await flushPromises()

    expect((globalThis.fetch as any).mock.calls[1][0]).toBe('http://localhost:9200/gtm/approvals/apr-123/approve')
    expect((globalThis.fetch as any).mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        headers: { Authorization: 'Bearer demo-human-key' },
      }),
    )
    expect(wrapper.text()).toContain('Last Approval Action')
    expect(wrapper.text()).toContain('approved')
  })
})
